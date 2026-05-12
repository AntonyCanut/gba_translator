import * as fs from 'fs';
import * as path from 'path';
import type {
  FullConfig,
  FullResult,
  Reporter,
  Suite,
  TestCase,
  TestResult,
} from '@playwright/test/reporter';
import { classifyError } from './error-classifier.js';
import {
  generateJsonReport,
  generateMarkdownReport,
  type ErrorEntry,
  type TestReport,
} from './report-generator.js';
import { createTickets } from './ticket-creator.js';

export interface ErrorReporterOptions {
  outputDir?: string;
  ticketsDir?: string;
  rom?: string;
  createTicketsEnabled?: boolean;
}

let errorCounter = 0;

function nextErrorId(): string {
  errorCounter++;
  return `ERR-${String(errorCounter).padStart(3, '0')}`;
}

class GBAErrorReporter implements Reporter {
  private outputDir: string;
  private ticketsDir: string;
  private rom: string;
  private createTicketsEnabled: boolean;
  private errors: ErrorEntry[] = [];
  private totalTests = 0;
  private passedTests = 0;
  private failedTests = 0;
  private skippedTests = 0;
  private startTime = 0;
  private wsLogs: Map<string, string[]> = new Map();

  constructor(options: ErrorReporterOptions = {}) {
    this.outputDir = options.outputDir ?? 'test-results/reports';
    this.ticketsDir = options.ticketsDir ?? 'tickets';
    this.rom = options.rom ?? 'frenchrom.gba';
    this.createTicketsEnabled = options.createTicketsEnabled ?? true;
  }

  onBegin(_config: FullConfig, _suite: Suite): void {
    this.startTime = Date.now();
    errorCounter = 0;
    this.errors = [];
    this.totalTests = 0;
    this.passedTests = 0;
    this.failedTests = 0;
    this.skippedTests = 0;
    this.wsLogs.clear();

    fs.mkdirSync(this.outputDir, { recursive: true });
    fs.mkdirSync(path.join(this.outputDir, '..', 'screenshots'), { recursive: true });
  }

  onTestEnd(test: TestCase, result: TestResult): void {
    this.totalTests++;

    if (result.status === 'passed') {
      this.passedTests++;
      return;
    }

    if (result.status === 'skipped') {
      this.skippedTests++;
      return;
    }

    this.failedTests++;

    const rawMessage = result.error?.message ?? 'Unknown error';
    const errorMessage = stripAnsi(rawMessage);
    const stackTrace = result.error?.stack;

    const { expected, actual } = extractExpectedActual(errorMessage);
    const gameState = extractGameState(errorMessage, result.attachments);
    const memoryDump = extractMemoryDump(errorMessage, result.attachments);
    const wsLogsForTest = this.wsLogs.get(test.id) ?? extractWsLogs(result.attachments);

    const classification = classifyError(
      test.title,
      errorMessage,
      expected,
      actual,
    );

    const errorId = nextErrorId();

    const screenshotPath = this.saveScreenshots(errorId, result.attachments);

    const entry: ErrorEntry = {
      id: errorId,
      test: buildTestTitle(test),
      file: test.location.file,
      category: classification.category,
      severity: classification.severity,
      message: errorMessage.slice(0, 500),
      stackTrace: stackTrace?.slice(0, 2000),
      expected,
      actual,
      screenshot: screenshotPath,
      gameState,
      memoryDump,
      wsLogs: wsLogsForTest,
      tags: classification.tags,
      confidence: classification.confidence,
      duration: result.duration,
    };

    this.errors.push(entry);
  }

  onEnd(result: FullResult): void {
    const duration = Date.now() - this.startTime;
    const timestamp = new Date().toISOString();

    const report: TestReport = {
      timestamp,
      rom: this.rom,
      totalTests: this.totalTests,
      passed: this.passedTests,
      failed: this.failedTests,
      skipped: this.skippedTests,
      duration,
      errors: this.errors,
    };

    const jsonPath = generateJsonReport(report, this.outputDir);
    const mdPath = generateMarkdownReport(report, this.outputDir);

    console.log(`\n[GBA Reporter] Rapport JSON: ${jsonPath}`);
    console.log(`[GBA Reporter] Rapport Markdown: ${mdPath}`);
    console.log(`[GBA Reporter] Total: ${this.totalTests} | Réussis: ${this.passedTests} | Échoués: ${this.failedTests} | Ignorés: ${this.skippedTests}`);

    if (this.errors.length > 0) {
      console.log(`\n[GBA Reporter] Erreurs détectées:`);
      for (const err of this.errors) {
        console.log(`  ${err.id} [${err.severity}] ${err.category}: ${err.message.slice(0, 100)}`);
      }
    }

    if (this.createTicketsEnabled && this.errors.length > 0) {
      const { created, skipped } = createTickets(this.errors, this.ticketsDir, this.rom);
      if (created.length > 0) {
        console.log(`\n[GBA Reporter] Tickets créés: ${created.length}`);
        for (const t of created) {
          console.log(`  + ${t}`);
        }
      }
      if (skipped.length > 0) {
        console.log(`[GBA Reporter] Tickets dédupliqués (ignorés): ${skipped.length}`);
      }
    }

    console.log(`\n[GBA Reporter] Statut final: ${result.status}`);
  }

  addWsLog(testId: string, log: string): void {
    const logs = this.wsLogs.get(testId) ?? [];
    logs.push(log);
    this.wsLogs.set(testId, logs);
  }

  private saveScreenshots(errorId: string, attachments: TestResult['attachments']): string | undefined {
    const screenshotDir = path.join(this.outputDir, '..', 'screenshots');
    fs.mkdirSync(screenshotDir, { recursive: true });

    for (const attachment of attachments) {
      if (attachment.contentType?.startsWith('image/') && attachment.body) {
        const ext = attachment.contentType === 'image/png' ? 'png' : 'jpg';
        const filename = `${errorId.toLowerCase()}.${ext}`;
        const filePath = path.join(screenshotDir, filename);
        fs.writeFileSync(filePath, attachment.body);
        return path.relative(process.cwd(), filePath);
      }

      if (attachment.contentType?.startsWith('image/') && attachment.path) {
        const ext = path.extname(attachment.path) || '.png';
        const filename = `${errorId.toLowerCase()}${ext}`;
        const destPath = path.join(screenshotDir, filename);
        try {
          fs.copyFileSync(attachment.path, destPath);
          return path.relative(process.cwd(), destPath);
        } catch {
          return attachment.path;
        }
      }
    }

    return undefined;
  }
}

function buildTestTitle(test: TestCase): string {
  const parts: string[] = [];
  let parent: Suite | undefined = test.parent;
  while (parent) {
    if (parent.title) parts.unshift(parent.title);
    parent = parent.parent;
  }
  parts.push(test.title);
  return parts.join(' > ');
}

function stripAnsi(text: string): string {
  // eslint-disable-next-line no-control-regex
  return text.replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '');
}

function extractExpectedActual(errorMessage: string): { expected?: string; actual?: string } {
  const playwrightExpected = errorMessage.match(/Expected:\s*"(.+?)"/);
  const playwrightReceived = errorMessage.match(/Received:\s*"(.+?)"/);
  if (playwrightExpected && playwrightReceived) {
    return { expected: playwrightExpected[1], actual: playwrightReceived[1] };
  }

  const expectedMatch = errorMessage.match(/expected\s*[=:]\s*["']?(.+?)["']?\s*(?:$|,|\n|but|received|actual|got)/i);
  const actualMatch = errorMessage.match(/(?:actual|received|got)\s*[=:]\s*["']?(.+?)["']?\s*(?:$|\n)/i);

  if (!expectedMatch && !actualMatch) {
    const toBeMatch = errorMessage.match(/expected\s+["'](.+?)["']\s+to\s+be\s+["'](.+?)["']/i);
    if (toBeMatch) {
      return { actual: toBeMatch[1], expected: toBeMatch[2] };
    }
  }

  return {
    expected: expectedMatch?.[1]?.trim(),
    actual: actualMatch?.[1]?.trim(),
  };
}

function extractGameState(
  errorMessage: string,
  attachments: TestResult['attachments'],
): ErrorEntry['gameState'] | undefined {
  for (const att of attachments) {
    if (att.name === 'gameState' && att.body) {
      try {
        return JSON.parse(att.body.toString());
      } catch {
        // fall through
      }
    }
  }

  const frameMatch = errorMessage.match(/frame[s]?\s*[=:]\s*(\d+)/i);
  const mapMatch = errorMessage.match(/map\s*[=:]\s*(\d+)/i);

  if (frameMatch || mapMatch) {
    return {
      ...(frameMatch && { frame: parseInt(frameMatch[1], 10) }),
      ...(mapMatch && { mapNumber: parseInt(mapMatch[1], 10) }),
    };
  }

  return undefined;
}

function extractMemoryDump(
  errorMessage: string,
  attachments: TestResult['attachments'],
): string | undefined {
  for (const att of attachments) {
    if (att.name === 'memoryDump' && att.body) {
      return att.body.toString();
    }
  }

  const memMatch = errorMessage.match(/(0x[0-9a-fA-F]+:\s*(?:[0-9a-fA-F]{2}\s*)+)/);
  return memMatch?.[1];
}

function extractWsLogs(attachments: TestResult['attachments']): string[] {
  for (const att of attachments) {
    if (att.name === 'wsLogs' && att.body) {
      try {
        return JSON.parse(att.body.toString());
      } catch {
        return att.body.toString().split('\n').filter(Boolean);
      }
    }
  }
  return [];
}

export default GBAErrorReporter;
