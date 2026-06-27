/**
 * probe_it_intro_freeze.mts — reproduce the Italian game-start (intro) freeze.
 *
 * Boots <rom>, starts a NEW game, walks the professor intro pressing A. For each
 * press it advances frames in SMALL increments, reading the render buffer
 * (gStringVar4) + a screen-hash before EACH micro-advance, so when the CPU
 * locks (infinite GetStringWidth -> emu:runFrame never returns -> bridge
 * timeout) the LAST captured buffer is the string the engine froze on.
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
  // Read every named string buffer + the wider message area and report each.
  const parts: string[] = [];
  for (const [name, addr, len] of [
    ['gSV1', 0x02021d18, 16], ['gSV2', 0x02021d28, 16], ['gSV3', 0x02021d38, 16], ['gSV4', 0x02021d48, 1000],
    ['gDisp', 0x02021fc0, 1000],
  ] as const) {
    try {
      const raw = await c.readMemory(addr as number, len as number);
      const t = decodePokemonText(raw).trim();
      if (t.length > 1) parts.push(`${name}="${t.replace(/\n/g, '/').slice(0, 80)}"`);
    } catch { /* */ }
  }
  const raw = await c.readMemory(0x02021d48, 200);
  const hex = Array.from(raw.slice(0, 120)).map((b) => b.toString(16).padStart(2, '0')).join(' ');
  return { text: parts.join('  '), hex };
}

async function main() {
  const c = new MgbaBridgeClient();
  await c.startMgba(ROM);
  await c.advanceFrames(600);

  await c.pressKey('START', 4);
  await c.advanceFrames(120);
  await c.pressKey('A', 4);
  await c.advanceFrames(120);

  let lastHash = '', same = 0, frozen = false, hung = false;
  let lastBuf = { text: '', hex: '' };
  const distinct: string[] = [];
  for (let i = 0; i < 160; i++) {
    await c.pressKey('A', 4);
    if (i % 4 === 3) { await c.pressKey('START', 4); } // confirm the naming keyboard (START == OK)
    // Micro-advance so the buffer + screenshot are sampled right up to the hang.
    for (let m = 0; m < 8; m++) {
      let buf = { text: '', hex: '' };
      try { buf = await sv4(c); } catch { /* */ }
      if (buf.text && buf.text.length > 2) {
        lastBuf = buf;
        if (!distinct.includes(buf.text)) { distinct.push(buf.text); console.error(`[${i}.${m}] sv4="${buf.text.replace(/\n/g, ' / ').slice(0, 110)}"`); }
      }
      try { await c.screenshot(`${OUT}/frame-${String(i).padStart(3, '0')}-${m}.png`); } catch { /* */ }
      try {
        await c.advanceFrames(5);
      } catch (e) {
        hung = true;
        console.error(`[${i}.${m}] HANG on advanceFrames: ${String(e)}`);
        console.error(`     FROZEN STRING sv4="${lastBuf.text}"`);
        console.error(`     hex=${lastBuf.hex}`);
        break;
      }
    }
    if (hung) break;
    let h = '';
    try { const p = `${OUT}/_f.png`; await c.screenshot(p); h = md5(p); if (h) fs.copyFileSync(p, `${OUT}/step-${String(i).padStart(3, '0')}.png`); } catch { /* */ }
    if (h && h === lastHash) same++; else { same = 0; lastHash = h; }
    if (same >= 24) { frozen = true; console.error(`[${i}] FROZEN (screen stable ${same}x); sv4="${lastBuf.text}"`); break; }
  }

  console.error(`[probe] frozen=${frozen} hung=${hung}`);
  console.error(`[probe] FROZEN STRING="${lastBuf.text}"`);
  console.error(`[probe] hex=${lastBuf.hex}`);
  console.log(JSON.stringify({ rom: ROM, frozen, hung, frozenString: lastBuf.text, frozenHex: lastBuf.hex }));
  try { await c.stop(); } catch { /* */ }
  process.exit(frozen || hung ? 1 : 0);
}
main().catch((e) => { console.error('FATAL', e); process.exit(3); });
