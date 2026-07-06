export const ADDRESSES = {
  gStringVar1: 0x02021d18,
  gStringVar2: 0x02021d28,
  gStringVar3: 0x02021d38,
  gStringVar4: 0x02021d48,
  STRING_VAR_SIZE_SMALL: 16,
  STRING_VAR4_SIZE: 1000,

  battleTextBuffer1: 0x02022e4c,
  battleTextBuffer2: 0x02022e5c,
  battleTextBuffer3: 0x02022e6c,
  BATTLE_TEXT_SIZE: 16,

  callback1: 0x030030f0,
  mapGroup: 0x02036dfc,
  mapNumber: 0x02036dfe,
  playerX: 0x02037078,
  playerY: 0x0203707a,
  battleFlag: 0x02023e8a,
  textFlag: 0x020375c0,
} as const;

export type GBAKey =
  | 'A' | 'B' | 'START' | 'SELECT'
  | 'UP' | 'DOWN' | 'LEFT' | 'RIGHT'
  | 'L' | 'R';

export const KEYS: Record<string, GBAKey> = {
  A: 'A',
  B: 'B',
  START: 'START',
  SELECT: 'SELECT',
  UP: 'UP',
  DOWN: 'DOWN',
  LEFT: 'LEFT',
  RIGHT: 'RIGHT',
  L: 'L',
  R: 'R',
};

export const TIMEOUTS = {
  BOOT: 10_000,
  TITLE_SCREEN: 15_000,
  NEW_GAME: 30_000,
  BATTLE: 60_000,
  DIALOGUE: 20_000,
  MENU: 15_000,
  DEFAULT: 30_000,
  REAL_GAMEPLAY: 300_000,
  REAL_BOOT: 60_000,
  REAL_NEW_GAME: 120_000,
} as const;

export const FRAME_COUNTS = {
  BOOT_MIN: 300,
  TITLE_WAIT: 600,
  ONE_SECOND: 60,
  TEN_SECONDS: 600,
  THIRTY_SECONDS: 1800,
  ONE_MINUTE: 3600,
  KEY_PRESS_HOLD: 4,
  KEY_GAP: 8,
  TEXT_WAIT: 120,
  MENU_TRANSITION: 30,
} as const;

export const SCREEN_TYPES = {
  TITLE: 'title',
  OVERWORLD: 'overworld',
  BATTLE: 'battle',
  MENU: 'menu',
  DIALOGUE: 'dialogue',
  INTRO: 'intro',
} as const;

export type ScreenType = typeof SCREEN_TYPES[keyof typeof SCREEN_TYPES];

export const FRENCH_MENU_STRINGS = [
  'NOUVELLE PARTIE',
  'CONTINUER',
  'OPTIONS',
  'MYSTÈRE',
] as const;

export const KNOWN_ENGLISH_STRINGS = [
  'NEW GAME',
  'CONTINUE',
  'OPTIONS',
  'MYSTERY',
  'Press Start',
  'FIGHT',
  'BAG',
  'POKEMON',
  'RUN',
] as const;

export const FRENCH_ACCENTED_CHARS = [
  'é', 'è', 'ê', 'ë', 'à', 'â', 'ç', 'ù', 'û', 'ü', 'î', 'ï', 'ô', 'œ',
] as const;

// German umlauts, charmap slots 0xF1-0xF6 (B-211) — see helpers/charmap.ts.
export const GERMAN_UMLAUT_CHARS = ['Ä', 'Ö', 'Ü', 'ä', 'ö', 'ü'] as const;
