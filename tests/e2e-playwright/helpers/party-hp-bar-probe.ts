import path from 'path';
import { MgbaBridgeClient } from '../../../emulator-web/src/mgba-bridge.js';

const KEY_PRESS_FRAMES = 4;
const INITIAL_BOOT_FRAMES = 300;
const CONTINUE_SEQUENCE_FRAMES = [60, 60, 120, 120] as const;
const MAIN_MENU_FRAMES = 60;
const MENU_CURSOR_FRAMES = 20;
const PARTY_RENDER_FRAMES = 120;

async function capturePartyScreen(
  client: MgbaBridgeClient,
  screenshotPath: string,
): Promise<{ playerX: number; playerY: number }> {
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

  // Main menu → Pokémon (second entry).
  await client.pressKey('START', KEY_PRESS_FRAMES);
  await client.advanceFrames(MAIN_MENU_FRAMES);
  await client.pressKey('DOWN', KEY_PRESS_FRAMES);
  await client.advanceFrames(MENU_CURSOR_FRAMES);
  await client.pressKey('A', KEY_PRESS_FRAMES);
  await client.advanceFrames(PARTY_RENDER_FRAMES);
  await client.screenshot(screenshotPath);

  return { playerX, playerY };
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
  const state = await withBridge(romPath, (client) => (
    capturePartyScreen(client, screenshotPath)
  ));
  console.log(JSON.stringify(state));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
