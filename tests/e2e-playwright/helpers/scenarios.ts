import type { EmulatorClient, GameState } from '../fixtures/emulator-client.js';
import { FRAME_COUNTS, KEYS } from './constants.js';

export interface WaitForGameStateOptions {
  maxFrames?: number;
  stepFrames?: number;
  label?: string;
}

export async function waitForGameState(
  client: EmulatorClient,
  predicate: (state: GameState) => boolean,
  options: WaitForGameStateOptions = {},
): Promise<GameState> {
  const { maxFrames = 3600, stepFrames = 60, label = 'game state' } = options;
  let elapsed = 0;

  while (elapsed < maxFrames) {
    await client.advanceFrames(stepFrames);
    elapsed += stepFrames;
    const state = await client.getState();
    if (predicate(state)) return state;
  }

  throw new Error(
    `Timeout waiting for ${label} after ${elapsed} frames (${(elapsed / 60).toFixed(1)}s)`,
  );
}

export async function waitForStableCallback(
  client: EmulatorClient,
  maxFrames = 1200,
): Promise<GameState> {
  let lastCallback = 0;
  let stableCount = 0;
  const step = 30;
  let elapsed = 0;

  while (elapsed < maxFrames) {
    await client.advanceFrames(step);
    elapsed += step;
    const state = await client.getState();
    if (state.callback1 !== 0 && state.callback1 === lastCallback) {
      stableCount++;
      if (stableCount >= 3) return state;
    } else {
      stableCount = 0;
    }
    lastCallback = state.callback1;
  }

  return client.getState();
}

export async function bootToTitle(client: EmulatorClient): Promise<void> {
  await client.fastForward(true);
  await client.advanceFrames(FRAME_COUNTS.TITLE_WAIT);
  await waitForStableCallback(client);
  await client.fastForward(false);
}

export async function startNewGame(client: EmulatorClient): Promise<void> {
  await bootToTitle(client);

  await client.fastForward(true);

  // Press START at title
  await client.pressKey(KEYS.START);
  await client.advanceFrames(FRAME_COUNTS.ONE_SECOND);

  // Press A to select "New Game" (first option)
  await client.pressKey(KEYS.A);
  await client.advanceFrames(FRAME_COUNTS.ONE_SECOND);

  // Advance through intro text
  for (let i = 0; i < 10; i++) {
    await client.pressKey(KEYS.A);
    await client.advanceFrames(FRAME_COUNTS.TEXT_WAIT);
  }

  await client.fastForward(false);
}

export async function navigateToMenu(client: EmulatorClient): Promise<void> {
  await bootToTitle(client);

  await client.fastForward(true);

  // Press START at title
  await client.pressKey(KEYS.START);
  await client.advanceFrames(FRAME_COUNTS.ONE_SECOND);

  await client.fastForward(false);
}

export async function navigateMenu(
  client: EmulatorClient,
  direction: 'UP' | 'DOWN',
  steps: number,
): Promise<void> {
  for (let i = 0; i < steps; i++) {
    await client.pressKey(KEYS[direction]);
    await client.advanceFrames(FRAME_COUNTS.MENU_TRANSITION);
  }
}

export async function advanceDialogue(
  client: EmulatorClient,
  presses = 5,
): Promise<void> {
  for (let i = 0; i < presses; i++) {
    await client.pressKey(KEYS.A);
    await client.advanceFrames(FRAME_COUNTS.TEXT_WAIT);
  }
}

export async function waitForText(
  client: EmulatorClient,
  maxFrames = 600,
): Promise<boolean> {
  const step = 30;
  let elapsed = 0;

  while (elapsed < maxFrames) {
    await client.advanceFrames(step);
    elapsed += step;
    const state = await client.getState();
    if (state.textActive) return true;
  }

  return false;
}

export async function waitForBattle(
  client: EmulatorClient,
  maxFrames = 3600,
): Promise<boolean> {
  const step = 60;
  let elapsed = 0;

  while (elapsed < maxFrames) {
    await client.advanceFrames(step);
    elapsed += step;
    const state = await client.getState();
    if (state.inBattle) return true;
  }

  return false;
}

export async function walk(
  client: EmulatorClient,
  direction: 'UP' | 'DOWN' | 'LEFT' | 'RIGHT',
  steps: number,
): Promise<void> {
  for (let i = 0; i < steps; i++) {
    await client.pressKey(KEYS[direction]);
    await client.advanceFrames(16);
  }
}

export async function navigateToBattle(client: EmulatorClient): Promise<boolean> {
  await startNewGame(client);
  await client.fastForward(true);

  // Skip through initial dialogues
  for (let i = 0; i < 20; i++) {
    await client.pressKey(KEYS.A);
    await client.advanceFrames(FRAME_COUNTS.TEXT_WAIT);
  }

  // Walk around in grass to trigger a wild battle
  for (let attempt = 0; attempt < 30; attempt++) {
    await walk(client, 'RIGHT', 3);
    await walk(client, 'LEFT', 3);
    await walk(client, 'UP', 2);
    await walk(client, 'DOWN', 2);

    const state = await client.getState();
    if (state.inBattle) {
      await client.fastForward(false);
      return true;
    }
  }

  await client.fastForward(false);
  return false;
}

export async function interactWithNPC(client: EmulatorClient): Promise<boolean> {
  await startNewGame(client);
  await client.fastForward(true);

  // Skip intro, then try talking to nearby NPCs
  for (let i = 0; i < 15; i++) {
    await client.pressKey(KEYS.A);
    await client.advanceFrames(FRAME_COUNTS.TEXT_WAIT);
  }

  // Walk to find an NPC and press A to talk
  await walk(client, 'UP', 3);
  await client.pressKey(KEYS.A);
  await client.advanceFrames(FRAME_COUNTS.TEXT_WAIT);

  const state = await client.getState();
  await client.fastForward(false);
  return state.textActive;
}
