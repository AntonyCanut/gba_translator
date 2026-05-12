import * as fs from 'fs';
import * as path from 'path';
import type { ErrorCategory, Severity } from './error-classifier.js';

export interface ErrorEntry {
  id: string;
  test: string;
  file: string;
  category: ErrorCategory;
  severity: Severity;
  message: string;
  stackTrace?: string;
  expected?: string;
  actual?: string;
  screenshot?: string;
  screenshotBefore?: string;
  gameState?: {
    frame?: number;
    screen?: string;
    mapGroup?: number;
    mapNumber?: number;
    playerX?: number;
    playerY?: number;
    inBattle?: boolean;
    textActive?: boolean;
  };
  memoryDump?: string;
  wsLogs?: string[];
  tags: string[];
  confidence: number;
  duration?: number;
}

export interface TestReport {
  timestamp: string;
  rom: string;
  totalTests: number;
  passed: number;
  failed: number;
  skipped: number;
  duration: number;
  errors: ErrorEntry[];
}

export function generateJsonReport(report: TestReport, outputDir: string): string {
  fs.mkdirSync(outputDir, { recursive: true });
  const filename = `report-${formatTimestamp(report.timestamp)}.json`;
  const filePath = path.join(outputDir, filename);
  fs.writeFileSync(filePath, JSON.stringify(report, null, 2), 'utf-8');
  return filePath;
}

export function generateMarkdownReport(report: TestReport, outputDir: string): string {
  fs.mkdirSync(outputDir, { recursive: true });
  const filename = `report-${formatTimestamp(report.timestamp)}.md`;
  const filePath = path.join(outputDir, filename);

  const lines: string[] = [];
  lines.push(`# Rapport de tests Playwright — GBA Translator`);
  lines.push('');
  lines.push(`**Date :** ${report.timestamp}`);
  lines.push(`**ROM :** ${report.rom}`);
  lines.push(`**Durée :** ${(report.duration / 1000).toFixed(1)}s`);
  lines.push('');

  lines.push('## Résumé');
  lines.push('');
  lines.push('| Métrique | Valeur |');
  lines.push('|----------|--------|');
  lines.push(`| Total | ${report.totalTests} |`);
  lines.push(`| Réussis | ${report.passed} |`);
  lines.push(`| Échoués | ${report.failed} |`);
  lines.push(`| Ignorés | ${report.skipped} |`);
  lines.push(`| Taux de réussite | ${report.totalTests > 0 ? ((report.passed / report.totalTests) * 100).toFixed(1) : 0}% |`);
  lines.push('');

  if (report.errors.length === 0) {
    lines.push('> Tous les tests sont passés avec succès.');
    fs.writeFileSync(filePath, lines.join('\n'), 'utf-8');
    return filePath;
  }

  const bySeverity = groupBy(report.errors, e => e.severity);
  const byCategory = groupBy(report.errors, e => e.category);

  lines.push('## Répartition par sévérité');
  lines.push('');
  lines.push('| Sévérité | Nombre |');
  lines.push('|----------|--------|');
  for (const sev of ['critical', 'major', 'minor'] as Severity[]) {
    const count = bySeverity[sev]?.length ?? 0;
    if (count > 0) {
      lines.push(`| ${severityEmoji(sev)} ${sev} | ${count} |`);
    }
  }
  lines.push('');

  lines.push('## Répartition par catégorie');
  lines.push('');
  lines.push('| Catégorie | Nombre |');
  lines.push('|-----------|--------|');
  for (const [cat, errs] of Object.entries(byCategory)) {
    lines.push(`| ${cat} | ${errs.length} |`);
  }
  lines.push('');

  lines.push('## Détails des erreurs');
  lines.push('');

  for (const error of report.errors) {
    lines.push(`### ${error.id} — ${error.category} (${error.severity})`);
    lines.push('');
    lines.push(`**Test :** \`${error.test}\``);
    lines.push(`**Fichier :** \`${error.file}\``);
    lines.push(`**Message :** ${error.message}`);
    lines.push('');

    if (error.expected || error.actual) {
      lines.push('| Champ | Valeur |');
      lines.push('|-------|--------|');
      if (error.expected) lines.push(`| Attendu | \`${error.expected}\` |`);
      if (error.actual) lines.push(`| Obtenu | \`${error.actual}\` |`);
      lines.push('');
    }

    if (error.gameState) {
      lines.push('**État du jeu :**');
      lines.push('');
      lines.push('```json');
      lines.push(JSON.stringify(error.gameState, null, 2));
      lines.push('```');
      lines.push('');
    }

    if (error.memoryDump) {
      lines.push(`**Memory dump :** \`${error.memoryDump}\``);
      lines.push('');
    }

    if (error.screenshot) {
      lines.push(`**Screenshot :** ![${error.id}](${error.screenshot})`);
      lines.push('');
    }

    if (error.stackTrace) {
      lines.push('<details>');
      lines.push('<summary>Stack trace</summary>');
      lines.push('');
      lines.push('```');
      lines.push(error.stackTrace);
      lines.push('```');
      lines.push('');
      lines.push('</details>');
      lines.push('');
    }

    if (error.wsLogs && error.wsLogs.length > 0) {
      lines.push('<details>');
      lines.push('<summary>WebSocket logs</summary>');
      lines.push('');
      lines.push('```');
      for (const log of error.wsLogs.slice(-20)) {
        lines.push(log);
      }
      lines.push('```');
      lines.push('');
      lines.push('</details>');
      lines.push('');
    }

    lines.push('---');
    lines.push('');
  }

  fs.writeFileSync(filePath, lines.join('\n'), 'utf-8');
  return filePath;
}

function formatTimestamp(iso: string): string {
  return iso.replace(/[:.]/g, '-').replace('T', '_').slice(0, 19);
}

function severityEmoji(sev: Severity): string {
  switch (sev) {
    case 'critical': return '[CRIT]';
    case 'major': return '[MAJ]';
    case 'minor': return '[MIN]';
  }
}

function groupBy<T>(items: T[], key: (item: T) => string): Record<string, T[]> {
  const result: Record<string, T[]> = {};
  for (const item of items) {
    const k = key(item);
    (result[k] ??= []).push(item);
  }
  return result;
}
