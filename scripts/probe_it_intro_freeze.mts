/**
 * probe_it_intro_freeze.mts — reproduce the Italian game-start (intro) freeze.
 *
 * Boots <rom>, starts a NEW game, walks the professor intro pressing A, and
 * after every press captures the render buffer (gStringVar4) + a screen-hash
 * BEFORE advancing frames. If advanceFrames hangs (CPU infinite loop with IRQs
 * off -> emu:runFrame never returns -> bridge timeout) we catch it and report
 * the LAST captured buffer = the string the engine froze on. We also flag a
 * stalled screen-hash as a freeze (the reliable signal per the skill).
 *
 * Run: npx tsx scripts/probe_it_intro_freeze.mts <rom>
 */
import path from 'path';
import fs from 'fs';
import crypto from 'crypto';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.ts';
import { decodePokemonText } from '../tests/e2e-playwright/helpers/charmap.js';

const ROM = path.resolve(process.argv[2] ?? 'output/roms/GenedRom-it.gba');
const OUT = '/tmp/it-intro';
fs.mkdirSync(OUT, { recursive: true });

function md5(p: string) { try { return crypto.createHash('md5').update(fs.readFileSync(p)).digest('hex'); } catch { return ''; } }

async function sv4(c: MgbaBridgeClient) {
  const raw = await c.readMemory(0x02021D18, 1000);
  const hex = Array.from(raw.slice(0, 160)).map((b) => b.toString(16).padStart(2, '0')).join(' ');
  return { text: decodePokemonText(raw).trim(), hex };
}

async function main() {
  const c = new MgbaBridgeClient();
  await c.startMgba(ROM);
  await c.advanceFrames(600);
  await c.screenshot(`${OUT}/00-title.png`);

  // Start a new game: START at title, then A to begin.
  await c.pressKey('START', 4);
  await c.advanceFrames(120);
  await c.pressKey('A', 4);
  await c.advanceFrames(120);

  let lastHash = '', same = 0, frozen = false, hung = false;
  let lastBuf = { text: '', hex: '' };
  let lastImg = '';
  for (let i = 0; i < 140; i++) {
    // Capture BEFORE advancing so a subsequent hang leaves us the last good read.
    let buf = { text: '', hex: '' };
    try { buf = await sv4(c); } catch { /* read may also hang */ }
    if (buf.text) lastBuf = buf;
    let h = '';
    try { const p = `${OUT}/_f.png`; await c.screenshot(p); h = md5(p); if (h) { fs.copyFileSync(p, `${OUT}/step-${String(i).padStart(3, '0')}.png`); lastImg = `${OUT}/step-${String(i).padStart(3, '0')}.png`; } } catch { /* */ }
    if (h && h === lastHash) same++; else { same = 0; lastHash = h; }
    if (same === 8) {
      console.error(`[${i}] SCREEN STALLED 8x; sv4="${buf.text.slice(0, 120)}"`);
      console.error(`     hex=${buf.hex}`);
    }
    if (same >= 24) { frozen = true; console.error(`[${i}] FROZEN (screen hash stable ${same}x)`); break; }

    try {
      await c.pressKey('A', 4);
      await c.advanceFrames(40);
    } catch (e) {
      hung = true;
      console.error(`[${i}] HANG on advanceFrames: ${String(e)}`);
      console.error(`     last sv4="${lastBuf.text}"`);
      console.error(`     last hex=${lastBuf.hex}`);
      break;
    }
  }

  console.error(`[probe] frozen=${frozen} hung=${hung}`);
  console.error(`[probe] lastBuf.text="${lastBuf.text}"`);
  console.error(`[probe] lastBuf.hex=${lastBuf.hex}`);
  console.error(`[probe] lastImg=${lastImg}`);
  console.log(JSON.stringify({ rom: ROM, frozen, hung, lastText: lastBuf.text, lastHex: lastBuf.hex, lastImg }));
  try { await c.stop(); } catch { /* */ }
  process.exit(frozen || hung ? 1 : 0);
}
main().catch((e) => { console.error('FATAL', e); process.exit(3); });
