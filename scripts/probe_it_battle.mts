/**
 * probe_it_battle.mts — verify the Italian ROM can reach and win its first battle.
 *
 * Loads the versioned pre-battle fixture, checks its expected map/position,
 * then follows a short declarative input route into the scripted battle.
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
const ROUTE_FILE = path.join(
  PROJECT_ROOT, 'tests', 'fixtures', 'routes', 'it_first_battle.json',
);
const ROM_SLOT_PATH = ROM.replace(/\.gba$/, `.ss${FIXTURE_SLOT}`);
const OUT = '/tmp/it-battle';

const ADDR = {
  sv1: 0x02021CD0, sv2: 0x02021CF4, sv4: 0x02021D18,
  bt1: 0x02022F58, bt2: 0x02022FD8, bt3: 0x02023058,
};

// Italian battle keywords checked against all text buffers. Includes the
// trainer-challenge lines (Unbound's first battle is scripted, not a wild
// encounter) so the explore phase can detect the battle as soon as the
// challenge text appears, not only once the Fight/Bag/Run menu renders.
const BATTLE_RE = /Lotta|Fuggi|Borsa|selvagg|usa |è apparso|appare|nemic|Punti Ferita|P\.F\.|in fuga|guadagna|Punti Esp|vuole combattere|ti sfida|manda in campo|scende in campo|ti ha sfidato/i;
// Italian victory indicators.
const VICTORY_RE = /guadagna|Punti Esp|livell|è cresciut|sconfitt|messo K\.?O|svenuto|in fuga|ha vinto|vinto!|mi arrendo|lascerò passare|Gible! Torna!/i;
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

interface RouteStep {
  key: string;
  repeat: number;
  holdFrames: number;
  frames: number;
}

interface BattleRoute {
  start: {
    map: [number, number];
    position: [number, number];
  };
  steps: RouteStep[];
}

function loadRoute(): BattleRoute {
  return JSON.parse(fs.readFileSync(ROUTE_FILE, 'utf8')) as BattleRoute;
}

async function followRoute(
  c: MgbaBridgeClient,
  route: BattleRoute,
): Promise<{ battleDetected: boolean; frozen: boolean }> {
  const state = await c.getState() as {
    mapGroup?: number;
    mapNumber?: number;
    playerX?: number;
    playerY?: number;
  };
  const actual = [state.mapGroup, state.mapNumber, state.playerX, state.playerY];
  const expected = [...route.start.map, ...route.start.position];
  if (actual.some((value, index) => value !== expected[index])) {
    console.error(`[probe] Fixture position mismatch: expected=${expected.join(',')} actual=${actual.join(',')}`);
    return { battleDetected: false, frozen: false };
  }

  let lastHash = '';
  let same = 0;
  let iteration = 0;
  for (const step of route.steps) {
    for (let repeat = 0; repeat < step.repeat; repeat++) {
      await c.pressKey(step.key, step.holdFrames);
      await c.advanceFrames(step.frames);

      const text = await harvestText(c, 'route');
      if (BATTLE_RE.test(text)) {
        console.error(`[probe] First battle detected at route step ${iteration}`);
        return { battleDetected: true, frozen: false };
      }

      const screenshot = path.join(OUT, `route-${String(iteration).padStart(3, '0')}.png`);
      await c.screenshot(screenshot);
      const hash = md5(screenshot);
      if (hash && hash === lastHash) same++; else { same = 0; lastHash = hash; }
      if (same >= 30) {
        console.error(`[probe] FREEZE on fixture route at step ${iteration}`);
        return { battleDetected: false, frozen: true };
      }
      iteration++;
    }
  }
  return { battleDetected: false, frozen: false };
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

  if (!fs.existsSync(FIXTURE_FILE) || !fs.existsSync(ROUTE_FILE)) {
    console.error('[probe] Versioned fixture or route missing');
    return finish(c, false, false, false);
  }

  console.error('[probe] Loading versioned savestate slot ' + FIXTURE_SLOT);
  fs.copyFileSync(FIXTURE_FILE, ROM_SLOT_PATH);
  await c.advanceFrames(120);
  await c.loadState(FIXTURE_SLOT);
  await c.advanceFrames(120);

  // ---- Phase 2: follow the recorded short route into the battle ----
  const routeResult = await followRoute(c, loadRoute());
  const battleDetected = routeResult.battleDetected;
  if (routeResult.frozen) {
    await shot(c, 'freeze-route.png');
    return finish(c, false, false, true);
  }

  await shot(c, '02-battle-entry.png');
  console.error(`[probe] battleDetected=${battleDetected}`);

  if (!battleDetected) {
    console.error('[probe] Could not reach first battle within iteration budget');
    return finish(c, false, false, false);
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
