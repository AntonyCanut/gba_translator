/**
 * probe_hooh_battle.mts — Ho-Oh / Lugia encounter probe.
 *
 * Loads a save-state (or battery .sav via boot+cont), reads the game flags
 * that gate the Ho-Oh and Lugia encounters, and if the player is already on
 * the encounter map attempts to trigger the battle while watching for a
 * screen-hash freeze (identical pixels across many A-presses = hang).
 *
 * Usage:
 *   MGBA_PATH=/opt/homebrew/bin/mgba \
 *   npx tsx scripts/probe_hooh_battle.mts [romPath] [slot|"sav"] [mapGroup] [mapNum]
 *
 *   slot    : mGBA savestate slot (0–9, default 1). Pass "sav" to use the
 *             battery .sav via boot+continue sequence instead.
 *   mapGroup: expected mapGroup where Ho-Oh/Lugia lives (optional check)
 *   mapNum  : expected mapNum  where Ho-Oh/Lugia lives (optional check)
 *
 * Exit codes:
 *   0 = no freeze detected on the encounter map
 *   1 = FREEZE detected (GetStringWidth infinite loop)
 *   2 = player not on encounter map after load (inconclusive)
 *   3 = error
 */
import path from 'path';
import fs from 'fs';
import crypto from 'crypto';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.ts';

const ROM    = path.resolve(process.argv[2] ?? 'output/roms/GenedRom-fr.gba');
const SLOT   = process.argv[3] ?? '1';
const USE_SAV = SLOT === 'sav';
const SLOT_N  = USE_SAV ? 1 : Number(SLOT);

const EXPECTED_MAP_GROUP = process.argv[4] !== undefined ? Number(process.argv[4]) : null;
const EXPECTED_MAP_NUM   = process.argv[5] !== undefined ? Number(process.argv[5]) : null;

const FREEZE_PRESSES = 45;
const MAX_PRESSES    = 240;
const OUT_DIR = path.resolve('output/proofs/hooh-probe');
fs.mkdirSync(OUT_DIR, { recursive: true });

function md5(p: string): string {
  try { return crypto.createHash('md5').update(fs.readFileSync(p)).digest('hex'); } catch { return ''; }
}

async function shot(c: MgbaBridgeClient, name: string): Promise<void> {
  try { await c.screenshot(path.join(OUT_DIR, `${name}.png`)); } catch { /* best-effort */ }
}

/**
 * Read a game flag from WRAM.
 * gSaveBlock1Ptr is at 0x03005008.  Flags array is at SaveBlock1 + 0x1558
 * in standard BPRE (CFRU may differ by a few bytes; use as an approximation).
 * Each flag is 1 bit: byte = flagId >> 3, bit = flagId & 7.
 */
async function readFlag(c: MgbaBridgeClient, flagId: number): Promise<boolean> {
  const sb1PtrBytes = await c.readMemory(0x03005008, 4);
  const sb1Ptr = (sb1PtrBytes[0] | (sb1PtrBytes[1] << 8) |
                  (sb1PtrBytes[2] << 16) | (sb1PtrBytes[3] << 24)) >>> 0;
  if (sb1Ptr < 0x02000000 || sb1Ptr >= 0x03000000) return false;

  // Try two common FLAGS_OFFSET values (BPRE: 0x1558, CFRU may use 0x1450 or similar)
  for (const offset of [0x1558, 0x1450, 0x1500]) {
    const byteIdx = flagId >> 3;
    const bitIdx  = flagId & 7;
    const addr = sb1Ptr + offset + byteIdx;
    try {
      const bytes = await c.readMemory(addr, 1);
      const bit   = (bytes[0] >> bitIdx) & 1;
      // Sanity: flag 0 should always be clear
      const flag0Addr  = sb1Ptr + offset;
      const flag0Bytes = await c.readMemory(flag0Addr, 1);
      if ((flag0Bytes[0] & 1) === 0) {
        return bit === 1;
      }
    } catch { /* try next offset */ }
  }
  return false;
}

async function getPos(c: MgbaBridgeClient) {
  const s = await c.getState();
  return { mapGroup: s.mapGroup as number, mapNum: s.mapNumber as number,
           x: s.playerX as number, y: s.playerY as number };
}

async function main(): Promise<void> {
  const client = new MgbaBridgeClient();
  console.error(`[hooh-probe] ROM: ${ROM}  slot/sav: ${SLOT}`);
  await client.startMgba(ROM);

  // ── Load save ───────────────────────────────────────────────────────────
  if (USE_SAV) {
    await client.advanceFrames(600);
    await shot(client, '01-title');
    await client.pressKey('START', 4); await client.advanceFrames(120);
    await client.pressKey('A', 4);     await client.advanceFrames(180);
    await client.pressKey('A', 4);     await client.advanceFrames(180);
  } else {
    await client.advanceFrames(120);
    await client.loadState(SLOT_N);
    await client.advanceFrames(60);
  }

  const pos0 = await getPos(client);
  console.error(`[hooh-probe] after load: map=${pos0.mapGroup}.${pos0.mapNum} pos=${pos0.x},${pos0.y}`);
  await shot(client, '02-after-load');

  // ── Game flags ──────────────────────────────────────────────────────────
  const flagHoOh  = await readFlag(client, 0x0700);  // Ho-Oh encountered
  const flagLugia = await readFlag(client, 0x0988);  // Lugia event
  const flagLugia2= await readFlag(client, 0x0994);  // Lugia state 2
  console.error(
    `[hooh-probe] flags: Ho-Oh-encountered(0x0700)=${flagHoOh}` +
    ` Lugia-event(0x0988)=${flagLugia} Lugia-state2(0x0994)=${flagLugia2}`
  );

  // ── Map check ───────────────────────────────────────────────────────────
  const onExpectedMap =
    (EXPECTED_MAP_GROUP === null || pos0.mapGroup === EXPECTED_MAP_GROUP) &&
    (EXPECTED_MAP_NUM   === null || pos0.mapNum   === EXPECTED_MAP_NUM);

  if (EXPECTED_MAP_GROUP !== null && !onExpectedMap) {
    console.error(
      `[hooh-probe] NOT on encounter map (expected ${EXPECTED_MAP_GROUP}.${EXPECTED_MAP_NUM} ` +
      `got ${pos0.mapGroup}.${pos0.mapNum}) — inconclusive`
    );
    console.log(JSON.stringify({
      rom: ROM, slot: SLOT, mapGroup: pos0.mapGroup, mapNum: pos0.mapNum,
      onExpectedMap: false, flagHoOh, flagLugia, verdict: 2,
    }));
    await client.stop();
    process.exit(2);
  }

  // ── Encounter attempt ───────────────────────────────────────────────────
  // Mash A through dialogue/cutscene and watch for freeze.
  let lastHash = '', sameCount = 0, frozen = false, battle = false;

  for (let i = 0; i < MAX_PRESSES; i++) {
    await client.pressKey('A', 4);
    await client.advanceFrames(30);

    const pos = await getPos(client);
    if ((pos as unknown as { inBattle: boolean }).inBattle) battle = true;

    try {
      const imgPath = '/tmp/_hooh_probe_frame.png';
      await client.screenshot(imgPath);
      const h = md5(imgPath);
      if (h && h === lastHash) sameCount++; else { sameCount = 0; lastHash = h; }
    } catch { /* ignore */ }

    if (sameCount >= FREEZE_PRESSES) { frozen = true; break; }

    if (i % 20 === 19) {
      await shot(client, `03-step-${String(i).padStart(3, '0')}`);
      const pos2 = await getPos(client);
      console.error(`[hooh-probe] step ${i}: map=${pos2.mapGroup}.${pos2.mapNum} pos=${pos2.x},${pos2.y} frozen=${frozen} battle=${battle}`);
    }
  }

  await shot(client, '04-final');
  const posF = await getPos(client);

  const verdict = frozen ? 1 : 0;
  console.error(`[hooh-probe] done: frozen=${frozen} battle=${battle} finalMap=${posF.mapGroup}.${posF.mapNum}`);
  console.log(JSON.stringify({
    rom: ROM, slot: SLOT, flagHoOh, flagLugia, flagLugia2,
    startMap: `${pos0.mapGroup}.${pos0.mapNum}`,
    finalMap: `${posF.mapGroup}.${posF.mapNum}`,
    battleTriggered: battle, frozen, verdict,
  }));

  await client.stop();
  process.exit(verdict);
}

main().catch((e) => { console.error('ERR', e); process.exit(3); });
