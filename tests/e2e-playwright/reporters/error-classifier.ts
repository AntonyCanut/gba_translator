export type ErrorCategory =
  | 'CRASH'
  | 'WRONG_TEXT'
  | 'MISSING_TRANSLATION'
  | 'VISUAL_REGRESSION'
  | 'ENCODING_ERROR'
  | 'OVERFLOW'
  | 'TIMEOUT';

export type Severity = 'critical' | 'major' | 'minor';

export interface ClassifiedError {
  category: ErrorCategory;
  severity: Severity;
  tags: string[];
  confidence: number;
}

const CATEGORY_CONFIG: Record<ErrorCategory, { severity: Severity; tags: string[] }> = {
  CRASH: { severity: 'critical', tags: ['stability', 'blocker', 'rom'] },
  WRONG_TEXT: { severity: 'major', tags: ['translation', 'text', 'i18n'] },
  MISSING_TRANSLATION: { severity: 'major', tags: ['translation', 'missing', 'i18n'] },
  VISUAL_REGRESSION: { severity: 'major', tags: ['visual', 'regression', 'screenshot'] },
  ENCODING_ERROR: { severity: 'major', tags: ['encoding', 'charmap', 'corruption'] },
  OVERFLOW: { severity: 'minor', tags: ['layout', 'overflow', 'text'] },
  TIMEOUT: { severity: 'minor', tags: ['performance', 'timeout', 'emulator'] },
};

const CRASH_PATTERNS = [
  /crash/i,
  /PC invalide/i,
  /invalid PC/i,
  /reboot/i,
  /freeze/i,
  /hung/i,
  /callback1.*stuck/i,
  /black\s*screen/i,
  /infinite\s*loop/i,
];

const ENCODING_PATTERNS = [
  /�/,
  /corrompus?/i,
  /corrupted/i,
  /charmap/i,
  /invalid.*char/i,
  /\?{3,}/,
  /\x00/,
];

const OVERFLOW_PATTERNS = [
  /overflow/i,
  /déborde/i,
  /dépasse/i,
  /truncat/i,
  /trop long/i,
  /too long/i,
  /exceeds.*width/i,
];

const ENGLISH_WORDS = [
  'NEW GAME', 'CONTINUE', 'OPTIONS', 'POKEMON', 'ATTACK', 'FIGHT',
  'BAG', 'RUN', 'POTION', 'SAVE', 'PLAYER', 'BADGES', 'YES', 'NO',
  'ITEMS', 'PARTY', 'SUMMARY', 'SWITCH', 'CANCEL', 'CONFIRM',
];

export function classifyError(
  testTitle: string,
  errorMessage: string,
  expected?: string,
  actual?: string,
): ClassifiedError {
  const combined = `${testTitle} ${errorMessage} ${expected ?? ''} ${actual ?? ''}`;

  if (matchesAny(combined, CRASH_PATTERNS)) {
    return makeResult('CRASH', 1.0);
  }

  if (/timeout|timed?\s*out|TIMEOUT/i.test(errorMessage)) {
    return makeResult('TIMEOUT', 0.9);
  }

  if (expected && actual) {
    const hasEnglishActual = ENGLISH_WORDS.some(w =>
      actual.toUpperCase().includes(w),
    );
    const hasFrenchExpected = /[éèêàùçîôûëïœ]/i.test(expected) ||
      /NOUVELLE|CONTINUER|SAUVEGARDER|ATTAQUE|COMBAT|SAC|FUITE/i.test(expected);

    if (hasEnglishActual && hasFrenchExpected) {
      return makeResult('MISSING_TRANSLATION', 0.95);
    }
    if (hasEnglishActual) {
      return makeResult('MISSING_TRANSLATION', 0.8);
    }
    return makeResult('WRONG_TEXT', 0.9);
  }

  if (matchesAny(combined, ENCODING_PATTERNS)) {
    return makeResult('ENCODING_ERROR', 0.85);
  }

  if (matchesAny(combined, OVERFLOW_PATTERNS)) {
    return makeResult('OVERFLOW', 0.8);
  }

  if (/screenshot|visual|snapshot|pixel|image.*diff/i.test(combined)) {
    return makeResult('VISUAL_REGRESSION', 0.85);
  }

  if (/translat|traduction|anglais|english|french|français/i.test(combined)) {
    return makeResult('MISSING_TRANSLATION', 0.7);
  }

  if (/text|texte|string|chaîne|affich/i.test(combined)) {
    return makeResult('WRONG_TEXT', 0.6);
  }

  return makeResult('TIMEOUT', 0.3);
}

function matchesAny(text: string, patterns: RegExp[]): boolean {
  return patterns.some(p => p.test(text));
}

function makeResult(category: ErrorCategory, confidence: number): ClassifiedError {
  const config = CATEGORY_CONFIG[category];
  return {
    category,
    severity: config.severity,
    tags: [...config.tags],
    confidence,
  };
}
