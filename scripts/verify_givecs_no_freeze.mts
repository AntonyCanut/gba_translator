/**
 * verify_givecs_no_freeze.mts — deterministic give-CS freeze check from the
 * .ss9 savestate (taken just before the post-Zeph cutscene, so no RNG battle).
 *
 * It loads the savestate into <rom>, mashes A through the give-CS cutscene and
 * judges a GENUINE freeze by SCREEN HASH: the rendered frame staying pixel
 * identical for many consecutive A-presses. (Player map/pos alone is NOT a
 * freeze signal — you stand still during the whole conversation, so a
 * pos-based check reports "stuck" for a perfectly healthy multi-box dialogue.
 * The give-CS bug is the field-move description word-wrap spinning forever:
 * the screen genuinely stops updating.)
 *
 * Exit code: 0 = reached the give-CS box and never froze, 1 = genuine freeze,
 * 2 = inconclusive (never reached the give-CS map — e.g. savestate/ROM drift).
 *
 * Run: MGBA_PATH=/opt/homebrew/bin/mgba \
 *   emulator-web/node_modules/.bin/tsx scripts/verify_givecs_no_freeze.mts <rom> [slot]
 */
import path from 'path';
import fs from 'fs';
import crypto from 'crypto';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.ts';

const ROM = path.resolve(process.argv[2] ?? 'output/roms/GenedRom-fr.gba');
const SLOT = Number(process.argv[3] ?? 9);
const GIVE_CS_MAP = '46.0';        // field map where the CS is handed over
const FREEZE_PRESSES = 45;          // identical screen for this many A-presses = freeze
const MAX_PRESSES = 240;

async function pos(c: MgbaBridgeClient) {
  const s = await c.getState();
  return `${s.mapGroup}.${s.mapNumber}:${s.playerX},${s.playerY}`;
}
function md5(p: string) { try { return crypto.createHash('md5').update(fs.readFileSync(p)).digest('hex'); } catch { return ''; } }

async function main() {
  const c = new MgbaBridgeClient();
  await c.startMgba(ROM);
  await c.advanceFrames(120);
  await c.loadState(SLOT);
  await c.advanceFrames(30);

  let lastHash = '', same = 0, reached = false, frozen = false;
  for (let i = 0; i < MAX_PRESSES; i++) {
    await c.pressKey('A', 4);
    await c.advanceFrames(30);
    const p = await pos(c);
    if (p.startsWith(GIVE_CS_MAP + ':')) reached = true;
    let h = '';
    try { await c.screenshot('/tmp/_givecs_vf.png'); h = md5('/tmp/_givecs_vf.png'); } catch { /* */ }
    if (h && h === lastHash) same++; else { same = 0; lastHash = h; }
    if (reached && same >= FREEZE_PRESSES) { frozen = true; break; }
  }

  const verdict = frozen ? 1 : (reached ? 0 : 2);
  console.error(`reached=${reached} frozen=${frozen} pos=${await pos(c)}`);
  console.log(JSON.stringify({ rom: ROM, slot: SLOT, reached, frozen, verdict }));
  await c.stop();
  process.exit(verdict);
}
main().catch((e) => { console.error('ERR', e); process.exit(3); });
