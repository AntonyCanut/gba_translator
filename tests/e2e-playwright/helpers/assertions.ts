import { expect } from '@playwright/test';
import type { EmulatorClient, GameState, TextBuffers } from '../fixtures/emulator-client.js';
import { KNOWN_ENGLISH_STRINGS, FRENCH_ACCENTED_CHARS } from './constants.js';

export function expectFrenchText(text: string): void {
  if (!text || text.trim().length === 0) return;

  const frenchIndicators = [
    ...FRENCH_ACCENTED_CHARS,
    ' le ', ' la ', ' les ', ' de ', ' du ', ' des ', ' un ', ' une ',
    ' et ', ' est ', ' en ', ' que ', ' qui ', ' dans ', ' pour ',
    ' sur ', ' avec ', ' pas ', ' ce ', ' se ', ' au ',
  ];

  const lower = text.toLowerCase();
  const hasFrench = frenchIndicators.some((indicator) =>
    lower.includes(indicator.toLowerCase()),
  );

  if (!hasFrench && text.length > 10) {
    const hasAsciiLetters = /[a-zA-Z]{3,}/.test(text);
    if (hasAsciiLetters) {
      console.warn(`Text may not be French: "${text.substring(0, 80)}..."`);
    }
  }
}

export function expectNoEnglishText(text: string): void {
  if (!text || text.trim().length === 0) return;

  const upper = text.toUpperCase();
  for (const english of KNOWN_ENGLISH_STRINGS) {
    expect(upper, `Found English text "${english}" in: "${text.substring(0, 80)}"`).not.toContain(
      english.toUpperCase(),
    );
  }
}

export function expectAccentedChars(text: string, expectedChars: string[]): void {
  for (const char of expectedChars) {
    expect(text, `Expected accented char '${char}' in: "${text.substring(0, 80)}"`).toContain(char);
  }
}

export function expectNoCrash(state: GameState): void {
  expect(state.callback1, 'Emulator crashed (callback1 === 0)').not.toBe(0);
}

export function expectFrameCountIncreasing(before: number, after: number): void {
  expect(after, 'Frame count should increase over time').toBeGreaterThan(before);
}

export async function expectScreenType(
  client: EmulatorClient,
  expectedType: 'battle' | 'overworld' | 'dialogue',
): Promise<void> {
  const state = await client.getState();
  switch (expectedType) {
    case 'battle':
      expect(state.inBattle, 'Expected battle screen').toBe(true);
      break;
    case 'overworld':
      expect(state.inBattle, 'Expected overworld (not in battle)').toBe(false);
      break;
    case 'dialogue':
      expect(state.textActive, 'Expected dialogue/text active').toBe(true);
      break;
  }
}

export function expectTextBuffersNotEmpty(buffers: TextBuffers): void {
  const allTexts = [
    buffers.stringVar1,
    buffers.stringVar2,
    buffers.stringVar3,
    buffers.stringVar4,
    buffers.battleText1,
    buffers.battleText2,
    buffers.battleText3,
  ];

  const hasContent = allTexts.some((t) => t.trim().length > 0);
  expect(hasContent, 'At least one text buffer should have content').toBe(true);
}
