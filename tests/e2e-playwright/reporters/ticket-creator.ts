import * as fs from 'fs';
import * as path from 'path';
import type { ErrorEntry } from './report-generator.js';

export interface TicketData {
  title: string;
  category: string;
  severity: string;
  source_test: string;
  created: string;
  status: string;
  context: Record<string, unknown>;
  steps_to_reproduce: string[];
  suggested_fix: string;
}

const TICKET_SEVERITIES_TO_CREATE = new Set(['critical', 'major']);

export function createTickets(
  errors: ErrorEntry[],
  ticketsDir: string,
  rom: string,
): { created: string[]; skipped: string[] } {
  fs.mkdirSync(ticketsDir, { recursive: true });

  const created: string[] = [];
  const skipped: string[] = [];

  const eligibleErrors = errors.filter(e => TICKET_SEVERITIES_TO_CREATE.has(e.severity));

  for (const error of eligibleErrors) {
    const ticketFilename = buildTicketFilename(error);
    const ticketPath = path.join(ticketsDir, ticketFilename);

    if (isDuplicate(error, ticketsDir)) {
      skipped.push(error.id);
      continue;
    }

    const ticket = buildTicket(error, rom);
    const yaml = serializeYaml(ticket);
    fs.writeFileSync(ticketPath, yaml, 'utf-8');
    created.push(ticketFilename);
  }

  return { created, skipped };
}

function buildTicketFilename(error: ErrorEntry): string {
  const sanitized = error.id.toLowerCase().replace(/[^a-z0-9-]/g, '-');
  return `auto-${error.category.toLowerCase()}-${sanitized}.yaml`;
}

function isDuplicate(error: ErrorEntry, ticketsDir: string): boolean {
  if (!fs.existsSync(ticketsDir)) return false;

  const existingFiles = fs.readdirSync(ticketsDir).filter((f: string) => f.endsWith('.yaml'));
  for (const file of existingFiles) {
    try {
      const content = fs.readFileSync(path.join(ticketsDir, file), 'utf-8');
      const existingCategory = extractYamlField(content, 'category');
      const existingStatus = extractYamlField(content, 'status');

      if (existingStatus === 'resolved') continue;

      if (existingCategory === error.category) {
        const existingExpected = extractYamlField(content, 'expected');
        const existingActual = extractYamlField(content, 'actual');

        if (
          existingExpected === (error.expected ?? '') &&
          existingActual === (error.actual ?? '')
        ) {
          return true;
        }
      }
    } catch {
      continue;
    }
  }
  return false;
}

function buildTicket(error: ErrorEntry, rom: string): TicketData {
  const shortDesc = buildShortDescription(error);

  return {
    title: `[AUTO] ${error.category}: ${shortDesc}`,
    category: error.category,
    severity: error.severity,
    source_test: error.test,
    created: new Date().toISOString(),
    status: 'open',
    context: {
      rom,
      ...(error.gameState?.frame != null && { frame: error.gameState.frame }),
      ...(error.gameState?.screen && { screen: error.gameState.screen }),
      ...(error.expected && { expected: error.expected }),
      ...(error.actual && { actual: error.actual }),
      ...(error.memoryDump && { memory_dump: error.memoryDump }),
      ...(error.screenshot && { screenshot: error.screenshot }),
    },
    steps_to_reproduce: buildStepsToReproduce(error, rom),
    suggested_fix: buildSuggestedFix(error),
  };
}

function buildShortDescription(error: ErrorEntry): string {
  if (error.expected && error.actual) {
    const expected = error.expected.slice(0, 40);
    const actual = error.actual.slice(0, 40);
    return `'${actual}' au lieu de '${expected}'`;
  }
  return error.message.slice(0, 80);
}

function buildStepsToReproduce(error: ErrorEntry, rom: string): string[] {
  const steps: string[] = [`Charger ${rom}`];

  if (error.gameState?.frame != null) {
    steps.push(`Avancer ${error.gameState.frame} frames`);
  }

  if (error.gameState?.screen) {
    steps.push(`Naviguer vers l'écran: ${error.gameState.screen}`);
  }

  if (error.memoryDump) {
    steps.push(`Lire le buffer texte en mémoire`);
  }

  steps.push(`Lancer le test: ${error.test}`);
  steps.push(`Observer l'erreur: ${error.message.slice(0, 100)}`);

  return steps;
}

function buildSuggestedFix(error: ErrorEntry): string {
  switch (error.category) {
    case 'CRASH':
      return "Analyser le dump mémoire et les logs WebSocket pour identifier la cause du crash. Vérifier les pointeurs de texte modifiés.";
    case 'WRONG_TEXT':
      return `Vérifier l'entrée de traduction dans translation_en_fr.json pour le texte incorrect.`;
    case 'MISSING_TRANSLATION':
      return "Ajouter ou corriger la traduction manquante dans translation_en_fr.json.";
    case 'VISUAL_REGRESSION':
      return "Comparer le screenshot avec le golden et mettre à jour si le changement est intentionnel.";
    case 'ENCODING_ERROR':
      return "Vérifier la table charmap Pokemon (text_codec.py) pour le caractère problématique. Vérifier les alias d'encodage.";
    case 'OVERFLOW':
      return "Raccourcir la traduction française ou ajuster la zone d'affichage si possible.";
    case 'TIMEOUT':
      return "Vérifier que l'émulateur répond correctement. Augmenter le timeout si le scénario est intrinsèquement long.";
  }
}

function serializeYaml(ticket: TicketData): string {
  const lines: string[] = [];

  lines.push(`title: ${yamlString(ticket.title)}`);
  lines.push(`category: ${ticket.category}`);
  lines.push(`severity: ${ticket.severity}`);
  lines.push(`source_test: ${yamlString(ticket.source_test)}`);
  lines.push(`created: ${yamlString(ticket.created)}`);
  lines.push(`status: ${ticket.status}`);

  lines.push('context:');
  for (const [key, value] of Object.entries(ticket.context)) {
    if (typeof value === 'string') {
      lines.push(`  ${key}: ${yamlString(value)}`);
    } else {
      lines.push(`  ${key}: ${value}`);
    }
  }

  lines.push('steps_to_reproduce:');
  for (const step of ticket.steps_to_reproduce) {
    lines.push(`  - ${yamlString(step)}`);
  }

  lines.push(`suggested_fix: ${yamlString(ticket.suggested_fix)}`);

  return lines.join('\n') + '\n';
}

function yamlString(value: string): string {
  if (/[:#\[\]{}|>&*!%@,]/.test(value) || value.includes('\n') || value.startsWith("'") || value.startsWith('"')) {
    return `"${value.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`;
  }
  return `"${value}"`;
}

function extractYamlField(content: string, field: string): string {
  const match = content.match(new RegExp(`^\\s*${field}:\\s*"?([^"\\n]*)"?`, 'm'));
  return match?.[1]?.trim() ?? '';
}
