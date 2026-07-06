/**
 * verify_selection_sprite.mts — Boot the patched FR ROM fresh and confirm the
 * naming-keyboard help panel now renders in French (ticket F-109).
 *
 * Run: npx tsx scripts/verify_selection_sprite.mts [rom]
 */
import fs from 'fs';
import path from 'path';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.js';

const ROM = path.resolve(process.argv[2] ?? 'output/roms/GenedRom-fr.gba');
const OUT_DIR = path.resolve('output/proofs/naming-vram');

async function main(): Promise<void> {
  const client = new MgbaBridgeClient();
  await client.startMgba(ROM);
  await client.advanceFrames(600);
  await client.pressKey('START', 4);
  await client.advanceFrames(60);
  await client.pressKey('A', 4);
  await client.advanceFrames(120);
  for (let i = 0; i < 18; i++) {
    await client.pressKey('A', 4);
    await client.advanceFrames(60);
  }
  await client.screenshot(path.join(OUT_DIR, '40-verify-fr-keyboard.png'));
  console.error('[verify] screenshot saved');
  await client.stop();
}

main().catch((e) => {
  console.error('[probe] FATAL', e);
  process.exit(1);
});
