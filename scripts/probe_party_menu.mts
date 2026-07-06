/**
 * probe_party_menu.mts — Screenshot the party (START → Pokémon) screen of an
 * arbitrary ROM. Purpose-built for the "patch ROM → verify in-game" loop used to
 * chase the party-menu « Lv » → « N. » graphic (issue #48 / B-234).
 *
 * Boots the ROM, restores savestate slot 2 (overworld with a Pokémon in the
 * party), navigates START → Pokémon, and screenshots the party list.
 *
 * IMPORTANT: `loadStateSlot(2)` loads `<rom-basename>.ss2`. When probing a
 * patched copy at /tmp/x.gba, first copy the savestate next to it:
 *     cp output/roms/GenedRom-fr.ss2 /tmp/x.ss2
 * Otherwise the game boots cold and the shot is a blank/white screen.
 *
 * Run:  npm i -D tsx
 *       MGBA_PATH=/opt/homebrew/bin/mgba npx tsx scripts/probe_party_menu.mts [rom] [out.png]
 */
import path from 'path';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.js';

const ROM = path.resolve(process.argv[2] ?? 'output/roms/GenedRom-fr.gba');
const OUT = process.argv[3] ?? '/tmp/party_menu.png';

async function main(): Promise<void> {
  const c = new MgbaBridgeClient();
  await c.startMgba(ROM);
  await c.advanceFrames(600);
  await c.loadState(2);
  await c.advanceFrames(30);
  // close any open UI, then open the START menu (Pokémon is the default entry)
  for (let i = 0; i < 3; i++) { await c.pressKey('B', 4); await c.advanceFrames(20); }
  await c.pressKey('START', 4); await c.advanceFrames(40);
  await c.pressKey('A', 4); await c.advanceFrames(90);
  await c.screenshot(OUT);
  console.error(`[probe] party shot -> ${OUT}`);
  await c.stop();
}

main().catch((e) => { console.error('[probe] FATAL', e); process.exit(1); });
