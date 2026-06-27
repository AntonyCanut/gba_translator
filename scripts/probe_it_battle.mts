/**
 * probe_it_battle.mts — load the IT ROM's battery save (Continue), find a wild
 * battle, and win it, proving battle text renders in Italian and the battle does
 * not freeze. Detects battles via the battle-text buffers (the inBattle flag is
 * unreliable on this harness) and a screen-hash freeze guard.
 *
 * Run: npx tsx scripts/probe_it_battle.mts [rom]
 */
import path from 'path';
import fs from 'fs';
import crypto from 'crypto';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.ts';
import { decodePokemonText } from '../tests/e2e-playwright/helpers/charmap.js';

const ROM = path.resolve(process.argv[2] ?? 'output/roms/GenedRom-it.gba');
const OUT = '/tmp/it-battle';
fs.rmSync(OUT, { recursive: true, force: true });
fs.mkdirSync(OUT, { recursive: true });

const BT = [0x02022f58, 0x02022fd8, 0x02023058];
const SV4 = 0x02021d48;
function md5(p: string) { try { return crypto.createHash('md5').update(fs.readFileSync(p)).digest('hex'); } catch { return ''; } }

async function readTxt(c: MgbaBridgeClient, addr: number, len = 200): Promise<string> {
  try { return decodePokemonText(await c.readMemory(addr, len)).trim(); } catch { return ''; }
}
async function battleText(c: MgbaBridgeClient): Promise<string> {
  const parts: string[] = [];
  for (const a of BT) { const t = await readTxt(c, a, 120); if (t.length > 2) parts.push(t); }
  const s = await readTxt(c, SV4, 200); if (s.length > 2) parts.push(s);
  return parts.join(' | ');
}
// Heuristic: are we in a battle? Look for the FIGHT/RUN menu or combat verbs.
function looksLikeBattle(t: string): boolean {
  return /Lotta|Fuggi|Borsa|selvati|usa |è apparso|appare|nemic|PS |Punti|in fuga|guadagna|Punti Esp/i.test(t);
}

const seen = new Set<string>();
const englishHits: string[] = [];
function logTxt(stage: string, t: string) {
  if (!t || seen.has(t)) return;
  seen.add(t);
  const en = /\b(FIGHT|RUN|BAG|fainted|appeared|used|wild|Fight|the foe)\b/.test(t);
  if (en) englishHits.push(t);
  console.error(`  [${stage}] ${t.replace(/\n/g, ' / ').slice(0, 110)}${en ? '  <<< ENGLISH' : ''}`);
}

async function main() {
  const c = new MgbaBridgeClient();
  await c.startMgba(ROM);
  await c.advanceFrames(220);
  // Title -> Continue.
  for (let i = 0; i < 6; i++) { await c.pressKey('A', 6); await c.advanceFrames(40); }
  await c.screenshot(`${OUT}/00-ingame.png`);
  const st = await c.getState() as { mapGroup?: number; mapNumber?: number; playerX?: number; playerY?: number };
  console.error(`[probe] in-game map=${st.mapGroup}.${st.mapNumber} pos=${st.playerX},${st.playerY}`);

  // Wander to trigger a wild battle. Detect via battle text.
  const dirs = ['UP', 'DOWN', 'LEFT', 'RIGHT'] as const;
  let inB = false, lastHash = '', same = 0;
  for (let i = 0; i < 240 && !inB; i++) {
    const dir = dirs[i % 4];
    for (let s = 0; s < 4; s++) { await c.pressKey(dir, 8); try { await c.advanceFrames(10); } catch { console.error('HANG while walking'); return done(c, false, false); } }
    const t = await battleText(c);
    if (looksLikeBattle(t)) { inB = true; logTxt('enter', t); break; }
    if (i % 10 === 0) {
      const h = md5((await c.screenshot(`${OUT}/walk-${i}.png`), `${OUT}/walk-${i}.png`));
      if (h && h === lastHash) same++; else { same = 0; lastHash = h; }
    }
  }
  console.error(`[probe] battle entered=${inB}`);
  if (!inB) { await c.screenshot(`${OUT}/no-battle.png`); return done(c, false, false); }

  await c.screenshot(`${OUT}/01-battle.png`);
  // Win: mash A (advance text -> FIGHT -> first move) and watch for battle end.
  let won = false, frozen = false; lastHash = ''; same = 0;
  for (let i = 0; i < 80; i++) {
    await c.pressKey('A', 4);
    try { await c.advanceFrames(40); } catch { frozen = true; console.error('HANG in battle'); break; }
    const t = await battleText(c);
    logTxt('battle', t);
    const h = md5((await c.screenshot(`${OUT}/b-${String(i).padStart(2, '0')}.png`), `${OUT}/b-${String(i).padStart(2, '0')}.png`));
    if (h && h === lastHash) same++; else { same = 0; lastHash = h; }
    if (same >= 24) { frozen = true; console.error(`[probe] BATTLE FROZEN at i=${i}`); break; }
    if (/guadagna|Punti Esp|è cresciut|liv\.|sconfitt|messo K\.?O|svenuto|in fuga|ha vinto/i.test(t)) { won = true; }
    if (won && !looksLikeBattle(t) && t.length < 3) {
      // returned to overworld
      for (let k = 0; k < 5; k++) { await c.pressKey('A', 4); await c.advanceFrames(30); }
      break;
    }
  }
  await c.screenshot(`${OUT}/02-after.png`);
  return done(c, true, won && !frozen);
}

async function done(c: MgbaBridgeClient, battleReached: boolean, battleWon: boolean) {
  console.log(JSON.stringify({ rom: ROM, battleReached, battleWon, englishHits }, null, 2));
  try { await c.stop(); } catch { /* */ }
  process.exit(0);
}
main().catch((e) => { console.error('FATAL', e); process.exit(3); });
