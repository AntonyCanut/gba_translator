/**
 * probe_it_playthrough.mts — play the Italian ROM from boot through the intro,
 * character creation/naming, into the overworld and the FIRST battle, winning
 * it. Proves the start does not freeze and everything renders in Italian.
 *
 *  - Detects a freeze two ways: a hang on advanceFrames (CPU infinite loop) and
 *    a screen-hash that stays identical across many inputs (the reliable signal).
 *  - Harvests every text buffer it sees and flags residual English tokens.
 *  - Saves screenshots to /tmp/it-play and a JSON report on stdout.
 *
 * Run: npx tsx scripts/probe_it_playthrough.mts [rom]
 */
import path from 'path';
import fs from 'fs';
import crypto from 'crypto';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.ts';
import { decodePokemonText } from '../tests/e2e-playwright/helpers/charmap.js';

const ROM = path.resolve(process.argv[2] ?? 'output/roms/GenedRom-it.gba');
const OUT = '/tmp/it-play';
fs.rmSync(OUT, { recursive: true, force: true });
fs.mkdirSync(OUT, { recursive: true });

const ADDR = {
  sv1: 0x02021CD0, sv2: 0x02021CF4, sv4: 0x02021D18,
  bt1: 0x02022F58, bt2: 0x02022FD8, bt3: 0x02023058,
};
const SMALL = 100, BIG = 1000;

// English words that must never survive in Italian text (word-boundary match).
const EN = ['POKE BALL', 'FIGHT', 'RUN', 'BAG', 'POKEMON', 'PLAYER', 'CONTINUE',
  'NEW GAME', 'OPTION', 'what is', 'your name', 'fainted', 'appeared', 'used',
  'the wild', ' boy', ' girl', 'Choose', 'Last, but', 'Welcome'];

function md5(p: string) { try { return crypto.createHash('md5').update(fs.readFileSync(p)).digest('hex'); } catch { return ''; } }

const seen = new Set<string>();
const captures: { stage: string; text: string; english: string[] }[] = [];

function inspect(text: string): string[] {
  const out: string[] = [];
  if (/[A-Za-zÀ-ÿ]\?[A-Za-z0-9]{1,3}\?/.test(text)) out.push(`garbage-token: ${text.slice(0, 40)}`);
  for (const e of EN) {
    const re = new RegExp(`\\b${e.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i');
    if (re.test(text)) out.push(`english:"${e}"`);
  }
  return out;
}

async function harvest(c: MgbaBridgeClient, stage: string) {
  for (const [name, addr, len] of [['sv1', ADDR.sv1, SMALL], ['sv2', ADDR.sv2, SMALL], ['sv4', ADDR.sv4, BIG], ['bt1', ADDR.bt1, SMALL], ['bt2', ADDR.bt2, SMALL], ['bt3', ADDR.bt3, SMALL]] as const) {
    let text = '';
    try { text = decodePokemonText(await c.readMemory(addr as number, len as number)).trim(); } catch { continue; }
    if (text.length < 3) continue;
    const key = `${name}:${text}`;
    if (seen.has(key)) continue;
    seen.add(key);
    const english = inspect(text);
    captures.push({ stage, text, english });
    const flag = english.length ? `  <<< ${english.join(',')}` : '';
    console.error(`  [${stage}/${name}] ${text.replace(/\n/g, ' / ').slice(0, 90)}${flag}`);
  }
}

async function shot(c: MgbaBridgeClient, name: string): Promise<string> {
  const p = `${OUT}/${name}.png`;
  try { await c.screenshot(p); } catch { /* */ }
  return p;
}

async function inBattle(c: MgbaBridgeClient): Promise<boolean> {
  try { const s = await c.getState(); return Boolean((s as { inBattle?: boolean }).inBattle); } catch { return false; }
}

let hung = false;
async function adv(c: MgbaBridgeClient, n: number): Promise<boolean> {
  try { await c.advanceFrames(n); return true; } catch (e) { hung = true; console.error(`HANG advanceFrames(${n}): ${String(e)}`); return false; }
}

async function main() {
  const c = new MgbaBridgeClient();
  await c.startMgba(ROM);
  if (!await adv(c, 600)) return finish(c, 'boot');
  await shot(c, '00-title');

  // ---- Intro + character creation + naming ----
  // Press A to advance dialogue; press START periodically to confirm the
  // FireRed naming keyboard (START == OK there).
  await c.pressKey('START', 4); await adv(c, 90);
  await c.pressKey('A', 4); await adv(c, 90);
  let lastHash = '', same = 0;
  for (let i = 0; i < 70; i++) {
    await c.pressKey('A', 4);
    if (i % 4 === 3) await c.pressKey('START', 4); // confirm naming keyboard
    if (!await adv(c, 40)) return finish(c, `intro-${i}`);
    await harvest(c, 'intro');
    const h = md5(await shot(c, `intro-${String(i).padStart(2, '0')}`));
    if (h && h === lastHash) same++; else { same = 0; lastHash = h; }
    if (same >= 30) { console.error(`FREEZE: intro screen stable ${same}x at i=${i}`); return finish(c, `intro-frozen-${i}`); }
    if (await inBattle(c)) { console.error(`battle during intro at i=${i}`); break; }
  }
  await shot(c, '01-after-intro');

  // ---- Explore overworld to trigger the first battle ----
  const dirs = ['UP', 'DOWN', 'LEFT', 'RIGHT', 'UP', 'RIGHT', 'DOWN', 'LEFT'] as const;
  let battleReached = await inBattle(c);
  lastHash = ''; same = 0;
  for (let i = 0; i < 160 && !battleReached; i++) {
    // advance any dialogue / interact
    await c.pressKey('A', 4); if (!await adv(c, 18)) return finish(c, `ow-A-${i}`);
    const dir = dirs[i % dirs.length];
    for (let s = 0; s < 3; s++) { await c.pressKey(dir, 8); if (!await adv(c, 12)) return finish(c, `ow-${dir}-${i}`); }
    if (i % 6 === 0) await harvest(c, 'overworld');
    if (i % 8 === 0) {
      const h = md5(await shot(c, `ow-${String(i).padStart(3, '0')}`));
      if (h && h === lastHash) same++; else { same = 0; lastHash = h; }
    }
    battleReached = await inBattle(c);
  }
  await shot(c, '02-explore-end');
  console.error(`battleReached=${battleReached}`);

  // ---- Battle: win by selecting Fight -> first move repeatedly ----
  let battleWon = false;
  if (battleReached) {
    await harvest(c, 'battle');
    await shot(c, '03-battle-start');
    for (let i = 0; i < 60; i++) {
      await c.pressKey('A', 4);          // advance text / pick Fight / pick first move
      if (!await adv(c, 40)) return finish(c, `battle-${i}`);
      if (i % 3 === 0) await harvest(c, 'battle');
      if (i % 5 === 0) await shot(c, `battle-${String(i).padStart(2, '0')}`);
      if (!await inBattle(c)) {
        // battle ended; advance a bit and confirm we are back in the overworld
        for (let k = 0; k < 6; k++) { await c.pressKey('A', 4); if (!await adv(c, 30)) break; }
        battleWon = !await inBattle(c);
        console.error(`battle ended at i=${i}, backInOverworld=${battleWon}`);
        break;
      }
    }
    await harvest(c, 'post-battle');
    await shot(c, '04-post-battle');
  }

  return finish(c, 'done', { battleReached, battleWon });
}

async function finish(c: MgbaBridgeClient, where: string, extra: Record<string, unknown> = {}) {
  const english = captures.filter((x) => x.english.length);
  const report = {
    rom: ROM, stoppedAt: where, hung,
    captured: captures.length,
    englishHits: english.length,
    englishSamples: english.slice(0, 20),
    ...extra,
  };
  console.log(JSON.stringify(report, null, 2));
  try { await c.stop(); } catch { /* */ }
  process.exit(hung || where.includes('frozen') ? 1 : 0);
}

main().catch((e) => { console.error('FATAL', e); process.exit(3); });
