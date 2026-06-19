/**
 * probe_volcan_freeze.mts — reproduce the "Volcan Cendre" item-pickup freeze
 * from the user's battery save. Boots <rom> (mGBA auto-loads <rom>.sav),
 * presses through the title → Continue, walks to the Poké Ball item to the
 * lower-left, picks it up and judges a freeze by SCREEN HASH (the only reliable
 * signal — see the diagnosing-unbound-freezes skill).
 *
 * Run: MGBA_PATH=/opt/homebrew/bin/mgba \
 *   <main>/emulator-web/node_modules/.bin/tsx scripts/probe_volcan_freeze.mts <rom>
 */
import path from 'path';
import fs from 'fs';
import crypto from 'crypto';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.ts';
import { decodePokemonText } from '../tests/e2e-playwright/helpers/charmap.js';

const ROM = path.resolve(process.argv[2] ?? '/tmp/freeze/repro.gba');
const OUT = '/tmp/freeze';
const FREEZE_PRESSES = 40;

function md5(p: string) { try { return crypto.createHash('md5').update(fs.readFileSync(p)).digest('hex'); } catch { return ''; } }

async function pos(c: MgbaBridgeClient) {
  const s = await c.getState();
  return { tag: `${s.mapGroup}.${s.mapNumber}:${s.playerX},${s.playerY}`, x: Number(s.playerX), y: Number(s.playerY), map: `${s.mapGroup}.${s.mapNumber}` };
}

async function sv4(c: MgbaBridgeClient) {
  const raw = await c.readMemory(0x02021D18, 1000);
  const hex = Array.from(raw.slice(0, 120)).map((b) => b.toString(16).padStart(2, '0')).join(' ');
  return { text: decodePokemonText(raw).trim(), hex };
}

async function step(c: MgbaBridgeClient, dir: string, n = 1) {
  for (let i = 0; i < n; i++) { await c.pressKey(dir, 16); await c.advanceFrames(10); }
}

// Walk toward the item by driving x down to targetX (ball is to the left),
// nudging y when a row is blocked. Returns true once x stops changing at/near target.
async function walkToBall(c: MgbaBridgeClient) {
  let prev = await pos(c);
  for (let i = 0; i < 24; i++) {
    await step(c, 'LEFT', 1);
    let p = await pos(c);
    if (p.x === prev.x) {
      // blocked horizontally — try slipping down then left, then up then left
      await step(c, 'DOWN', 1); await step(c, 'LEFT', 1);
      p = await pos(c);
      if (p.x === prev.x) { await step(c, 'UP', 1); await step(c, 'LEFT', 1); p = await pos(c); }
    }
    console.error(`  walk[${i}] ${p.tag}`);
    if (p.x === prev.x && p.y === prev.y && i > 2) break; // fully stuck (likely facing the ball)
    prev = p;
  }
}

async function main() {
  const c = new MgbaBridgeClient();
  await c.startMgba(ROM);
  await c.advanceFrames(220);

  // Title -> Continue. Press START then A a few times to load the save.
  for (let i = 0; i < 6; i++) { await c.pressKey('A', 6); await c.advanceFrames(40); }
  const inGame = await pos(c);
  console.error(`[probe] in-game ${inGame.tag}`);
  await c.screenshot(`${OUT}/10-ingame.png`);

  // The Poké Ball sits to the left on open floor. Walk left onto it.
  await walkToBall(c);
  await c.screenshot(`${OUT}/11-atball.png`);

  // Pick it up + advance through the gain dialogue, watching for a freeze.
  let lastHash = '', same = 0, frozen = false, gain = '';
  for (let i = 0; i < 80; i++) {
    await c.pressKey('A', 4);
    await c.advanceFrames(30);
    const s = await sv4(c);
    if (s.text && /obten|trouv|re.u|gain|got|found|ball|potion|.+/i.test(s.text) && s.text.length > 3 && !gain) {
      gain = s.text;
    }
    let h = '';
    try { await c.screenshot(`${OUT}/_f.png`); h = md5(`${OUT}/_f.png`); } catch { /* */ }
    if (h && h === lastHash) same++; else { same = 0; lastHash = h; }
    if (same === 6) {
      const s2 = await sv4(c);
      console.error(`  [${i}] screen stable, sv4="${s2.text.slice(0, 90)}"`);
      console.error(`       hex=${s2.hex}`);
    }
    if (same >= FREEZE_PRESSES) { frozen = true; break; }
  }

  const final = await pos(c);
  const s = await sv4(c);
  await c.screenshot(`${OUT}/12-final.png`);
  console.error(`[probe] final ${final.tag} frozen=${frozen} gain="${gain}"`);
  console.error(`[probe] sv4="${s.text}"`);
  console.error(`[probe] hex=${s.hex}`);
  console.log(JSON.stringify({ rom: ROM, inGame: inGame.tag, final: final.tag, frozen, gain, sv4: s.text }));
  await c.stop();
  process.exit(frozen ? 1 : 0);
}
main().catch((e) => { console.error('ERR', e); process.exit(3); });
