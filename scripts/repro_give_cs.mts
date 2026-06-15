/**
 * repro_give_cs.mts — deterministic reproduction of the post-Zeph "give CS"
 * sequence, robust to this Unbound build where the textActive/inBattle/callback
 * RAM flags read by getState are NOT valid (verified: a visible "Sbire: Vite !"
 * box reports textActive=false). Only player map/pos (via gSaveBlock1Ptr) is
 * trustworthy.
 *
 * Strategy: mash A every iteration to advance ALL dialogue; rig every battle
 * deterministically each iteration (pin player battler HP to max, zero opponent
 * battler HP) so the underleveled team always wins regardless of move immunity;
 * step DOWN periodically to make overworld progress. Judge a FREEZE by: the
 * player map/pos never changes for a long stretch of A-presses AND the screen
 * stays identical — i.e. the dialog never advances and control never returns.
 *
 * Run: npx tsx scripts/repro_give_cs.mts <romPath> <tag>
 */
import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.js';

const ROM = path.resolve(process.argv[2] ?? 'output/roms/GenedRom-fr.gba');
const TAG = process.argv[3] ?? 'gcs';
const OUT_DIR = path.resolve('output/proofs/give-cs');
fs.mkdirSync(OUT_DIR, { recursive: true });

const GBATTLEMONS = 0x02023c0c - 0x28; // hp@0x28 maxHP@0x2A stride 0x58
const STRIDE = 0x58;

function u32(b: Uint8Array): number { return (b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24)) >>> 0; }
function u16(b: Uint8Array, o = 0): number { return (b[o] | (b[o + 1] << 8)); }
function u16le(n: number): Uint8Array { return new Uint8Array([n & 0xff, (n >> 8) & 0xff]); }
async function sb1(c: MgbaBridgeClient): Promise<number> { return u32(await c.readMemory(0x03005008, 4)); }

async function shot(c: MgbaBridgeClient, n: string): Promise<string> {
  const p = path.join(OUT_DIR, `${TAG}-${n}.png`);
  try { await c.screenshot(p); } catch { /* */ }
  return p;
}
function hashFile(p: string): string {
  try { return crypto.createHash('md5').update(fs.readFileSync(p)).digest('hex'); } catch { return ''; }
}

async function rigBattle(c: MgbaBridgeClient): Promise<void> {
  for (let i = 0; i < 4; i++) {
    const base = GBATTLEMONS + i * STRIDE;
    const cur = u16(await c.readMemory(base + 0x28, 2));
    const max = u16(await c.readMemory(base + 0x2a, 2));
    if (max === 0 || max > 2000) continue;
    if (i % 2 === 0) { if (cur !== max) await c.writeMemory(base + 0x28, u16le(max)); }
    else { if (cur !== 0) await c.writeMemory(base + 0x28, u16le(0)); }
  }
}

async function pos(c: MgbaBridgeClient): Promise<string> {
  const st = await c.getState();
  return `${st.mapGroup}.${st.mapNumber}:${st.playerX},${st.playerY}`;
}

async function main(): Promise<void> {
  const c = new MgbaBridgeClient();
  await c.startMgba(ROM);
  await c.advanceFrames(600);
  await c.pressKey('START', 4); await c.advanceFrames(120);
  await c.pressKey('A', 4); await c.advanceFrames(180);
  await c.pressKey('A', 4); await c.advanceFrames(200);

  console.error(`[start] ${await pos(c)}`);
  await shot(c, '00-loaded');

  let reset = false, freeze = false;
  let lastPos = await pos(c);
  let posChangeIter = 0;
  let lastHash = '';
  let sameScreen = 0;
  const visited = new Set<string>([lastPos]);

  for (let i = 0; i < 1600; i++) {
    const ptr = await sb1(c);
    if (!(ptr >= 0x02000000 && ptr < 0x03000000)) { reset = true; console.error(`[i${i}] RESET sb1=0x${ptr.toString(16)}`); await shot(c, `RESET-${i}`); break; }

    await rigBattle(c);
    await c.pressKey('A', 4); await c.advanceFrames(34);
    if (i % 5 === 4) { await c.pressKey('DOWN', 4); await c.advanceFrames(14); }

    const p = await pos(c);
    if (p !== lastPos) { lastPos = p; posChangeIter = i; visited.add(p); }

    const sp = await shot(c, `f-${String(i).padStart(4, '0')}`);
    const h = hashFile(sp);
    if (h && h === lastHash) sameScreen++; else { sameScreen = 0; lastHash = h; }
    // delete non-milestone frames to avoid disk spam
    if (i % 8 !== 0) { try { fs.unlinkSync(sp); } catch { /* */ } }

    if (i % 20 === 0) console.error(`[i${i}] ${p} sameScreen=${sameScreen} sincePosChange=${i - posChangeIter}`);

    // FREEZE: screen identical for a long time AND no positional progress, while
    // we are continuously pressing A. (Battles change the screen each turn, so a
    // truly static screen for this long = a hung dialog / soft-lock.)
    if (sameScreen >= 60 && i - posChangeIter >= 60) {
      freeze = true;
      console.error(`[i${i}] !!! FREEZE: screen static ${sameScreen} frames, no pos change ${i - posChangeIter}, at ${p}`);
      await shot(c, `FREEZE-${i}`); break;
    }
  }

  await shot(c, 'zz-final');
  console.error(`[done] ${await pos(c)} reset=${reset} freeze=${freeze} distinctTiles=${visited.size}`);
  console.log(JSON.stringify({ rom: ROM, tag: TAG, reset, freeze, visited: [...visited] }));
  await c.stop();
}

main().catch((e) => { console.error(e); process.exit(1); });
