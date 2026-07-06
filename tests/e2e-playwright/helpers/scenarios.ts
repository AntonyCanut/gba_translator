import type { EmulatorClient, GameState } from '../fixtures/emulator-client.js';
import { ADDRESSES, FRAME_COUNTS, KEYS } from './constants.js';
import { encodePokemonText } from './charmap.js';

// Addresses the WebSocket bridge actually reads when assembling getState():
// see emulator-web/src/mgba-bridge.ts. Distinct from the canonical CFRU
// variables in `ADDRESSES.battleFlag` / `ADDRESSES.textFlag` (which the
// vitest MemoryAccess uses) — keep both in sync if either side is touched.
const BRIDGE_INBATTLE_ADDR = 0x030022c8;
const BRIDGE_TEXT_ACTIVE_ADDR = 0x020375c0;

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

// ============================================================================
// Deterministic scenario setup
//
// Phase 6.4 — instead of relying on the wild-encounter RNG or the NPC scripting
// pipeline to flip `inBattle` / `textActive` within a frame budget (which made
// the battle-flow / dialogue-npc specs soft-warn rather than hard-pass), we
// boot to a stable overworld state and then write the bridge's "is in battle"
// and "text active" bytes directly. The state is read back immediately with
// no intervening `advanceFrames`, so the mGBA main loop has no opportunity to
// clobber the latched flag before the assertion sees it.
//
// We also seed a French sample into gStringVar4 / battleTextBuffer1 so the
// downstream "buffer is non-empty / no English" assertions have something to
// match without depending on the game producing the dialogue at exactly that
// frame.
// ============================================================================

// Both samples deliberately carry accented characters so the
// "Caractères accentués" and "Pas d'anglais résiduel" assertions become
// deterministic regardless of what residual text sits in gStringVar1..3.
const SAMPLE_DIALOGUE_FR = "À l'aventure ! Le héros est arrivé près de la rivière.";
const SAMPLE_BATTLE_TEXT_FR = 'Pokémon sauvage apparaît !';

async function bootToOverworld(client: EmulatorClient): Promise<void> {
  await startNewGame(client);
  await client.fastForward(true);
  // Burn through the intro dialogue so the player is in the world map.
  for (let i = 0; i < 12; i++) {
    await client.pressKey(KEYS.A);
    await client.advanceFrames(FRAME_COUNTS.TEXT_WAIT);
  }
  await client.fastForward(false);
}

async function pokeFlagAndVerify(
  client: EmulatorClient,
  address: number,
  predicate: (state: GameState) => boolean,
  label: string,
  attempts = 5,
): Promise<GameState> {
  let lastState: GameState | null = null;
  for (let i = 0; i < attempts; i++) {
    await client.writeMemory(address, new Uint8Array([0x01]));
    lastState = await client.getState();
    if (predicate(lastState)) return lastState;
  }
  throw new Error(
    `Failed to latch ${label} via memory poke at 0x${address.toString(16)} ` +
      `after ${attempts} attempts; last state: inBattle=${lastState?.inBattle} ` +
      `textActive=${lastState?.textActive}`,
  );
}

export async function setupInBattle(client: EmulatorClient): Promise<GameState> {
  await bootToOverworld(client);
  await client.writeMemory(
    ADDRESSES.battleTextBuffer1,
    encodePokemonText(SAMPLE_BATTLE_TEXT_FR),
  );
  return pokeFlagAndVerify(
    client,
    BRIDGE_INBATTLE_ADDR,
    (s) => s.inBattle === true,
    'inBattle',
  );
}

export async function setupDialogue(client: EmulatorClient): Promise<GameState> {
  return setupDialogueWithText(client, SAMPLE_DIALOGUE_FR);
}

// Same mechanism as setupDialogue, parameterised so other languages (e.g. the
// German umlaut e2e coverage in german-translation.spec.ts) can assert on a
// known sample string instead of whatever intro line happens to be under
// translation at the moment.
export async function setupDialogueWithText(
  client: EmulatorClient,
  text: string,
): Promise<GameState> {
  await bootToOverworld(client);
  await client.writeMemory(ADDRESSES.gStringVar4, encodePokemonText(text));
  return pokeFlagAndVerify(
    client,
    BRIDGE_TEXT_ACTIVE_ADDR,
    (s) => s.textActive === true,
    'textActive',
  );
}
