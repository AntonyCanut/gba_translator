/**
 * probe_drive.mts — scripted emulator driver with savestate checkpoints.
 *
 * Executes a compact command list against a booted ROM, with battle/reset
 * detection after every command. Commands (comma separated):
 *   boot         advance 600 frames (title)
 *   cont         START+A+A continue sequence
 *   mash<n>      n A-presses (40 frames each)
 *   U<n> D<n> L<n> R<n>   n directional steps
 *   save<s> load<s>       mGBA savestate slot s
 *   shot:<name>  screenshot
 *   wait<n>      advance n frames
 *
 * Run: npx tsx scripts/probe_drive.mts <romPath> <tag> "cont,mash250,save1"
 */
import fs from 'fs';
import path from 'path';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.js';

const ROM = path.resolve(process.argv[2]);
const TAG = process.argv[3] ?? 'drv';
const SCRIPT = (process.argv[4] ?? '').split(',').map((s) => s.trim()).filter(Boolean);
const OUT_DIR = path.resolve('output/proofs/battle-probe');
fs.mkdirSync(OUT_DIR, { recursive: true });

const DIRKEYS: Record<string, string> = { U: 'UP', D: 'DOWN', L: 'LEFT', R: 'RIGHT' };

async function main(): Promise<void> {
  const client = new MgbaBridgeClient();
  await client.startMgba(ROM);
  let battle = false;
  let reset = false;

  const check = async (label: string): Promise<boolean> => {
    const st = await client.getState();
    const d = await client.readMemory(0x03005008, 4);
    const ptr = ((d[0] | (d[1] << 8) | (d[2] << 16) | (d[3] << 24)) >>> 0);
    const badPtr = !(ptr >= 0x02000000 && ptr < 0x03000000);
    console.error(`[${label}] map=${st.mapGroup}.${st.mapNumber} pos=${st.playerX},${st.playerY} battle=${st.inBattle} text=${st.textActive} sb1=0x${ptr.toString(16)}`);
    if (badPtr) {
      reset = true;
      console.error(`[${label}] !!! RESET DETECTED`);
      await client.screenshot(path.join(OUT_DIR, `${TAG}-RESET-${label.replace(/[^a-z0-9]/gi, '_')}.png`));
      return false;
    }
    if (st.inBattle && !battle) {
      battle = true;
      console.error(`[${label}] >>> BATTLE STARTED`);
      await client.screenshot(path.join(OUT_DIR, `${TAG}-BATTLE-${label.replace(/[^a-z0-9]/gi, '_')}.png`));
    }
    return true;
  };

  outer: for (const cmd of SCRIPT) {
    let m;
    if (cmd === 'boot') {
      await client.advanceFrames(600);
    } else if (cmd === 'cont') {
      await client.pressKey('START', 4); await client.advanceFrames(120);
      await client.pressKey('A', 4); await client.advanceFrames(180);
      await client.pressKey('A', 4); await client.advanceFrames(180);
    } else if ((m = cmd.match(/^mash(\d+)$/))) {
      const n = parseInt(m[1]);
      for (let i = 0; i < n; i++) {
        await client.pressKey('A', 4);
        await client.advanceFrames(40);
        if (i % 20 === 19 && !(await check(`${cmd}@${i}`))) break outer;
        if (battle) { await check(`${cmd}@${i}`); }
      }
    } else if ((m = cmd.match(/^([UDLR])(\d+)$/))) {
      const key = DIRKEYS[m[1]];
      const n = parseInt(m[2]);
      for (let i = 0; i < n; i++) {
        await client.pressKey(key, 4);
        await client.advanceFrames(14);
      }
    } else if ((m = cmd.match(/^mashshot(\d+)$/))) {
      const n = parseInt(m[1]);
      for (let i = 0; i < n; i++) {
        await client.pressKey('A', 4);
        await client.advanceFrames(45);
        await client.screenshot(path.join(OUT_DIR, `${TAG}-ms-${String(i).padStart(3, '0')}.png`));
        if (i % 5 === 4 && !(await check(`${cmd}@${i}`))) break outer;
      }
    } else if ((m = cmd.match(/^save(\d)$/))) {
      await client.saveState(parseInt(m[1]));
    } else if ((m = cmd.match(/^load(\d)$/))) {
      await client.loadState(parseInt(m[1]));
      await client.advanceFrames(10);
    } else if ((m = cmd.match(/^key:([A-Z]+)$/))) {
      await client.pressKey(m[1], 4);
      await client.advanceFrames(60);
    } else if ((m = cmd.match(/^shot:(.+)$/))) {
      await client.screenshot(path.join(OUT_DIR, `${TAG}-${m[1]}.png`));
    } else if ((m = cmd.match(/^wait(\d+)$/))) {
      await client.advanceFrames(parseInt(m[1]));
    } else if ((m = cmd.match(/^mem:([0-9a-fA-Fx]+):(\d+)$/))) {
      const addr = parseInt(m[1], 16);
      const len = parseInt(m[2]);
      const bytes = await client.readMemory(addr, len);
      console.error(`[mem 0x${addr.toString(16)}] ${Array.from(bytes).map((b) => b.toString(16).padStart(2, '0')).join(' ')}`);
    } else if ((m = cmd.match(/^explore(i?)(\d+)$/))) {
      const interact = m[1] === 'i';
      const n = parseInt(m[2]);
      const dirNames = ['UP', 'DOWN', 'LEFT', 'RIGHT'];
      const visited = new Set<string>();
      let rngState = 0x9e3779b9 | 0;
      const rng = () => { rngState = (Math.imul(rngState, 1103515245) + 12345) & 0x7fffffff; return rngState >>> 16; };
      let lastKey = '';
      let stuck = 0;
      for (let i = 0; i < n; i++) {
        const st0 = await client.getState();
        const key = `${st0.mapGroup}.${st0.mapNumber}:${st0.playerX},${st0.playerY}`;
        visited.add(key);
        if (key === lastKey) stuck++; else stuck = 0;
        lastKey = key;
        if (stuck > 0 && stuck % 6 === 0) {
          // a dialog may hold the player: page through it with B (never opens one)
          for (let k = 0; k < 8; k++) {
            await client.pressKey('B', 4);
            await client.advanceFrames(30);
          }
        }
        const dir = dirNames[rng() % 4];
        for (let s = 0; s < 2 + (rng() % 5); s++) {
          await client.pressKey(dir, 4);
          await client.advanceFrames(14);
        }
        if (interact) {
          await client.pressKey('A', 4);
          await client.advanceFrames(30);
          await client.pressKey('B', 4);
          await client.advanceFrames(20);
          await client.pressKey('B', 4);
          await client.advanceFrames(20);
        }
        if (i % 5 === 4) {
          if (!(await check(`explore@${i}`))) break outer;
          if (battle) {
            await client.screenshot(path.join(OUT_DIR, `${TAG}-explore-battle-${i}.png`));
            for (let k = 0; k < 30; k++) {
              await client.pressKey('A', 4);
              await client.advanceFrames(50);
              if (!(await check(`battlewatch@${i}.${k}`))) break outer;
              if (k % 5 === 0) await client.screenshot(path.join(OUT_DIR, `${TAG}-battlewatch-${k}.png`));
            }
            break;
          }
        }
        if (i % 5 === 4) await client.screenshot(path.join(OUT_DIR, `${TAG}-explore-${i}.png`));
      }
      console.error(`[explore] distinct tiles: ${visited.size}`);
    } else {
      console.error(`[drive] unknown command: ${cmd}`);
    }
    if (!(await check(cmd))) break;
  }

  await client.screenshot(path.join(OUT_DIR, `${TAG}-final.png`));
  console.log(JSON.stringify({ rom: ROM, tag: TAG, battle, reset }));
  await client.stop();
}

main().catch((e) => { console.error(e); process.exit(1); });
