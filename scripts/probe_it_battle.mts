/**
 * probe_it_battle.mts — verify the Italian ROM can reach and win its first battle.
 *
 * Two execution paths:
 *   1. Fixture savestate exists (tests/fixtures/saves/it_first_battle.ss7):
 *      copy it to the ROM slot, load state, go straight to the battle phase.
 *   2. No fixture: boot from title, auto-play through the Unbound intro/prologue
 *      (confirmed working by F-56), mash into the first scripted battle, then
 *      save the state as a fixture for future runs.
 *
 * Battle detection: text buffers (Italian keywords) — the inBattle flag at
 * 0x030022C8 is unreliable in Unbound (per project notes).
 * Freeze detection: screen-hash staying pixel-identical across consecutive
 * presses — NOT player position or CPU/PC.
 *
 * Exit codes: 0=success, 1=battle not reached or not won, 2=freeze, 3=crash.
 *
 * Run: npx tsx scripts/probe_it_battle.mts [rom]
 */
import path from 'path';
import fs from 'fs';
import crypto from 'crypto';
import { fileURLToPath } from 'url';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.ts';
import { decodePokemonText } from '../tests/e2e-playwright/helpers/charmap.js';

const ROM = path.resolve(process.argv[2] ?? 'output/roms/GenedRom-it.gba');
const __scriptDir = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__scriptDir, '..');

const FIXTURE_SLOT = 7;
const FIXTURE_FILE = path.join(
  PROJECT_ROOT, 'tests', 'fixtures', 'saves', 'it_first_battle.ss7',
);
const ROM_SLOT_PATH = ROM.replace(/\.gba$/, `.ss${FIXTURE_SLOT}`);
const OUT = '/tmp/it-battle';

const ADDR = {
  sv1: 0x02021CD0, sv2: 0x02021CF4, sv4: 0x02021D18,
  bt1: 0x02022F58, bt2: 0x02022FD8, bt3: 0x02023058,
};

// Italian battle keywords checked against all text buffers.
const BATTLE_RE = /Lotta|Fuggi|Borsa|selvagg|usa |è apparso|appare|nemic|Punti Ferita|P\.F\.|in fuga|guadagna|Punti Esp/i;
// Italian victory indicators.
const VICTORY_RE = /guadagna|Punti Esp|livell|è cresciut|sconfitt|messo K\.?O|svenuto|in fuga|ha vinto|vinto!/i;
// English tokens that must not appear in Italian text.
const ENGLISH_RE = /\b(FIGHT|RUN|BAG|fainted|appeared|used|wild|Fight|the foe|POKE BALL|CONTINUE|NEW GAME|Options?)\b/;

function md5(p: string): string {
  try { return crypto.createHash('md5').update(fs.readFileSync(p)).digest('hex'); } catch { return ''; }
}

const seen = new Set<string>();
const englishHits: string[] = [];

function logTxt(stage: string, t: string): void {
  if (!t || seen.has(t)) return;
  seen.add(t);
  const en = ENGLISH_RE.test(t);
  if (en) englishHits.push(t);
  console.error(`  [${stage}] ${t.replace(/\n/g, ' / ').slice(0, 110)}${en ? '  <<< ENGLISH' : ''}`);
}

async function readTxt(c: MgbaBridgeClient, addr: number, len: number): Promise<string> {
  try { return decodePokemonText(await c.readMemory(addr, len)).trim(); } catch { return ''; }
}

async function harvestText(c: MgbaBridgeClient, stage: string): Promise<string> {
  const bufs: string[] = [];
  const targets: [string, number, number][] = [
    ['sv1', ADDR.sv1, 100], ['sv2', ADDR.sv2, 100], ['sv4', ADDR.sv4, 200],
    ['bt1', ADDR.bt1, 120], ['bt2', ADDR.bt2, 120], ['bt3', ADDR.bt3, 120],
  ];
  for (const [name, addr, len] of targets) {
    const t = await readTxt(c, addr, len);
    if (t.length > 2) { logTxt(`${stage}/${name}`, t); bufs.push(t); }
  }
  return bufs.join(' | ');
}

async function shot(c: MgbaBridgeClient, name: string): Promise<void> {
  try { await c.screenshot(path.join(OUT, name)); } catch { /* */ }
}

async function main(): Promise<void> {
  fs.rmSync(OUT, { recursive: true, force: true });
  fs.mkdirSync(OUT, { recursive: true });

  if (!fs.existsSync(ROM)) {
    console.error(`[probe] ROM not found: ${ROM}`);
    process.exit(3);
  }

  const c = new MgbaBridgeClient();
  await c.startMgba(ROM);

  let startedFromFixture = false;

  // ---- Fast path: pre-baked fixture savestate ----
  if (fs.existsSync(FIXTURE_FILE)) {
    console.error('[probe] Fixture found — loading savestate slot ' + FIXTURE_SLOT);
    fs.copyFileSync(FIXTURE_FILE, ROM_SLOT_PATH);
    await c.advanceFrames(120);
    try {
      await c.loadState(FIXTURE_SLOT);
      await c.advanceFrames(120);
      startedFromFixture = true;
      console.error('[probe] Fixture loaded — skipping intro');
    } catch (e) {
      console.error('[probe] loadState failed:', String(e), '— falling back to boot');
    }
  }

  // ---- Slow path: boot from title through the Unbound intro ----
  if (!startedFromFixture) {
    console.error('[probe] No fixture — booting from title through Unbound intro...');

    await c.advanceFrames(600);   // wait for title logo animation
    await shot(c, '00-title.png');

    // START to open menu, A to confirm → starts new game (no battery save in IT).
    await c.pressKey('START', 4); await c.advanceFrames(120);
    await c.pressKey('A', 4);    await c.advanceFrames(120);

    let lastHash = '', same = 0;
    // ~220 iterations × 40 frames ≈ 147 s — generous budget for the Unbound prologue.
    for (let i = 0; i < 220; i++) {
      await c.pressKey('A', 4);
      // Naming keyboard (BPRE): START confirms the selected name in early steps.
      if (i < 25 && i % 4 === 3) await c.pressKey('START', 4);
      await c.advanceFrames(40);

      const txt = await harvestText(c, 'intro');
      if (BATTLE_RE.test(txt)) {
        console.error('[probe] Battle detected during intro phase!');
        break;
      }

      if (i % 15 === 0) {
        const p = path.join(OUT, `intro-${String(i).padStart(3, '0')}.png`);
        await c.screenshot(p);
        const h = md5(p);
        if (h && h === lastHash) same++; else { same = 0; lastHash = h; }
        if (same >= 28) {
          console.error(`[probe] FREEZE during intro at i=${i}`);
          await shot(c, 'freeze-intro.png');
          return finish(c, false, false, true);
        }
      }
    }
    await shot(c, '01-post-intro.png');
    const st = await c.getState() as { mapGroup?: number; mapNumber?: number };
    console.error(`[probe] post-intro: map=${st.mapGroup}.${st.mapNumber}`);
  }

  // ---- Phase 2: drive into the first scripted battle ----
  // Unbound's first battle is scripted (not a wild encounter), so pressing A
  // through NPC dialogue/event scripts is the correct trigger — not wandering.
  const dirs = ['DOWN', 'RIGHT', 'UP', 'LEFT'] as const;
  let battleDetected = false;
  let lastHash2 = '', same2 = 0;
  let fixtureSaved = false;

  for (let i = 0; i < 480 && !battleDetected; i++) {
    // 5 A-presses per every 6 steps (script/dialogue advance); 1 directional.
    if (i % 6 === 5) {
      await c.pressKey(dirs[Math.floor(i / 6) % 4], 8);
      await c.advanceFrames(18);
    } else {
      await c.pressKey('A', 4);
      await c.advanceFrames(32);
    }

    const txt = await harvestText(c, 'explore');
    if (BATTLE_RE.test(txt)) {
      battleDetected = true;
      console.error(`[probe] First battle detected at explore i=${i}`);
      break;
    }

    if (i % 10 === 0) {
      const p = path.join(OUT, `explore-${String(i).padStart(3, '0')}.png`);
      await c.screenshot(p);
      const h = md5(p);
      if (h && h === lastHash2) same2++; else { same2 = 0; lastHash2 = h; }
      if (same2 >= 32) {
        console.error(`[probe] FREEZE in explore at i=${i}`);
        await shot(c, 'freeze-explore.png');
        return finish(c, false, false, true);
      }
    }
  }

  await shot(c, '02-battle-entry.png');
  console.error(`[probe] battleDetected=${battleDetected} startedFromFixture=${startedFromFixture}`);

  if (!battleDetected) {
    console.error('[probe] Could not reach first battle within iteration budget');
    return finish(c, false, false, false);
  }

  // Save fixture on first successful generation.
  if (!startedFromFixture && !fixtureSaved) {
    try {
      await c.saveState(FIXTURE_SLOT);
      await new Promise<void>((r) => setTimeout(r, 600));
      if (fs.existsSync(ROM_SLOT_PATH)) {
        fs.copyFileSync(ROM_SLOT_PATH, FIXTURE_FILE);
        console.error(`[probe] Fixture saved → ${FIXTURE_FILE}`);
        fixtureSaved = true;
      }
    } catch (e) {
      console.error('[probe] Fixture save failed (non-fatal):', String(e));
    }
  }

  // ---- Phase 3: fight and win ----
  // Mash A: advances battle text → opens FIGHT menu → selects first move.
  let battleWon = false;
  let frozen = false;
  let lastHash3 = '', same3 = 0;

  for (let i = 0; i < 150; i++) {
    await c.pressKey('A', 4);
    await c.advanceFrames(40);

    const txt = await harvestText(c, 'battle');

    const p = path.join(OUT, `battle-${String(i).padStart(2, '0')}.png`);
    await c.screenshot(p);
    const h = md5(p);
    if (h && h === lastHash3) same3++; else { same3 = 0; lastHash3 = h; }
    if (same3 >= 30) {
      frozen = true;
      console.error(`[probe] BATTLE FROZEN at i=${i}`);
      break;
    }

    if (VICTORY_RE.test(txt)) {
      battleWon = true;
      console.error(`[probe] Victory detected at battle i=${i}!`);
      for (let k = 0; k < 12; k++) { await c.pressKey('A', 4); await c.advanceFrames(30); }
      break;
    }
  }

  await shot(c, '03-after-battle.png');
  return finish(c, true, battleWon && !frozen, frozen);
}

async function finish(
  c: MgbaBridgeClient,
  battleReached: boolean,
  battleWon: boolean,
  froze: boolean,
): Promise<void> {
  const report = { rom: ROM, battleReached, battleWon, froze, englishHits };
  // Single-line JSON so callers can parse by scanning the last stdout line.
  console.log(JSON.stringify(report));
  try { await c.stop(); } catch { /* */ }
  if (froze) process.exit(2);
  if (!battleReached || !battleWon) process.exit(1);
  process.exit(0);
}

main().catch((e) => { console.error('FATAL', e); process.exit(3); });
