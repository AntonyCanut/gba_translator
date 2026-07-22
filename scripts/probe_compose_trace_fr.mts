/**
 * probe_font_trace_fr.mts — Trace which code reads the lead mon's nickname
 * while the battle healthbox is being drawn, to locate the small-font glyph
 * data the healthbox text renderer actually uses (issue #97).
 *
 * Farms a wild battle like probe_accent_healthbox_fr.mts, but arms a READ
 * range watchpoint on gPlayerParty[0].nickname the moment the player freezes
 * (battle intro starting, healthbox not yet drawn). Every hit records the ARM
 * register file (r15 = reading PC, r14 = caller LR). After the healthbox label
 * tiles land in OBJ VRAM, the hits and an EWRAM dump (to find nickname copies)
 * are written to <outDir>.
 *
 * Run:  tsx scripts/probe_font_trace_fr.mts <romPath> <outDir>
 *   <outDir>/label_tiles.json must exist; battery .sav next to the ROM.
 */
import fs from 'fs';
import path from 'path';
import { MgbaBridgeClient, WatchHit } from '../emulator-web/src/mgba-bridge.js';

const ROM = path.resolve(process.argv[2] ?? 'output/roms/GenedRom-fr.gba');
const OUT_DIR = path.resolve(process.argv[3] ?? 'output/proofs/font-trace');
fs.mkdirSync(OUT_DIR, { recursive: true });

const TILES = JSON.parse(
  fs.readFileSync(path.join(OUT_DIR, 'label_tiles.json'), 'utf8'),
) as { detect: string[] };
const DETECT = TILES.detect.map((h) => Buffer.from(h, 'hex'));
const OBJ_BASE = 0x06010000;
const OBJ_SIZE = 0x8000;
const TILE = 32;

const PARTY = 0x02024284;
const NICK_OFF = PARTY + 8;
const NICKNAME = new Uint8Array([0x17, 0x1b, 0x17, 0x1b, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff]);

async function readBig(client: MgbaBridgeClient, base: number, size: number): Promise<Buffer> {
  const chunks: Uint8Array[] = [];
  for (let off = 0; off < size; off += 4096) {
    chunks.push(await client.readMemory(base + off, Math.min(4096, size - off)));
  }
  return Buffer.concat(chunks.map((c) => Buffer.from(c)));
}

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
  for (const f of [60, 60, 120, 120]) { await client.pressKey('A', 4); await client.advanceFrames(f); }
  for (let attempt = 0; attempt < 8; attempt++) {
    const [x0, y0] = await pos(client);
    for (let s = 0; s < 3; s++) { await client.pressKey('LEFT', 8); await client.advanceFrames(16); }
    const [x1, y1] = await pos(client);
    if (x1 !== x0 || y1 !== y0) return true;
    for (let a = 0; a < 3; a++) { await client.pressKey('A', 4); await client.advanceFrames(30); }
    await client.pressKey('B', 4); await client.advanceFrames(20);
  }
  return false;
}

async function main(): Promise<void> {
  const client = new MgbaBridgeClient();
  await client.startMgba(ROM);
  try {
    await client.advanceFrames(300);
    if (!(await ensureOverworld(client))) { console.log('{"ok":false,"why":"no-control"}'); return; }
    await client.writeMemory(NICK_OFF, NICKNAME);
    console.error('[trace] nickname set to éééé');
    const caps = await client.capabilities();
    console.error(`[trace] caps: ${JSON.stringify(caps)}`);

    const runs = ['DOWN', 'RIGHT', 'UP', 'LEFT', 'DOWN', 'LEFT', 'UP', 'RIGHT'] as const;
    const allHits: WatchHit[] = [];
    for (let i = 0; i < 600; i++) {
      const [x0, y0] = await pos(client);
      const dir = runs[i % runs.length];
      for (let s = 0; s < 3; s++) { await client.pressKey(dir, 8); await client.advanceFrames(16); }
      const [x1, y1] = await pos(client);
      if (x0 !== x1 || y0 !== y1) continue;

      // Frozen: arm the read watchpoint BEFORE the healthbox renders.
      await client.clearWatchHits();
      const wpId = await client.setRangeWatchpoint(0x02018300, 0x02018600, 'W');
      console.error(`[trace] frozen at step ${i}; read-watchpoint id=${wpId} armed`);
      let rendered = false;
      for (let t = 0; t < 10 && !rendered; t++) {
        await client.advanceFrames(60);
        allHits.push(...await client.drainWatchHits());
        rendered = labelOnScreen(await readBig(client, OBJ_BASE, OBJ_SIZE));
        console.error(`[trace] t=${t} hits so far=${allHits.length} rendered=${rendered}`);
      }
      if (!rendered) { console.error('[trace] wall, not a battle — but hits collected; backing out');
        const opp = OPPOSITE[dir];
        for (let s = 0; s < 2; s++) { await client.pressKey(opp, 8); await client.advanceFrames(16); }
        continue;
      }
      await client.advanceFrames(60);
      allHits.push(...await client.drainWatchHits());
      fs.writeFileSync(path.join(OUT_DIR, 'hits.json'), JSON.stringify(allHits, null, 1));
      await client.screenshot(path.join(OUT_DIR, 'battle.png'));
      // summary: unique (pc, lr) with counts
      const summary = new Map<string, number>();
      for (const h of allHits) {
        const k = `pc=${(h.regs.r15 ?? 0).toString(16)} lr=${(h.regs.r14 ?? 0).toString(16)} addr=${h.addr.toString(16)}`;
        summary.set(k, (summary.get(k) ?? 0) + 1);
      }
      const top = [...summary.entries()].sort((a, b) => b[1] - a[1]).slice(0, 40);
      console.log(JSON.stringify({ ok: true, hits: allHits.length, top }, null, 1));
      return;
    }
    console.log('{"ok":false,"why":"no-battle"}');
  } finally {
    await client.stop();
  }
}

main().catch((e) => { console.error(e); console.log(JSON.stringify({ ok: false, err: String(e).slice(0, 200) })); process.exit(0); });
