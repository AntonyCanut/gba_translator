import fs from 'fs';
import path from 'path';
import { PNG } from 'pngjs';
import { MgbaBridgeClient } from '../../../emulator-web/src/mgba-bridge.js';

const KEY_PRESS_FRAMES = 4;
const INITIAL_BOOT_FRAMES = 300;
const CONTINUE_SEQUENCE_FRAMES = [60, 60, 120, 120] as const;
const MAIN_MENU_FRAMES = 60;
const MENU_CURSOR_FRAMES = 20;
const PARTY_RENDER_FRAMES = 120;
const MAX_MAIN_MENU_ENTRIES = 8;

function haveIdenticalPixels(actual: Buffer, expected: Buffer): boolean {
  const actualPng = PNG.sync.read(actual);
  const expectedPng = PNG.sync.read(expected);

  return actualPng.width === expectedPng.width
    && actualPng.height === expectedPng.height
    && actualPng.data.equals(expectedPng.data);
}

async function findMatchingMenuScreen(
  client: MgbaBridgeClient,
  screenshotPath: string,
  expectedScreenPath: string,
): Promise<number> {
  const expectedScreen = fs.readFileSync(expectedScreenPath);
  await client.saveState(1);

  for (let index = 0; index < MAX_MAIN_MENU_ENTRIES; index++) {
    if (index > 0) {
      await client.loadState(1);
      await client.advanceFrames(MENU_CURSOR_FRAMES);
    }

    for (let cursorMove = 0; cursorMove < index; cursorMove++) {
      await client.pressKey('DOWN', KEY_PRESS_FRAMES);
      await client.advanceFrames(MENU_CURSOR_FRAMES);
    }

    await client.pressKey('A', KEY_PRESS_FRAMES);
    await client.advanceFrames(PARTY_RENDER_FRAMES);

    const candidatePath = `${screenshotPath}.menu-${index}.png`;
    await client.screenshot(candidatePath);
    const candidateScreen = fs.readFileSync(candidatePath);
    const matchesExpectedScreen = haveIdenticalPixels(candidateScreen, expectedScreen);

    if (matchesExpectedScreen) {
      fs.renameSync(candidatePath, screenshotPath);
      return index + 1;
    }

    fs.rmSync(candidatePath, { force: true });
  }

  throw new Error(
    `Écran Pokémon introuvable après ${MAX_MAIN_MENU_ENTRIES} entrées du menu`,
  );
}

async function capturePartyScreen(
  client: MgbaBridgeClient,
  screenshotPath: string,
  expectedScreenPath: string,
): Promise<{ playerX: number; playerY: number; searchedMenuEntries: number }> {
  await client.advanceFrames(INITIAL_BOOT_FRAMES);

  // Title → Continue → overworld, using the battery save adjacent to the ROM.
  for (const frames of CONTINUE_SEQUENCE_FRAMES) {
    await client.pressKey('A', KEY_PRESS_FRAMES);
    await client.advanceFrames(frames);
  }

  const overworld = await client.getState();
  const playerX = Number(overworld.playerX);
  const playerY = Number(overworld.playerY);
  if (playerX <= 0 || playerY <= 0) {
    throw new Error(`La save n'a pas chargé le joueur (${playerX}, ${playerY})`);
  }

  // Explore the main menu until the rendered framebuffer matches the party screen.
  await client.pressKey('START', KEY_PRESS_FRAMES);
  await client.advanceFrames(MAIN_MENU_FRAMES);
  const searchedMenuEntries = await findMatchingMenuScreen(
    client,
    screenshotPath,
    expectedScreenPath,
  );

  return { playerX, playerY, searchedMenuEntries };
}

async function withBridge<T>(
  romPath: string,
  run: (client: MgbaBridgeClient) => Promise<T>,
  attempts = 3,
): Promise<T> {
  let lastError: unknown;

  for (let attempt = 1; attempt <= attempts; attempt++) {
    const client = new MgbaBridgeClient();
    try {
      await client.startMgba(romPath);
      return await run(client);
    } catch (error) {
      lastError = error;
    } finally {
      await client.stop();
    }

    if (attempt < attempts) {
      await new Promise((resolve) => setTimeout(resolve, 1_000));
    }
  }

  throw lastError instanceof Error ? lastError : new Error(String(lastError));
}

async function main(): Promise<void> {
  const romPath = path.resolve(process.argv[2]);
  const screenshotPath = path.resolve(process.argv[3]);
  const expectedScreenPath = path.resolve(process.argv[4]);
  const state = await withBridge(romPath, (client) => (
    capturePartyScreen(client, screenshotPath, expectedScreenPath)
  ));
  console.log(JSON.stringify(state));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
