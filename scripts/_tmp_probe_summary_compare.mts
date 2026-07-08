import fs from 'fs';
import path from 'path';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.js';

const OUT_DIR = path.resolve('output/proofs/hp-vram-compare');
fs.mkdirSync(OUT_DIR, { recursive: true });

async function shot(client: MgbaBridgeClient, name: string): Promise<void> {
  try {
    await client.screenshot(path.join(OUT_DIR, `${name}.png`));
    console.error(`[shot] ${name}`);
  } catch (e) {
    console.error(`[shot] ${name} failed: ${String(e)}`);
  }
}

async function run(romPath: string, stateSlot: number, tag: string): Promise<void> {
  const client = new MgbaBridgeClient();
  console.error(`[probe] booting ${romPath}`);
  await client.startMgba(path.resolve(romPath));
  await client.advanceFrames(600);
  await client.loadState(stateSlot);
  await client.advanceFrames(30);
  await shot(client, `${tag}-00-state`);

  for (let i = 0; i < 3; i++) {
    await client.pressKey('B', 4);
    await client.advanceFrames(20);
  }
  await client.pressKey('START', 4);
  await client.advanceFrames(40);
  await shot(client, `${tag}-01-startmenu`);
  await client.pressKey('A', 4);
  await client.advanceFrames(90);
  await shot(client, `${tag}-02-party`);
  await client.pressKey('A', 4);
  await client.advanceFrames(30);
  await shot(client, `${tag}-03-party-context`);
  await client.pressKey('A', 4);
  await client.advanceFrames(90);
  await shot(client, `${tag}-04-summary`);
  await client.pressKey('RIGHT', 4);
  await client.advanceFrames(60);
  await shot(client, `${tag}-05-summary-skills`);

  await client.stop();
}

async function main(): Promise<void> {
  const target = process.argv[2] ?? 'fr';
  if (target === 'fr') {
    await run('output/roms/GenedRom-fr.gba', 2, 'fr');
  } else if (target === 'en') {
    await run('input/roms/englishrom.gba', 3, 'en');
  } else {
    throw new Error(`unknown target ${target}`);
  }
  console.error('[probe] done');
}

main().catch((e) => {
  console.error('[probe] FATAL', e);
  process.exit(1);
});
