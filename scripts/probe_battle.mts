/**
 * probe_battle.mts — Battle-start crash reproducer (Hoopa bridge scene).
 *
 * Boots a ROM, continues the existing save (parked on the Crystal Peak bridge
 * cinematic), mashes A through the whole cutscene until the scripted Hoopa
 * battle starts, then monitors the game state for a console-reset signature
 * (saveblock pointer invalidated / map flip with zeroed coords).
 *
 * Run:  npx tsx scripts/probe_battle.mts [romPath] [tag]
 */
import fs from 'fs';
import path from 'path';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.js';

const ROM = path.resolve(process.argv[2] ?? 'output/roms/GenedRom-fr.gba');
const TAG = process.argv[3] ?? 'cur';
const OUT_DIR = path.resolve('output/proofs/battle-probe');
fs.mkdirSync(OUT_DIR, { recursive: true });

async function shot(client: MgbaBridgeClient, name: string): Promise<void> {
  try {
    await client.screenshot(path.join(OUT_DIR, `${TAG}-${name}.png`));
  } catch (e) {
    console.error(`[shot] ${name} failed: ${String(e)}`);
  }
}

async function sb1Ptr(client: MgbaBridgeClient): Promise<number> {
  const d = await client.readMemory(0x03005008, 4);
  return (d[0] | (d[1] << 8) | (d[2] << 16) | (d[3] << 24)) >>> 0;
}

async function main(): Promise<void> {
  const client = new MgbaBridgeClient();
  console.error(`[probe] booting ${ROM}`);
  await client.startMgba(ROM);

  await client.advanceFrames(600);
  await shot(client, '01-title');

  await client.pressKey('START', 4);
  await client.advanceFrames(120);
  await client.pressKey('A', 4);
  await client.advanceFrames(180);
  await client.pressKey('A', 4);
  await client.advanceFrames(180);

  let st = await client.getState();
  console.error(`[probe] after continue: map=${st.mapGroup}.${st.mapNumber} pos=${st.playerX},${st.playerY}`);
  await shot(client, '02-loaded');

  let battle = false;
  let reset = false;
  let battleSteps = 0;
  let lastGoodMap = `${st.mapGroup}.${st.mapNumber}`;
  const dirs = ['UP', 'LEFT', 'DOWN', 'RIGHT'] as const;
  for (let i = 0; i < 900; i++) {
    if (!st.textActive && !st.inBattle && i % 3 === 2) {
      // Overworld with no textbox: take a few steps to make progress.
      const dir = dirs[(i / 3 | 0) % dirs.length];
      for (let s = 0; s < 4; s++) {
        await client.pressKey(dir, 4);
        await client.advanceFrames(14);
      }
    }
    await client.pressKey('A', 4);
    await client.advanceFrames(40);
    st = await client.getState();
    const ptr = await sb1Ptr(client);
    const badPtr = !(ptr >= 0x02000000 && ptr < 0x03000000);
    if (badPtr) {
      reset = true;
      console.error(`[probe] RESET detected at press ${i} (sb1=0x${ptr.toString(16)}, lastMap=${lastGoodMap})`);
      await shot(client, `0X-reset-${i}`);
      break;
    }
    if (st.inBattle && !battle) {
      battle = true;
      console.error(`[probe] BATTLE started at press ${i} map=${st.mapGroup}.${st.mapNumber}`);
      await shot(client, `04-battle-start`);
    }
    if (st.inBattle) battleSteps++;
    if (!st.inBattle) lastGoodMap = `${st.mapGroup}.${st.mapNumber}`;
    if (i % 25 === 0) {
      console.error(`[probe] press ${i}: map=${st.mapGroup}.${st.mapNumber} pos=${st.playerX},${st.playerY} battle=${st.inBattle} text=${st.textActive}`);
      await shot(client, `03-step-${String(i).padStart(3, '0')}`);
    }
    if (battle && st.inBattle && battleSteps % 5 === 1) await shot(client, `05-battle-${String(i).padStart(3, '0')}`);
    if (battle && battleSteps > 40) break;
  }

  await shot(client, '06-final');
  st = await client.getState();
  console.error(`[probe] done: battle=${battle} reset=${reset} finalMap=${st.mapGroup}.${st.mapNumber}`);
  console.log(JSON.stringify({ rom: ROM, tag: TAG, battleTriggered: battle, resetDetected: reset, finalState: st }));
  await client.stop();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
