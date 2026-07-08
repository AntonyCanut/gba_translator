/**
 * probe_enemy_team_multi_battle.mts — reach and dump CFRU's in-battle "Team
 * Preview" overlay from a genuine BATTLE_TYPE_MULTI fight (investigation for
 * GitHub issue #75, the "ENEMY TEAM" graphic). Follow-up to
 * probe_enemy_team_preview.mts, which proved the 1v1/double "Team Preview"
 * overlay renders the dynamic trainer name (gText_TeamPreviewSingleDoubleText,
 * e.g. "Admin Ombre Ivory"), NOT the static "ENEMY TEAM"/"YOUR TEAM" graphic —
 * see memory unbound-enemy-team-not-cfru-teampreview.md.
 *
 * ⚠️ BLOCKED ON A FIXTURE — read this before running.
 * ---------------------------------------------------
 * Unbound's only genuine player+AI-partner "Multi Battle" (BATTLE_TYPE_MULTI,
 * upstream gText_TeamPreviewMultiText — two trainer names at once) lives
 * inside dedicated postgame facilities in Daherapolis:
 *   - Tour de Combat ("Salle Multi" / "Combat Multi", combined_fr.txt
 *     offsets 0x1F8F690-0x1F9419A, e.g. 0x1F94151 "Combat Multi")
 *   - Cirque de Combat (0x1F8A917-0x1F8ADD8, same Solo/Duo/Multi format)
 * Both require: talking to the facility's guide NPC, then either linking a
 * second real player or picking an AI partner in a "Salon de Combat"
 * (0x1F8DD7F "tu n'as pas trouvé de partenaire pour ton duo" /
 * 0x1F8DD3C "Veuillez choisir un partenaire parmi les Dresseurs") before the
 * Multi Battle itself starts. This is postgame content (Daherapolis is also
 * where the dev-team gauntlet battles live) reached only after substantial
 * story progress.
 *
 * Searched (this session): every .sav/.srm/.ss1-9 in this repo (all
 * early/mid-game — see tests/fixtures/saves/README.md), any debug menu /
 * warp / flag-editing tool (none exists; the only writeMemory() cheat in the
 * codebase, an HP-pin auto-win used by scripts/repro_give_cs.mts, is
 * documented as UNSAFE — it corrupts RAM into a black screen, do not repurpose
 * it to fake game-progress flags). No fast path exists. Producing a fixture
 * requires an actual playthrough (manual or a long automated run) to
 * Daherapolis with a partner chosen in the Salon de Combat, saved right
 * before the Multi Battle starts — out of scope for a single probe script.
 * See B-263/B-264 follow-up ticket for tracking that fixture's creation.
 *
 * Once such a fixture exists, drop it at FIXTURE below (or override with
 * $MULTI_FIXTURE) and supply the button path from where it leaves the player
 * up to the first turn of the Multi Battle — WITHOUT editing this file. The
 * exact sequence depends entirely on where the save drops you (facade guide,
 * Salon de Combat, or already at the Salle Multi door), so it lives as
 * runtime DATA next to the fixture, not hard-coded here:
 *   - a sidecar text file `<fixture-basename>.walk.txt`, or
 *   - the $MULTI_WALK env var (same syntax, ';'- or newline-separated).
 * Walk-line syntax (whitespace-separated, '#' starts a comment):
 *   KEY [repeat=1] [holdFrames=4] [advanceFrames=20]
 * e.g.  `DOWN 5 4 12`  = tap DOWN five times, 4-frame hold, 12 frames between;
 *       `A 1 4 90`     = press A once, wait 90 frames for the textbox.
 * Everything else (Team Preview option setup, L-before-A overlay sweep,
 * VRAM/palette dump) is unchanged and proven working by
 * probe_enemy_team_preview.mts. If no walk data is supplied the probe still
 * runs the L-sweep from wherever the fixture lands (useful if the save is
 * already parked on the first Multi Battle turn).
 *
 * Run: MGBA_PATH=/opt/homebrew/bin/mgba \
 *        MULTI_FIXTURE=tests/fixtures/saves/pre-multi-battle-daherapolis.srm \
 *        npx tsx scripts/probe_enemy_team_multi_battle.mts
 */
import fs from 'fs';
import path from 'path';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.ts';

const ROM = path.resolve('output/roms/GenedRom-fr.gba');
const SAV = ROM.replace(/\.gba$/i, '.sav');
// Must sit right before entering the Salle Multi in Daherapolis' Tour de
// Combat (or Cirque de Combat), partner already picked. Still to be produced
// by a human playthrough — see the blocker note above. Override at runtime
// with $MULTI_FIXTURE if you park a save elsewhere.
const FIXTURE = path.resolve(
  process.env.MULTI_FIXTURE || 'tests/fixtures/saves/pre-multi-battle-daherapolis.srm',
);
const OUT_DIR = path.resolve('output/proofs/enemy-team-multi');
fs.mkdirSync(OUT_DIR, { recursive: true });

/** One parsed walk step: press `key` `repeat` times, holding `hold` frames,
 *  advancing `advance` frames after each press. */
interface WalkStep { key: string; repeat: number; hold: number; advance: number; }

/** Parse the walk-script syntax documented in the file header. Accepts ';' or
 *  newline separators, strips '#' comments, tolerates blank lines. */
function parseWalkScript(src: string): WalkStep[] {
  const steps: WalkStep[] = [];
  for (const rawLine of src.split(/[;\n]/)) {
    const line = rawLine.replace(/#.*$/, '').trim();
    if (!line) continue;
    const [key, repeat, hold, advance] = line.split(/\s+/);
    steps.push({
      key: key.toUpperCase(),
      repeat: repeat ? parseInt(repeat, 10) : 1,
      hold: hold ? parseInt(hold, 10) : 4,
      advance: advance ? parseInt(advance, 10) : 20,
    });
  }
  return steps;
}

/** Resolve the walk data from $MULTI_WALK or the fixture's `.walk.txt` sidecar
 *  (env wins). Returns [] when nothing is supplied — the L-sweep then runs from
 *  wherever the fixture lands. */
function loadWalkScript(): WalkStep[] {
  if (process.env.MULTI_WALK) return parseWalkScript(process.env.MULTI_WALK);
  const sidecar = FIXTURE.replace(/\.[^.]+$/, '') + '.walk.txt';
  if (fs.existsSync(sidecar)) return parseWalkScript(fs.readFileSync(sidecar, 'utf8'));
  return [];
}

async function shot(c: MgbaBridgeClient, name: string): Promise<void> {
  try { await c.screenshot(path.join(OUT_DIR, `${name}.png`)); } catch (e) { console.error(`[shot] ${name} failed`, e); }
}
async function dumpRegion(c: MgbaBridgeClient, base: number, size: number, file: string): Promise<void> {
  const chunks: Buffer[] = [];
  for (let off = 0; off < size; off += 4096) {
    const len = Math.min(4096, size - off);
    chunks.push(Buffer.from(await c.readMemory(base + off, len)));
  }
  fs.writeFileSync(path.join(OUT_DIR, file), Buffer.concat(chunks));
}
async function dumpScreen(c: MgbaBridgeClient, tag: string): Promise<void> {
  await dumpRegion(c, 0x06000000, 0x10000, `${tag}-vram-bg.bin`);
  await dumpRegion(c, 0x06010000, 0x8000, `${tag}-vram-obj.bin`);
  await dumpRegion(c, 0x05000000, 0x400, `${tag}-pal.bin`);
}

async function setTeamPreviewAlways(c: MgbaBridgeClient): Promise<void> {
  // Proven in probe_enemy_team_preview.mts: without this, CantLoadTeamPreviewTrigger()
  // blocks the L-button overlay outside Battle Frontier — but Daherapolis IS
  // Battle Frontier-adjacent, so this step may turn out to be unnecessary
  // there. Keep it anyway; it's a harmless no-op if already "Toujours".
  await c.pressKey('START', 4); await c.advanceFrames(40);
  for (let i = 0; i < 6; i++) { await c.pressKey('RIGHT', 4); await c.advanceFrames(20); }
  await c.pressKey('A', 4); await c.advanceFrames(60);
  for (let i = 0; i < 2; i++) { await c.pressKey('R', 8); await c.advanceFrames(60); }
  for (let i = 0; i < 6; i++) { await c.pressKey('DOWN', 4); await c.advanceFrames(20); }
  await c.pressKey('RIGHT', 4); await c.advanceFrames(30);
  await c.pressKey('B', 6); await c.advanceFrames(40);
  await c.pressKey('A', 6); await c.advanceFrames(60);
  for (let i = 0; i < 3; i++) { await c.pressKey('B', 6); await c.advanceFrames(30); }
}

async function main(): Promise<void> {
  if (!fs.existsSync(FIXTURE)) {
    console.error(`[multi] FIXTURE missing: ${FIXTURE} — see blocker note at top of this file.`);
    process.exit(3);
  }
  fs.copyFileSync(FIXTURE, SAV);
  const c = new MgbaBridgeClient();
  await c.startMgba(ROM);
  await c.advanceFrames(600);
  await c.pressKey('START', 4); await c.advanceFrames(120);
  await c.pressKey('A', 4);    await c.advanceFrames(180);
  await c.pressKey('A', 4);    await c.advanceFrames(180);
  for (let i = 0; i < 3; i++) { await c.pressKey('B', 4); await c.advanceFrames(20); }

  await setTeamPreviewAlways(c);
  await shot(c, '00-loaded');

  // ---- Walk into the Salle Multi and start the fight ----
  // Data-driven (see file header): the exact path from where the fixture drops
  // the player to the first Multi Battle turn is supplied at runtime via
  // $MULTI_WALK or a `<fixture>.walk.txt` sidecar, because it is unknowable
  // until the (human-produced) fixture exists. With no walk data the sweep
  // simply runs from the fixture's landing spot.
  const walk = loadWalkScript();
  if (walk.length === 0) {
    console.error('[multi] no walk script ($MULTI_WALK / .walk.txt) — running L-sweep from fixture landing spot');
  }
  for (let s = 0; s < walk.length; s++) {
    const { key, repeat, hold, advance } = walk[s];
    for (let r = 0; r < repeat; r++) {
      await c.pressKey(key, hold);
      await c.advanceFrames(advance);
    }
    await shot(c, `05-walk-${String(s).padStart(2, '0')}-${key}`);
  }

  // ---- L-BEFORE-A sweep (unchanged, proven in probe_enemy_team_preview.mts) ----
  for (let k = 0; k < 60; k++) {
    await c.pressKey('L', 4);
    await c.advanceFrames(16);
    const tag = `06-k${String(k).padStart(3, '0')}`;
    await shot(c, tag);
    if (k % 2 === 0) await dumpScreen(c, tag);
    await c.pressKey('A', 4);
    await c.advanceFrames(10);
  }

  await c.stop();
  console.error('[multi] done');
}

main().catch((e) => { console.error('[multi] FATAL', e); process.exit(1); });
