/**
 * probe_load_givecs.mts — boot the FR ROM with the post-Zeph save and report
 * WHERE the save lands (map/pos) and whether a battle blocks the path to the
 * give-CS hillbilly. Mashes A and walks DOWN; no memory cheats (they corrupt
 * this Unbound build). Pure observation: map/pos + screenshot-static detection.
 *
 * Run: emulator-web/node_modules/.bin/tsx scripts/probe_load_givecs.mts <romPath>
 */
import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.ts';

const ROM = path.resolve(process.argv[2] ?? '/tmp/givecs_scratch/game.gba');
const OUT = path.resolve('output/proofs/give-cs-load');
fs.mkdirSync(OUT, { recursive: true });

function u32(b: Uint8Array): number { return (b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24)) >>> 0; }
async function sb1(c: MgbaBridgeClient): Promise<number> { return u32(await c.readMemory(0x03005008, 4)); }
async function pos(c: MgbaBridgeClient): Promise<string> {
  const st = await c.getState();
  return `${st.mapGroup}.${st.mapNumber}:${st.playerX},${st.playerY}`;
}
function md5(p: string): string { try { return crypto.createHash('md5').update(fs.readFileSync(p)).digest('hex'); } catch { return ''; } }

async function main(): Promise<void> {
  const c = new MgbaBridgeClient();
  await c.startMgba(ROM);
  await c.advanceFrames(600);
  // Title -> Continue
  await c.pressKey('START', 4); await c.advanceFrames(120);
  await c.pressKey('A', 4); await c.advanceFrames(120);
  await c.pressKey('A', 4); await c.advanceFrames(180);
  const p0 = await pos(c);
  console.error(`[loaded] pos=${p0} sb1=0x${(await sb1(c)).toString(16)}`);
  await c.screenshot(path.join(OUT, '00-loaded.png'));

  let lastPos = p0, lastChange = 0, lastHash = '', same = 0;
  for (let i = 0; i < 400; i++) {
    await c.pressKey('A', 4); await c.advanceFrames(30);
    if (i % 4 === 3) { await c.pressKey('DOWN', 6); await c.advanceFrames(12); }
    const p = await pos(c);
    if (p !== lastPos) { lastPos = p; lastChange = i; }
    const sp = path.join(OUT, `f-${String(i).padStart(3, '0')}.png`);
    await c.screenshot(sp);
    const h = md5(sp);
    if (h && h === lastHash) same++; else { same = 0; lastHash = h; }
    if (i % 8 !== 0) { try { fs.unlinkSync(sp); } catch { /* */ } }
    if (i % 10 === 0) console.error(`[i${i}] pos=${p} same=${same} sinceMove=${i - lastChange}`);
    const ptr = await sb1(c);
    if (!(ptr >= 0x02000000 && ptr < 0x03000000)) { console.error(`[i${i}] RESET sb1=0x${ptr.toString(16)}`); await c.screenshot(path.join(OUT, `RESET-${i}.png`)); break; }
    if (same >= 50 && i - lastChange >= 50) { console.error(`[i${i}] FREEZE/STUCK pos=${p}`); await c.screenshot(path.join(OUT, `STUCK-${i}.png`)); break; }
  }
  console.error(`[final] pos=${await pos(c)}`);
  await c.screenshot(path.join(OUT, 'zz-final.png'));
  await c.stop();
}
main().catch((e) => { console.error('ERR', e); process.exit(1); });
