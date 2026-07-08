/**
 * probe_enemy_team_preview.mts — reach and dump CFRU's in-battle "Team
 * Preview" overlay (investigation for GitHub issue #75, the "ENEMY TEAM"
 * graphic).
 *
 * Chain proven working this session:
 *  1. Load post-zeph-pre-cs.srm, open Options -> Options de combat -> set
 *     "Apercu equipe" (Team Preview) from "Zone Combat seul." (Frontier
 *     Only) to "Toujours" (Always) — required, otherwise
 *     CantLoadTeamPreviewTrigger() blocks the L-button overlay outside
 *     Battle Frontier (upstream CFRU src/battle_indicators.c).
 *  2. Walk down to trigger the Zeph/Admin Ombre Ivory single battle.
 *  3. At the action-selection ("Que doit faire ... ?") menu, press L BEFORE
 *     A each step (pressing A first always advances past the menu before L
 *     gets a chance — the bug that blocked every earlier attempt) to open
 *     the Team Preview overlay, dumping VRAM + palette + a screenshot at
 *     every step.
 *
 * RESULT (see output/proofs/enemy-team-final/06-k032.png and memory
 * unbound-enemy-team-not-cfru-teampreview.md): this overlay renders the
 * dynamic trainer name ("Admin Ombre Ivory") being typed out — CFRU's
 * standard `gText_TeamPreviewSingleDoubleText` ("[Trainer]'s Team") path,
 * NOT the static "ENEMY TEAM"/"YOUR TEAM" graphic from the issue. This
 * proves the issue's asset is NOT this code path for a regular 1-trainer
 * battle. Leading remaining hypothesis: Unbound may render the "ENEMY TEAM"
 * graphic only for the BATTLE_TYPE_MULTI branch (`gText_TeamPreviewMultiText`,
 * two trainers at once) — rerun this same probe from a Multi Battle
 * (partner battle) savestate instead of a 1v1 to test that.
 *
 * Run: MGBA_PATH=/opt/homebrew/bin/mgba npx tsx scripts/probe_enemy_team_preview.mts
 */
import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.ts';
import { decodePokemonText } from '../tests/e2e-playwright/helpers/charmap.js';

const ROM = path.resolve('output/roms/GenedRom-fr.gba');
const SAV = ROM.replace(/\.gba$/i, '.sav');
const FIXTURE = path.resolve('tests/fixtures/saves/post-zeph-pre-cs.srm');
const OUT_DIR = path.resolve('output/proofs/enemy-team-final');
fs.mkdirSync(OUT_DIR, { recursive: true });

const ADDR = { sv1: 0x02021CD0, sv2: 0x02021CF4, sv4: 0x02021D18 };

async function readTxt(c: MgbaBridgeClient, addr: number, len: number): Promise<string> {
  try { return decodePokemonText(await c.readMemory(addr, len)).trim(); } catch { return ''; }
}
async function harvest(c: MgbaBridgeClient): Promise<string> {
  const parts: string[] = [];
  for (const [addr, len] of [[ADDR.sv1, 100], [ADDR.sv2, 100], [ADDR.sv4, 200]] as const) {
    const t = await readTxt(c, addr, len);
    if (t.length > 2) parts.push(t);
  }
  return parts.join(' | ');
}

function md5(p: string): string {
  try { return crypto.createHash('md5').update(fs.readFileSync(p)).digest('hex'); } catch { return ''; }
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

async function main(): Promise<void> {
  fs.copyFileSync(FIXTURE, SAV);
  const c = new MgbaBridgeClient();
  await c.startMgba(ROM);
  await c.advanceFrames(600);
  await c.pressKey('START', 4); await c.advanceFrames(120);
  await c.pressKey('A', 4);    await c.advanceFrames(180);
  await c.pressKey('A', 4);    await c.advanceFrames(180);
  for (let i = 0; i < 3; i++) { await c.pressKey('B', 4); await c.advanceFrames(20); }

  // ---- Set "Team Preview" option to "Always" ----
  await c.pressKey('START', 4); await c.advanceFrames(40);
  for (let i = 0; i < 6; i++) { await c.pressKey('RIGHT', 4); await c.advanceFrames(20); }
  await c.pressKey('A', 4); await c.advanceFrames(60);
  for (let i = 0; i < 2; i++) { await c.pressKey('R', 8); await c.advanceFrames(60); }
  await shot(c, '00-combat-options');
  // 6 DOWN presses lands on "Apercu equipe" (proved via probe_options_menu5's
  // contact3.png: down-05, the 6th press, shows the "Propose de voir
  // l'equipe adverse." description for that row).
  for (let i = 0; i < 6; i++) { await c.pressKey('DOWN', 4); await c.advanceFrames(20); }
  await shot(c, '01-on-team-preview-setting');
  await c.pressKey('RIGHT', 4); await c.advanceFrames(30);
  await shot(c, '02-team-preview-set-always');
  // B opens "Enregistrer ou annuler reglages?" (Sauver/Ignorer/Annuler); A
  // confirms the default "Sauver" (Save), then a few more B's fully close
  // the START menu back to the overworld (proved by probe_exit_menu2.mts).
  await c.pressKey('B', 6); await c.advanceFrames(40);
  await c.pressKey('A', 6); await c.advanceFrames(60);
  for (let i = 0; i < 3; i++) { await c.pressKey('B', 6); await c.advanceFrames(30); }
  await shot(c, '03-back-to-overworld');

  // ---- Walk down to trigger the Zeph/Ivory battle cutscene ----
  const BATTLE_RE = /envoie|utilise|Ivory|go\s*!|combattre|Que doit faire/i;
  let lastHash = '', same = 0, frozen = false, battleSeen = false;
  let i = 0;
  for (; i < 400 && !battleSeen; i++) {
    await c.pressKey('DOWN', 8); await c.advanceFrames(10);
    await c.pressKey('A', 4);    await c.advanceFrames(20);
    const txt = await harvest(c);
    if (BATTLE_RE.test(txt)) {
      battleSeen = true;
      console.error(`[final] battle text detected at i=${i}: ${txt.slice(0, 80)}`);
      break;
    }
    if (i % 10 === 0) {
      const p = path.join(OUT_DIR, '_walk.png');
      await c.screenshot(p);
      const h = md5(p);
      if (h && h === lastHash) same++; else { same = 0; lastHash = h; }
      if (same >= 30) { frozen = true; break; }
    }
  }
  await shot(c, '04-pre-battle');
  if (frozen) {
    console.error('[final] FREEZE during walk — aborting');
    await c.stop();
    process.exit(2);
  }
  if (!battleSeen) {
    console.error('[final] battle never detected during walk — aborting');
    await c.stop();
    process.exit(4);
  }

  // ---- L-BEFORE-A sweep ----
  // Bug found in earlier attempts: pressing A before L every step means A
  // (cursor already on "Attaque") always advances PAST the action-select
  // screen before L ever gets a chance to act on it — so a screenshot taken
  // after both presses can never show the action-select screen with L
  // applied. Fix: try L FIRST each step (catches the action-select screen
  // exactly as it was left by the PREVIOUS step's A), screenshot, THEN press
  // A to progress if nothing opened.
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
  console.error('[final] done');
}

main().catch((e) => { console.error('[final] FATAL', e); process.exit(1); });
