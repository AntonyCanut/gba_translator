/**
 * probe_accent_healthbox_fr.mts — Render « á » and « é » side by side in a
 * REAL battle healthbox so the small-font acute accent (issue #97) can be
 * compared in-engine against the untouched source accent.
 *
 * The healthbox nickname font is stored in a packed glyph format that no
 * offline decoder in this repo reproduces (naive 4bpp/2bpp reads of the LZ77
 * font blocks give noise for known letters), so the ONLY trustworthy way to
 * see the accent shape is to let the engine draw it. « á » ships pre-drawn in
 * the base international font and is the accent version the user calls
 * correct; « é » is rebuilt by languages/fr/patches/font.py. Rendering both
 * in the same box, same font, same palette gives a pixel-exact target.
 *
 * Strategy: continue rattata_levelup.sav (same battery save as issue #125),
 * overwrite the lead party mon's nickname — the 10 unencrypted bytes at
 * gPlayerParty+8 — with the codepoints for « áéáé », farm a wild encounter,
 * and screenshot the command menu where the player healthbox shows the
 * nickname. Battle detection is by OBJ VRAM content (label_tiles.json from
 * scripts/battle_hp_label_tiles.py), exactly like the #125 probe.
 *
 * Emits one JSON verdict line on stdout: { reached, dumped, category, finalPos }.
 *
 * Run:  tsx scripts/probe_accent_healthbox_fr.mts <romPath> <outDir>
 *   <outDir>/label_tiles.json must exist. The ROM must have its battery .sav
 *   placed next to it beforehand.
 */
import fs from 'fs';
import path from 'path';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.js';

const ROM = path.resolve(process.argv[2] ?? 'output/roms/GenedRom-fr.gba');
const OUT_DIR = path.resolve(process.argv[3] ?? 'output/proofs/accent-healthbox');
// Optional hex-encoded nickname override (max 10 bytes, 0xFF-padded), e.g.
// "1b1a1619d5" renders « éèàça » — used by the glyph-layout decoding probes.
const NICK_HEX = process.argv[4] ?? '171b171b';
fs.mkdirSync(OUT_DIR, { recursive: true });

const TILES = JSON.parse(
  fs.readFileSync(path.join(OUT_DIR, 'label_tiles.json'), 'utf8'),
) as { detect: string[] };
const DETECT = TILES.detect.map((h) => Buffer.from(h, 'hex'));
const OBJ_BASE = 0x06010000;
const OBJ_SIZE = 0x8000;
const TILE = 32;

// gPlayerParty (see scripts/verify_capture_no_reset.mts) — slot 0 nickname is
// the 10 unencrypted bytes at struct offset 8. 0x17 = á, 0x1B = é, 0xFF = EOS.
const PARTY = 0x02024284;
const NICK_OFF = PARTY + 8;
const NICKNAME = new Uint8Array(10).fill(0xff);
Buffer.from(NICK_HEX, 'hex').copy(NICKNAME, 0, 0, Math.min(10, NICK_HEX.length / 2));

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

async function renameLeadMon(client: MgbaBridgeClient): Promise<boolean> {
  await client.writeMemory(NICK_OFF, NICKNAME);
  const back = Buffer.from(await client.readMemory(NICK_OFF, NICKNAME.length));
  const ok = back.equals(Buffer.from(NICKNAME));
  console.error(`[probe] nickname write ok=${ok} bytes=${back.toString('hex')}`);
  return ok;
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

    if (!(await renameLeadMon(client))) {
      return { reached: false, dumped: false, category: 'nickname-write-failed', finalPos: `${st0.playerX},${st0.playerY}` };
    }

    // Bonus shot: the party list (START → POKéMON) renders the same nickname
    // in the antialiased party font — the « Hélionceau » complaint surface.
    await client.pressKey('START', 4); await client.advanceFrames(40);
    await client.pressKey('A', 4); await client.advanceFrames(90);
    await shot(client, '02b-party-menu');
    for (let i = 0; i < 4; i++) { await client.pressKey('B', 4); await client.advanceFrames(30); }

    const runs = ['DOWN', 'RIGHT', 'UP', 'LEFT', 'DOWN', 'LEFT', 'UP', 'RIGHT'] as const;
    for (let i = 0; i < 600; i++) {
      const [x0, y0] = await pos(client);
      const dir = runs[i % runs.length];
      for (let s = 0; s < 3; s++) { await client.pressKey(dir, 8); await client.advanceFrames(16); }
      const [x1, y1] = await pos(client);
      if (i % 25 === 0) console.error(`[probe] step ${i}: pos=${x1},${y1}`);
      if (x0 !== x1 || y0 !== y1) continue;

      let detected = false;
      for (let t = 0; t < 4 && !detected; t++) {
        await client.advanceFrames(90);
        detected = labelOnScreen(await readBig(client, OBJ_BASE, OBJ_SIZE));
      }
      if (detected) {
        await client.advanceFrames(60);
        await shot(client, '03-battle-intro');
        // Advance past the wild-appear intro so the PLAYER healthbox (which
        // carries the renamed mon) is on screen at the command menu.
        for (let k = 0; k < 5; k++) { await client.pressKey('A', 4); await client.advanceFrames(40); }
        await client.advanceFrames(120);
        fs.writeFileSync(path.join(OUT_DIR, 'battle-vram-obj.bin'), await readBig(client, OBJ_BASE, OBJ_SIZE));
        fs.writeFileSync(path.join(OUT_DIR, 'battle-pal.bin'), await readBig(client, 0x05000000, 0x400));
        fs.writeFileSync(path.join(OUT_DIR, 'battle-ewram.bin'), await readBig(client, 0x02000000, 0x40000));
        fs.writeFileSync(path.join(OUT_DIR, 'battle-iwram.bin'), await readBig(client, 0x03000000, 0x8000));
        await shot(client, '04-battle-final');
        const [fx, fy] = await pos(client);
        console.error(`[probe] healthbox captured at pos ${fx},${fy}`);
        return { reached: true, dumped: true, category: 'battle', finalPos: `${fx},${fy}` };
      }
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
