/**
 * probe_battle_healthbox_fr.mts — Reach a REAL wild battle and capture the
 * healthbox label so the « HP »→« PV » fix (issue #125) can be verified
 * in-engine, not just at the ROM byte level.
 *
 * The e2e `setupInBattle` helper only *pokes* the inBattle flag — it never
 * runs battle init, so the healthbox label sprite is never decompressed into
 * OBJ VRAM. This probe instead continues the `rattata_levelup.sav` battery
 * save (parked in a tight grass pocket, reused from issue #104) and oscillates
 * to farm wild encounters. The build's `inBattle` RAM byte is unreliable
 * (see tests/fixtures/saves/README.md), so a battle is detected by CONTENT:
 * whenever the player stops moving we sample OBJ VRAM and look for any of the
 * healthbox label tiles (H / P / V, from scripts/battle_hp_label_tiles.py).
 * As soon as a label tile is on screen we let the boxes finish rendering, dump
 * OBJ + BG VRAM and a screenshot, and stop — the offline verifier then asserts
 * the loaded label is « PV », not « HP ».
 *
 * Emits one JSON verdict line on stdout: { reached, dumped, category, finalPos }.
 *
 * Run:  tsx scripts/probe_battle_healthbox_fr.mts <romPath> <outDir>
 *   <outDir>/label_tiles.json (from battle_hp_label_tiles.py) must exist.
 *   The ROM must have its battery .sav placed next to it beforehand.
 */
import fs from 'fs';
import path from 'path';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.js';

const ROM = path.resolve(process.argv[2] ?? 'output/roms/GenedRom-fr.gba');
const OUT_DIR = path.resolve(process.argv[3] ?? 'output/proofs/battle-healthbox');
fs.mkdirSync(OUT_DIR, { recursive: true });

const TILES = JSON.parse(
  fs.readFileSync(path.join(OUT_DIR, 'label_tiles.json'), 'utf8'),
) as { hp_h: string[]; hp_p: string[]; pv_p: string[]; pv_v: string[]; detect: string[] };
const DETECT = TILES.detect.map((h) => Buffer.from(h, 'hex'));
const OBJ_BASE = 0x06010000;
const OBJ_SIZE = 0x8000;
const TILE = 32;

async function shot(client: MgbaBridgeClient, name: string): Promise<void> {
  try {
    await client.screenshot(path.join(OUT_DIR, `${name}.png`));
  } catch (e) {
    console.error(`[shot] ${name} failed: ${String(e)}`);
  }
}

async function readBig(client: MgbaBridgeClient, base: number, size: number): Promise<Buffer> {
  const chunks: Uint8Array[] = [];
  for (let off = 0; off < size; off += 4096) {
    chunks.push(await client.readMemory(base + off, Math.min(4096, size - off)));
  }
  return Buffer.concat(chunks.map((c) => Buffer.from(c)));
}

/** Is any healthbox label tile (32-byte, tile-aligned) present in OBJ VRAM? */
function labelOnScreen(objVram: Buffer): boolean {
  for (const want of DETECT) {
    for (let off = 0; off + TILE <= objVram.length; off += TILE) {
      if (objVram.compare(want, 0, TILE, off, off + TILE) === 0) return true;
    }
  }
  return false;
}

async function pos(c: MgbaBridgeClient): Promise<[number, number]> {
  const s = await c.getState();
  return [Number(s.playerX), Number(s.playerY)];
}

const OPPOSITE: Record<string, 'UP' | 'DOWN' | 'LEFT' | 'RIGHT'> = {
  UP: 'DOWN', DOWN: 'UP', LEFT: 'RIGHT', RIGHT: 'LEFT',
};

async function ensureOverworld(client: MgbaBridgeClient): Promise<boolean> {
  // Continue past the title / save-select menu, then confirm we actually have
  // overworld control by checking a test-walk changes the player position.
  for (const f of [60, 60, 120, 120]) { await client.pressKey('A', 4); await client.advanceFrames(f); }
  for (let attempt = 0; attempt < 8; attempt++) {
    const [x0, y0] = await pos(client);
    for (let s = 0; s < 3; s++) { await client.pressKey('LEFT', 8); await client.advanceFrames(16); }
    const [x1, y1] = await pos(client);
    if (x1 !== x0 || y1 !== y0) return true;
    // Still stuck on a menu/dialog: mash A/B to clear it, then retry.
    for (let a = 0; a < 3; a++) { await client.pressKey('A', 4); await client.advanceFrames(30); }
    await client.pressKey('B', 4); await client.advanceFrames(20);
  }
  return false;
}

async function runOnce(): Promise<{ reached: boolean; dumped: boolean; category: string; finalPos: string }> {
  const client = new MgbaBridgeClient();
  await client.startMgba(ROM);
  try {
    await client.advanceFrames(300);
    await shot(client, '01-title');

    const control = await ensureOverworld(client);
    const st0 = await client.getState();
    console.error(`[probe] control=${control} map=${st0.mapGroup}.${st0.mapNumber} pos=${st0.playerX},${st0.playerY}`);
    await shot(client, '02-overworld');
    if (!control) return { reached: false, dumped: false, category: 'no-control', finalPos: `${st0.playerX},${st0.playerY}` };

    // Oscillate in the grass pocket. When the player stops (encounter OR wall),
    // let a battle intro render and sample OBJ VRAM for a healthbox label.
    const runs = ['DOWN', 'RIGHT', 'UP', 'LEFT', 'DOWN', 'LEFT', 'UP', 'RIGHT'] as const;
    for (let i = 0; i < 600; i++) {
      const [x0, y0] = await pos(client);
      const dir = runs[i % runs.length];
      for (let s = 0; s < 3; s++) { await client.pressKey(dir, 8); await client.advanceFrames(16); }
      const [x1, y1] = await pos(client);
      if (i % 25 === 0) console.error(`[probe] step ${i}: pos=${x1},${y1}`);
      if (x0 !== x1 || y0 !== y1) continue; // moved freely — no battle, no wall

      // Frozen: give a wild-battle intro up to ~360 frames to slide the boxes in.
      let detected = false;
      for (let t = 0; t < 4 && !detected; t++) {
        await client.advanceFrames(90);
        detected = labelOnScreen(await readBig(client, OBJ_BASE, OBJ_SIZE));
      }
      if (detected) {
        await client.advanceFrames(60);
        await shot(client, '03-battle-healthbox');
        // Advance past the wild-appear intro so BOTH healthboxes are on screen
        // at the FIGHT/BAG/POKéMON/RUN command menu.
        for (let k = 0; k < 5; k++) { await client.pressKey('A', 4); await client.advanceFrames(40); }
        await client.advanceFrames(120);
        const obj = await readBig(client, OBJ_BASE, OBJ_SIZE);
        fs.writeFileSync(path.join(OUT_DIR, 'battle-vram-obj.bin'), obj);
        fs.writeFileSync(path.join(OUT_DIR, 'battle-vram-bg.bin'), await readBig(client, 0x06000000, 0x10000));
        fs.writeFileSync(path.join(OUT_DIR, 'battle-oam.bin'), await readBig(client, 0x07000000, 0x400));
        fs.writeFileSync(path.join(OUT_DIR, 'battle-pal.bin'), await readBig(client, 0x05000000, 0x400));
        await shot(client, '04-battle-final');
        const [fx, fy] = await pos(client);
        console.error(`[probe] healthbox captured at pos ${fx},${fy}`);
        return { reached: true, dumped: true, category: 'battle', finalPos: `${fx},${fy}` };
      }
      // Just a wall: back out so the next direction can find open grass.
      const opp = OPPOSITE[dir];
      for (let s = 0; s < 2; s++) { await client.pressKey(opp, 8); await client.advanceFrames(16); }
    }
    const [fx, fy] = await pos(client);
    return { reached: false, dumped: false, category: 'no-battle', finalPos: `${fx},${fy}` };
  } finally {
    await client.stop();
  }
}

async function main(): Promise<void> {
  console.error(`[probe] booting ${ROM}`);
  let last = { reached: false, dumped: false, category: 'init', finalPos: '0,0' };
  // mGBA's bridge occasionally drops the first connection right after boot;
  // retry so the (2-3 s) happy path survives a flaky launch. A persistent
  // "could not connect" means the emulator can't run in this environment
  // (e.g. no display) — the caller treats that as a skip, so keep the retry
  // budget small to fail fast there.
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      last = await runOnce();
      if (last.dumped) break;
    } catch (e) {
      console.error(`[probe] attempt ${attempt} failed: ${String(e).slice(0, 200)}`);
      await new Promise((r) => setTimeout(r, 1500));
    }
  }
  console.log(JSON.stringify(last));
}

main().catch((e) => {
  console.error(e);
  console.log(JSON.stringify({ reached: false, dumped: false, category: 'fatal', finalPos: '0,0', err: String(e).slice(0, 160) }));
  process.exit(0);
});
