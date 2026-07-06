/**
 * probe_startmenu.mts — open the START menu and screenshot it.
 * Run: npx tsx scripts/probe_startmenu.mts <romPath> <slot>
 */
import fs from 'fs';
import path from 'path';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.js';

const ROM = path.resolve(process.argv[2] ?? 'output/roms/GenedRom-fr.gba');
const SLOT = parseInt(process.argv[3] ?? '1');
const OUT = path.resolve('output/proofs/startmenu');
fs.mkdirSync(OUT, { recursive: true });

async function main(): Promise<void> {
  const c = new MgbaBridgeClient();
  await c.startMgba(ROM);
  await c.advanceFrames(300);
  await c.loadState(SLOT);
  await c.advanceFrames(30);
  const st = await c.getState();
  console.error(`[loaded slot ${SLOT}] map=${st.mapGroup}.${st.mapNumber} pos=${st.playerX},${st.playerY} battle=${st.inBattle}`);
  await c.screenshot(path.join(OUT, `slot${SLOT}-overworld.png`));
  // clear any active dialogue with B presses (B never opens a menu)
  if (st.textActive) {
    for (let i = 0; i < 8; i++) { await c.pressKey('B', 4); await c.advanceFrames(30); }
    const st2 = await c.getState();
    console.error(`[after B] textActive=${st2.textActive}`);
  }
  // open START menu
  await c.pressKey('START', 4);
  await c.advanceFrames(40);
  await c.screenshot(path.join(OUT, `slot${SLOT}-startmenu.png`));
  await c.advanceFrames(20);
  await c.screenshot(path.join(OUT, `slot${SLOT}-startmenu-2.png`));
  console.error('done');
  await c.stop();
}
main().catch((e) => { console.error(e); process.exit(1); });
