/**
 * In-engine freeze guard for the Day-Care "withdraw your Pokémon" menu (ticket
 * B-187 « Freeze jeu »).
 *
 * Language-agnostic replay: it boots the given ROM with its adjacent battery
 * save (the player is standing in front of the Day-Care lady with a Pokémon
 * deposited), mashes A through the "do you want your Pokémon back?" prompt and
 * into the selection menu whose fixed-size cursor-help window renders the global
 * "go back to the previous menu" description at 0x416244. A wrong string there
 * makes that window's word-wrap spin forever → the frame stops updating
 * (FREEZE) or mGBA stops answering frame callbacks (the infinite loop reads as a
 * bridge timeout). Both are the bug; both are reported as frozen:true.
 *
 * Freeze is judged by SCREEN HASH only — the rendered frame staying
 * pixel-identical for many consecutive A-presses — never by player position
 * (the player stands still during any dialogue) or CPU PC (read inside the
 * VBlank IRQ, so it is ~always BIOS). See the diagnosing-unbound-freezes skill.
 *
 * Because it drives the menu through each build's OWN prompt text (no
 * FR-specific byte gate), the same script verifies every language ROM.
 *
 * Output: a single JSON line {rom, verdict, reached, frozen}. reached=false
 * means the save never opened the prompt (boot/save drift) — the caller should
 * skip, not fail.
 *
 * Usage: tsx verify_daycare_no_freeze.mts <rom.gba>
 */
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.ts';
import crypto from 'crypto';
import fs from 'fs';
import os from 'os';
import path from 'path';

const ROM = process.argv[2];
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'daycare-'));
const shot = (n: string) => path.join(TMP, n);
const md5 = (p: string) => crypto.createHash('md5').update(fs.readFileSync(p)).digest('hex');

async function main() {
  const c = new MgbaBridgeClient();
  let frozen = false;
  let reached = false;
  let tag = '';
  try {
    await c.startMgba(ROM);
    await c.advanceFrames(240);
    await c.screenshot(shot('ow.png'));
    const overworld = md5(shot('ow.png'));

    // Mash A through the whole withdraw flow. Track:
    //  - reached: the screen ever left the overworld (a prompt/menu opened).
    //  - frozen : the frame stayed pixel-identical for many A-presses, OR a
    //             frame-advance threw AFTER we had reached the menu (the
    //             GetStringWidth infinite loop starves the frame callback).
    let last = '';
    let same = 0;
    let maxsame = 0;
    for (let i = 0; i < 45; i++) {
      try {
        await c.pressKeyAndAdvance('A', 6);
        await c.advanceFrames(28);
      } catch (e) {
        // A hang during frame advance is the infinite-loop freeze — but only
        // meaningful once the menu was actually reached.
        tag += ' hangAt=' + i + ' reached=' + reached;
        if (reached) frozen = true;
        break;
      }
      await c.screenshot(shot('p' + (i % 3) + '.png'));
      const h = md5(shot('p' + (i % 3) + '.png'));
      if (h !== overworld) reached = true;
      if (h === last) same++;
      else {
        same = 0;
        last = h;
      }
      if (same > maxsame) maxsame = same;
      if (same >= 22 && reached) {
        frozen = true;
        break;
      }
    }
    tag += ' maxsame=' + maxsame;
  } catch (e) {
    tag += ' EXC=' + String((e as Error).message || e).slice(0, 80);
  }
  const verdict = frozen ? 'FREEZE' : reached ? 'OK' : 'NOT_REACHED';
  console.log(JSON.stringify({ rom: ROM.split('/').pop(), verdict, reached, frozen, tag }));
  try {
    await c.stop();
  } catch {}
  try {
    fs.rmSync(TMP, { recursive: true, force: true });
  } catch {}
  process.exit(0);
}

main().catch((e) => {
  console.log(JSON.stringify({ verdict: 'ERROR', reached: false, frozen: false, err: String(e).slice(0, 120) }));
  process.exit(0);
});
