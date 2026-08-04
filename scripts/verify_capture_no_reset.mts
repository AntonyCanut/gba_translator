/**
 * In-engine reset guard for the wild-capture flow (ticket « Capture reset game »).
 *
 * Repro: on the buggy build, catching any wild Pokémon shows the new-species
 * Pokédex page and then REBOOTS the game to the title screen (the pc_move_labels
 * patch had repointed the literal-pool word at 0xC12E0, which the capture/nickname
 * flow uses as the base of a terminator-walked string family).
 *
 * The script stages the ROM plus the committed fixtures in a temp dir
 * (capture_reset.sav + capture_reset.ss0 — a savestate on the battle action menu
 * with Poké Balls in the bag), loads savestate slot 0, throws a Poké Ball
 * (Right → A opens the bag, Right ×2 selects the Poké Balls pocket, A + A uses
 * the ball — the capture is deterministic from the savestate), then presses
 * through the exp/level-up/Pokédex sequence, declining the nickname with B.
 *
 * Verdict signal — the PARTY, not the screen: a successful capture appends the
 * caught mon to gPlayerParty (0x02024284, 100-byte slots, personality != 0 for
 * an occupied slot). A reboot re-loads the battery save, whose party does NOT
 * contain the caught mon (the probe never saves in-game). So:
 *   - occupied slots == start+1 at the end          → OK
 *   - party grew, then returned to its initial size → RESET
 *   - party never grew                              → NOT_REACHED
 *
 * The third state matters when a committed savestate drifts from a rebuilt
 * ROM: menu inputs can still change the screen without ever throwing the ball.
 * Without observing the caught Pokémon at least once, an unchanged final party
 * cannot prove a reboot; treating it as RESET produced false positives after
 * harmless string relocation changed the savestate's ROM layout.
 *
 * Output: one JSON line
 * {rom, verdict, reached, reset, partyBefore, partyAfter, maxParty}.
 * Usage: MGBA_PATH=... emulator-web/node_modules/.bin/tsx \
 *          scripts/verify_capture_no_reset.mts <rom.gba>
 */
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.ts';
import crypto from 'crypto';
import fs from 'fs';
import os from 'os';
import path from 'path';

const ROM = process.argv[2] ?? 'output/roms/GenedRom-fr.gba';
const FIXTURES = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..', 'tests', 'fixtures', 'saves');
const PARTY = 0x02024284;
const PARTY_SLOTS = 6;
const PARTY_STRIDE = 100;

const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'capture-reset-'));
const md5 = (p: string) => crypto.createHash('md5').update(fs.readFileSync(p)).digest('hex');

async function occupiedSlots(c: MgbaBridgeClient): Promise<number> {
  let n = 0;
  for (let i = 0; i < PARTY_SLOTS; i++) {
    const d = await c.readMemory(PARTY + i * PARTY_STRIDE, 4);
    if ((d[0] | d[1] | d[2] | d[3]) !== 0) n++;
  }
  return n;
}

async function main() {
  // Stage ROM + fixtures under one basename so mGBA finds .sav/.ss0 next to it.
  const rom = path.join(TMP, 'capture.gba');
  fs.copyFileSync(path.resolve(ROM), rom);
  fs.copyFileSync(path.join(FIXTURES, 'capture_reset.sav'), path.join(TMP, 'capture.sav'));
  fs.copyFileSync(path.join(FIXTURES, 'capture_reset.ss0'), path.join(TMP, 'capture.ss0'));

  const c = new MgbaBridgeClient();
  let reached = false;
  let reset = false;
  let partyBefore = -1;
  let partyAfter = -1;
  let maxParty = -1;
  let tag = '';
  try {
    await c.startMgba(rom);
    await c.advanceFrames(180);
    await c.loadState(0);
    await c.advanceFrames(30);
    partyBefore = await occupiedSlots(c);
    maxParty = partyBefore;

    await c.screenshot(path.join(TMP, 'menu.png'));
    const menuHash = md5(path.join(TMP, 'menu.png'));

    // Battle menu → bag → Poké Balls pocket → throw the ball.
    const throwSeq: Array<[string, number]> = [
      ['Right', 30], ['A', 90],            // open the bag (« Cube »)
      ['Right', 40], ['Right', 40],        // Poké Balls pocket, ball highlighted
      ['A', 120], ['A', 240],              // select + « Utiliser » (throw)
    ];
    for (const [key, frames] of throwSeq) {
      await c.pressKey(key, 4);
      await c.advanceFrames(frames);
    }
    await c.advanceFrames(360);            // capture animation
    maxParty = Math.max(maxParty, await occupiedSlots(c));

    // Exp gain / level-up / Pokédex page / nickname prompt (declined with B).
    const followSeq = 'AAAABAABAABAAABAAABAAA'.split('');
    for (let i = 0; i < followSeq.length; i++) {
      await c.pressKey(followSeq[i], 4);
      await c.advanceFrames(60);
      maxParty = Math.max(maxParty, await occupiedSlots(c));
      if (!reached) {
        await c.screenshot(path.join(TMP, 'p.png'));
        if (md5(path.join(TMP, 'p.png')) !== menuHash) reached = true;
      }
    }
    await c.advanceFrames(120);
    partyAfter = await occupiedSlots(c);
    maxParty = Math.max(maxParty, partyAfter);

    if (partyBefore < 1 || partyBefore >= PARTY_SLOTS) {
      tag += ' badPartyBefore';
    } else if (maxParty <= partyBefore) {
      tag += ' captureNotObserved';
    } else if (partyAfter < maxParty) {
      reset = true;
    }
  } catch (e) {
    tag += ' EXC=' + String((e as Error).message || e).slice(0, 80);
    // A hang/crash mid-sequence after the flow started is the bug too.
    if (reached) reset = true;
  }
  const verdict = reset
    ? 'RESET'
    : !reached || partyBefore < 1 || maxParty <= partyBefore
      ? 'NOT_REACHED'
      : 'OK';
  console.log(JSON.stringify({
    rom: path.basename(ROM), verdict, reached, reset,
    partyBefore, partyAfter, maxParty, tag,
  }));
  try { await c.stop(); } catch { /* ignore */ }
  try { fs.rmSync(TMP, { recursive: true, force: true }); } catch { /* ignore */ }
  process.exit(verdict === 'RESET' ? 1 : 0);
}

main().catch((e) => {
  console.log(JSON.stringify({ verdict: 'ERROR', err: String(e).slice(0, 120) }));
  process.exit(2);
});
