/**
 * probe_dexnav_find_state.mts — Check every existing savestate slot on the FR
 * ROM to find one where the DexNav key item has been unlocked (a "DexNav"
 * entry appears in the START menu), and where the player stands on an
 * outdoor wild-encounter tile.
 *
 * Run:  npx tsx scripts/probe_dexnav_find_state.mts
 */
import fs from 'fs';
import path from 'path';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.js';

const ROM = path.resolve('output/roms/GenedRom-fr.gba');
const OUT_DIR = path.resolve('output/proofs/dexnav-find');
fs.mkdirSync(OUT_DIR, { recursive: true });

const SLOTS = [1, 2, 3, 8, 9];

async function main(): Promise<void> {
  const client = new MgbaBridgeClient();
  console.error(`[probe] booting ${ROM}`);
  await client.startMgba(ROM);
  await client.advanceFrames(600);

  for (const slot of SLOTS) {
    try {
      await client.loadState(slot);
      await client.advanceFrames(30);
      // Close any open UI first
      for (let i = 0; i < 3; i++) {
        await client.pressKey('B', 4);
        await client.advanceFrames(20);
      }
      await client.screenshot(path.join(OUT_DIR, `slot${slot}-idle.png`));
      await client.pressKey('START', 4);
      await client.advanceFrames(40);
      await client.screenshot(path.join(OUT_DIR, `slot${slot}-startmenu.png`));
      console.error(`[probe] slot ${slot} done`);
      // Back out before trying next slot
      await client.pressKey('B', 4);
      await client.advanceFrames(20);
    } catch (e) {
      console.error(`[probe] slot ${slot} FAILED: ${String(e)}`);
    }
  }

  await client.stop();
  console.error('[probe] done');
}

main().catch((e) => {
  console.error('[probe] FATAL', e);
  process.exit(1);
});
