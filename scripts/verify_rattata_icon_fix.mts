/**
 * verify_rattata_icon_fix.mts — in-engine guard for issue #104.
 *
 * Boots the built FR ROM from the player's battery save (loaded as SRAM), then:
 *  1) reads the party-menu bottom-button Cancel pointer (code literal 0x1211E8)
 *     that the running game uses, and checks it renders « Sortir » (not « Annuler »);
 *  2) sets Rattata's experience 1 below the L16 threshold, grinds one wild battle so
 *     it levels up, captures the level-up banner's icon tiles from OBJ VRAM, and
 *     verifies that block appears VERBATIM in the clean source ROM — i.e. the rendered
 *     icon is a real, un-corrupted mon icon (a rotation-corrupted icon would not match).
 *
 * Emits one JSON verdict line on stdout (last line): { reached, iconClean, buttonSortir }.
 *
 * Args: <builtRom> <sourceRom>.  The <builtRom>.sav (battery save) must sit next to it.
 */
import fs from 'fs';
import path from 'path';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.js';

const ROM = process.argv[2] ?? 'output/roms/GenedRom-fr.gba';
const SOURCE = process.argv[3] ?? 'input/roms/patchedfrenchrom.gba';
const PARTY = 0x02024284, SLOT = 4;
const EXP_OFF = PARTY + SLOT * 100 + 0x24, LVL_OFF = PARTY + SLOT * 100 + 0x54;
const PARTY_CANCEL_PTR = 0x081211E8;
const SORTIR = Buffer.from([0xcd, 0xe3, 0xe6, 0xe8, 0xdd, 0xe6, 0xff]); // "Sortir"+FF
const BANNER_ICON_TILE = 277;

function u32(b: Uint8Array, o = 0): number { return (b[o] | (b[o + 1] << 8) | (b[o + 2] << 16) | (b[o + 3] << 24)) >>> 0; }
async function pos(c: MgbaBridgeClient): Promise<[number, number]> { const s = await c.getState(); return [s.playerX as number, s.playerY as number]; }
async function readBig(c: MgbaBridgeClient, a: number, n: number): Promise<Uint8Array> {
  const out = new Uint8Array(n);
  for (let o = 0; o < n; o += 4096) out.set(await c.readMemory(a + o, Math.min(4096, n - o)), o);
  return out;
}

async function main(): Promise<void> {
  const source = fs.readFileSync(path.resolve(SOURCE));
  const c = new MgbaBridgeClient();
  await c.startMgba(path.resolve(ROM));
  await c.advanceFrames(300);
  for (const f of [60, 60, 120, 120]) { await c.pressKey('A', 4); await c.advanceFrames(f); }

  // (1) party-menu bottom button: read the live Cancel literal + its target string.
  const ptr = u32(await c.readMemory(PARTY_CANCEL_PTR, 4));
  let buttonSortir = false;
  if (ptr >= 0x08000000 && ptr < 0x0a000000) {
    const s = await c.readMemory(ptr, SORTIR.length);
    buttonSortir = Buffer.from(s).equals(SORTIR);
  }

  // (2) force + capture the Rattata level-up banner icon.
  await c.writeMemory(EXP_OFF, new Uint8Array([0xff, 0x0f, 0, 0])); // 4095
  const lvBefore = (await c.readMemory(LVL_OFF, 1))[0];
  for (let t = 0; t < 6; t++) { await c.pressKey('LEFT', 8); await c.advanceFrames(18); }
  // Short oscillating runs keep the player inside the small grass pocket (wandering
  // farther walks onto non-encounter cave tiles); farms wild encounters to level up.
  const runs = ['DOWN', 'RIGHT', 'UP', 'LEFT', 'DOWN', 'LEFT', 'UP', 'RIGHT'] as const;
  let reached = false, iconClean = false;
  for (let i = 0; i < 700 && !reached; i++) {
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
          // step through the message; the banner slides in — sample a few frames.
          for (let k = 0; k < 8 && !iconClean; k++) {
            await c.pressKey('A', 3); await c.advanceFrames(8);
            const vram = await readBig(c, 0x06010000 + BANNER_ICON_TILE * 32, 512);
            if (Buffer.from(vram).some(b => b !== 0) && source.includes(Buffer.from(vram))) {
              iconClean = true; // rendered tiles exist verbatim in the clean source ROM
            }
          }
          break;
        }
        const [px, py] = await pos(c);
        if (px !== x1 || py !== y1) break;
      }
    }
  }
  const [fx, fy] = await pos(c);
  await c.stop();
  console.log(JSON.stringify({ rom: ROM.split('/').pop(), reached, iconClean, buttonSortir, lvBefore, finalPos: `${fx},${fy}` }));
}

main().catch((e) => {
  console.log(JSON.stringify({ verdict: 'ERROR', reached: false, iconClean: false, buttonSortir: false, err: String(e).slice(0, 160) }));
  process.exit(0);
});
