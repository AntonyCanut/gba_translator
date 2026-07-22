/**
 * probe_levelup_nd_dot.mts — screenshot the in-battle level-up notification box
 * for issue #138 follow-up (dot's grey shadow pixels wrong/missing).
 *
 * Boots the built FR ROM from the player's battery save, sets a party member's
 * exp 1 below its next level threshold, farms wild battles until it levels up,
 * and screenshots the level-up banner ("N.xx") a few times while it's on screen.
 *
 * Args: <builtRom> <outDir>
 */
import path from 'path';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.js';

const ROM = path.resolve(process.argv[2] ?? 'output/roms/GenedRom-fr.gba');
const OUTDIR = process.argv[3] ?? '/tmp/issue138';
const PARTY = 0x02024284, SLOT = 4;
const EXP_OFF = PARTY + SLOT * 100 + 0x24, LVL_OFF = PARTY + SLOT * 100 + 0x54;

async function pos(c: MgbaBridgeClient): Promise<[number, number]> { const s = await c.getState(); return [s.playerX as number, s.playerY as number]; }

async function main(): Promise<void> {
  const c = new MgbaBridgeClient();
  await c.startMgba(ROM);
  await c.advanceFrames(300);
  for (const f of [60, 60, 120, 120]) { await c.pressKey('A', 4); await c.advanceFrames(f); }

  await c.writeMemory(EXP_OFF, new Uint8Array([0xff, 0x0f, 0, 0])); // 4095
  const lvBefore = (await c.readMemory(LVL_OFF, 1))[0];
  for (let t = 0; t < 6; t++) { await c.pressKey('LEFT', 8); await c.advanceFrames(18); }
  const runs = ['DOWN', 'RIGHT', 'UP', 'LEFT', 'DOWN', 'LEFT', 'UP', 'RIGHT'] as const;
  let reached = false;
  for (let i = 0; i < 700 && !reached; i++) {
    if (i % 20 === 0) console.log(JSON.stringify({ progress: i }));
    const [x0, y0] = await pos(c);
    const dir = runs[i % runs.length];
    for (let s = 0; s < 4; s++) { await c.pressKey(dir, 8); await c.advanceFrames(16); }
    const [x1, y1] = await pos(c);
    if (x0 === x1 && y0 === y1) {
      for (let turn = 0; turn < 30; turn++) {
        await c.pressKey('A', 4); await c.advanceFrames(24);
        await c.pressKey('A', 4); await c.advanceFrames(24);
        await c.advanceFrames(22);
        if ((await c.readMemory(LVL_OFF, 1))[0] > lvBefore) {
          reached = true;
          for (let k = 0; k < 10; k++) {
            await c.advanceFrames(10);
            await c.screenshot(path.join(OUTDIR, `levelup_${k}.png`));
          }
          break;
        }
        const [px, py] = await pos(c);
        if (px !== x1 || py !== y1) break;
      }
    }
  }
  console.log(JSON.stringify({ reached }));
  await c.stop();
}

main().catch((e) => { console.error('[probe] FATAL', e); process.exit(1); });
