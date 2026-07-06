/**
 * probe_naming_cancel.mts — Continue past the player-naming keyboard (ticket
 * F-109) toward the starter-Pokémon selection / nickname screen, where a
 * graphical CANCEL button is hypothesized to live (ticket F-110).
 *
 * Reuses the known-good New-Game path recorded from prior probing sessions
 * (see memory unbound-mgba-probe-quirks): boot, START/DOWN/A into the
 * character-customization + naming flow (blind A-mash fills a placeholder
 * name), mash through the shipwreck-flashback cutscenes/dialogue, then a
 * deterministic (fixed-seed) `explore` walk through the post-flashback
 * warehouse map (map group.number 4.10) to reach the starter-selection scene.
 *
 * Runs in short STAGES (1-9, savestate slots 5-9 plus scratch slots 1-4),
 * each resumed from a previous stage's savestate, to stay well under the
 * mGBA Lua bridge's ~3-4 minute connection-drop window on long sessions
 * (see memory unbound-mgba-probe-quirks). Savestates (output/roms/*.ssN)
 * persist on disk across invocations within a session but are gitignored,
 * so a fresh clone/checkout must always start again from stage 1.
 *
 * Every checkpoint dumps a screenshot + BG/OBJ VRAM + OAM + palette in the
 * SAME call (never split across two key-presses — a previously identified
 * trap where unsynced dumps can straddle two frames and hide a real
 * change), so any candidate "Cancel" screen can be correlated byte-for-byte
 * with what was on screen.
 *
 * Progress so far (stages 1-10): reaches map 4.10, a large shipping-container
 * warehouse, but has not yet found the trigger that advances past it. A
 * console/terminal object and a Poké-Ball-shaped ground decal are both
 * visible but interacting with either (from every reachable adjacent tile)
 * produced no dialogue/state change — likely decorative, or reachable only
 * from a tile this walk hasn't covered yet. `hugWall` (right-hand-rule) can
 * 2-cycle forever in open rooms; `preferUnvisited` (flood-fill) is more
 * robust, but stage 10 ran it for 300 more steps from stage 7's endpoint and
 * it also saturated (froze at one tile once every reachable tile had been
 * visited) without ever changing map/finding an NPC — i.e. the walkably-
 * reachable part of map 4.10 from this entry point has now been exhaustively
 * flood-filled and contains no discovered progression trigger. The next
 * attempt should stop guessing tile-by-tile and either (a) read the map's
 * event/warp object table directly from ROM (map header → event list, see
 * how the Unbound map format lays this out — no decomp source is available
 * in this repo, so this means byte-level RAM/ROM inspection of the map
 * header pointed to by the mapGroup/mapNumber pair) or (b) try an entirely
 * different branch of the intro (e.g. a different mash count/timing before
 * reaching map 4.10 might land the player elsewhere, since this maze may
 * not even be on the intended path). Two key-press quirks confirmed here:
 * a single 4-frame tap only turns the sprite to face a new direction, a
 * second tap is needed to actually move a tile; START is bound to the
 * naming keyboard's "OK" shortcut.
 *
 * Run: npx tsx scripts/probe_naming_cancel.mts <stage 1-9> [rom]
 */
import fs from 'fs';
import path from 'path';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.js';

const STAGE = parseInt(process.argv[2] ?? '1', 10);
const ROM = path.resolve(process.argv[3] ?? 'output/roms/GenedRom-fr.gba');
const OUT_DIR = path.resolve('output/proofs/naming-cancel');
fs.mkdirSync(OUT_DIR, { recursive: true });

async function dumpRegion(
  client: MgbaBridgeClient,
  base: number,
  size: number,
  file: string,
): Promise<void> {
  const chunks: Uint8Array[] = [];
  for (let off = 0; off < size; off += 4096) {
    const len = Math.min(4096, size - off);
    chunks.push(await client.readMemory(base + off, len));
  }
  const buf = Buffer.concat(chunks.map((c) => Buffer.from(c)));
  fs.writeFileSync(path.join(OUT_DIR, file), buf);
}

async function checkpoint(client: MgbaBridgeClient, tag: string): Promise<void> {
  await client.screenshot(path.join(OUT_DIR, `${tag}.png`));
  await dumpRegion(client, 0x06000000, 0x10000, `${tag}-vram-bg.bin`);
  await dumpRegion(client, 0x06010000, 0x8000, `${tag}-vram-obj.bin`);
  await dumpRegion(client, 0x07000000, 0x400, `${tag}-oam.bin`);
  await dumpRegion(client, 0x05000000, 0x400, `${tag}-pal.bin`);
  const st = await client.getState();
  console.error(`[cp ${tag}] map=${st.mapGroup}.${st.mapNumber} pos=${st.playerX},${st.playerY} battle=${st.inBattle} text=${st.textActive}`);
}

async function mash(client: MgbaBridgeClient, n: number, frames = 40): Promise<void> {
  for (let i = 0; i < n; i++) {
    await client.pressKey('A', 4);
    await client.advanceFrames(frames);
  }
}

// Deterministic explore walk, same fixed-seed RNG as scripts/probe_drive.mts's `explorei`.
async function exploreInteract(client: MgbaBridgeClient, n: number, tagPrefix: string): Promise<void> {
  const dirNames = ['UP', 'DOWN', 'LEFT', 'RIGHT'];
  let rngState = 0x9e3779b9 | 0;
  const rng = () => {
    rngState = (Math.imul(rngState, 1103515245) + 12345) & 0x7fffffff;
    return rngState >>> 16;
  };
  let lastKey = '';
  let stuck = 0;
  for (let i = 0; i < n; i++) {
    const st0 = await client.getState();
    const key = `${st0.mapGroup}.${st0.mapNumber}:${st0.playerX},${st0.playerY}`;
    if (key === lastKey) stuck++; else stuck = 0;
    lastKey = key;
    if (stuck > 0 && stuck % 6 === 0) {
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
    await client.pressKey('A', 4);
    await client.advanceFrames(30);
    await client.pressKey('B', 4);
    await client.advanceFrames(20);
    await client.pressKey('B', 4);
    await client.advanceFrames(20);
    if (i % 25 === 24) {
      await checkpoint(client, `${tagPrefix}-${String(i).padStart(3, '0')}`);
    }
  }
}

// Right-hand-rule wall follower: at each step try turning right relative to
// current facing first, then straight, then left, then back — the standard
// technique for solving a simply-connected maze without map data. Detects
// "blocked" purely from whether playerX/playerY actually changed after a
// key-press, since the corridor maze in map 4.10 defeated a pure random walk
// (bounded to a small pocket after 300+ steps).
async function hugWall(client: MgbaBridgeClient, n: number, tagPrefix: string): Promise<void> {
  const CW = ['UP', 'RIGHT', 'DOWN', 'LEFT'];
  let facing = 0;
  for (let i = 0; i < n; i++) {
    const before = await client.getState();
    const order = [(facing + 1) % 4, facing, (facing + 3) % 4, (facing + 2) % 4];
    for (const dirIdx of order) {
      // A single 4-frame tap isn't enough to complete a full tile step (the
      // walk animation needs the key held across several taps) — retry the
      // same direction a few times before concluding it's actually blocked.
      let moved = false;
      for (let tap = 0; tap < 4 && !moved; tap++) {
        await client.pressKey(CW[dirIdx], 4);
        await client.advanceFrames(16);
        const after = await client.getState();
        if (after.playerX !== before.playerX || after.playerY !== before.playerY || after.mapNumber !== before.mapNumber) {
          moved = true;
        }
      }
      if (moved) {
        facing = dirIdx;
        break;
      }
    }
    await client.pressKey('A', 4);
    await client.advanceFrames(20);
    if (i % 20 === 19) {
      await checkpoint(client, `${tagPrefix}-${String(i).padStart(3, '0')}`);
    }
  }
}

// Right-hand-rule breaks down in an open room (it can 2-cycle between tiles
// forever — confirmed happening at map 4.10 pos 8,14, where all 4
// directions are actually free per a manual diagnostic, yet hugWall froze
// there for 180+ steps). This walker instead prefers whichever direction
// leads to a tile not yet in `visited`, falling back to any direction that
// moves at all — a simple flood-fill that can't get trapped in a short
// cycle the way pure wall-following can.
async function preferUnvisited(client: MgbaBridgeClient, n: number, tagPrefix: string): Promise<void> {
  const dirNames = ['UP', 'DOWN', 'LEFT', 'RIGHT'];
  const visited = new Set<string>();
  for (let i = 0; i < n; i++) {
    const before = await client.getState();
    visited.add(`${before.mapNumber}:${before.playerX},${before.playerY}`);
    // Scratch checkpoint of THIS iteration's position, so a direction that
    // only reaches an already-visited tile can be undone without losing
    // forward progress from earlier iterations (loading a fixed slot would
    // always rewind to the walk's starting tile instead).
    await client.saveState(2);
    let fallbackDir: string | null = null;
    let moved = false;
    for (const dir of dirNames) {
      let stepMoved = false;
      for (let tap = 0; tap < 4 && !stepMoved; tap++) {
        await client.pressKey(dir, 4);
        await client.advanceFrames(16);
        const after = await client.getState();
        if (after.playerX !== before.playerX || after.playerY !== before.playerY || after.mapNumber !== before.mapNumber) {
          stepMoved = true;
        }
      }
      if (stepMoved) {
        const after = await client.getState();
        const key = `${after.mapNumber}:${after.playerX},${after.playerY}`;
        if (!visited.has(key)) {
          moved = true;
          break;
        }
        if (fallbackDir === null) fallbackDir = dir;
        await client.loadState(2);
        await client.advanceFrames(10);
      }
    }
    if (!moved && fallbackDir !== null) {
      await client.loadState(2);
      await client.advanceFrames(10);
      await client.pressKey(fallbackDir, 4);
      await client.advanceFrames(16);
    }
    await client.pressKey('A', 4);
    await client.advanceFrames(20);
    if (i % 20 === 19) {
      await checkpoint(client, `${tagPrefix}-${String(i).padStart(3, '0')}`);
    }
  }
}

async function main(): Promise<void> {
  const client = new MgbaBridgeClient();
  console.error(`[probe] stage ${STAGE} booting`);
  await client.startMgba(ROM);

  if (STAGE === 1) {
    await client.advanceFrames(600);
    await client.pressKey('START', 4); await client.advanceFrames(60);
    await client.pressKey('DOWN', 4); await client.advanceFrames(30);
    await client.pressKey('A', 4); await client.advanceFrames(120);
    console.error('[probe] character customization + naming (blind mash)');
    await mash(client, 30);
    await checkpoint(client, '00-post-customization');
    await client.saveState(5);
  } else if (STAGE === 2) {
    await client.advanceFrames(10);
    await client.loadState(5);
    await client.advanceFrames(30);
    // START is bound to the keyboard's "OK" shortcut (per the Selection help
    // panel, F-109) — confirm the blindly-typed name before mashing onward.
    await client.pressKey('START', 4);
    await client.advanceFrames(90);
    await checkpoint(client, '01a-post-confirm');
    console.error('[probe] mashing through shipwreck flashback cutscenes');
    await mash(client, 400);
    await checkpoint(client, '01-post-flashback');
    await client.saveState(6);
  } else if (STAGE === 3) {
    await client.advanceFrames(10);
    await client.loadState(6);
    await client.advanceFrames(30);
    console.error('[probe] deterministic explore through post-flashback map (part 1)');
    await exploreInteract(client, 150, '02-explore');
    await checkpoint(client, '03-post-explore1');
    await client.saveState(7);
  } else if (STAGE === 4) {
    await client.advanceFrames(10);
    await client.loadState(7);
    await client.advanceFrames(30);
    console.error('[probe] deterministic explore through post-flashback map (part 2)');
    await exploreInteract(client, 150, '04-explore2');
    await checkpoint(client, '05-post-explore2');
    await client.saveState(8);
  } else if (STAGE === 6) {
    await client.advanceFrames(10);
    await client.loadState(6);
    await client.advanceFrames(30);
    console.error('[probe] wall-hugging maze solve from post-flashback start');
    await hugWall(client, 250, '07-hug');
    await checkpoint(client, '08-post-hug');
    await client.saveState(9);
  } else if (STAGE === 7) {
    await client.advanceFrames(10);
    await client.loadState(9);
    await client.advanceFrames(30);
    console.error('[probe] flood-fill (prefer-unvisited) walk from the stuck tile');
    await preferUnvisited(client, 200, '11-flood');
    await checkpoint(client, '12-post-flood');
    await client.saveState(1);
  } else if (STAGE === 8) {
    await client.advanceFrames(10);
    await client.loadState(9);
    await client.advanceFrames(30);
    console.error('[probe] stepping onto the tile directly north of the console (2 taps: 1st turns, 2nd walks)');
    for (let tap = 0; tap < 2; tap++) {
      await client.pressKey('DOWN', 4);
      await client.advanceFrames(16);
    }
    await checkpoint(client, '13-adjacent-console');
    console.error('[probe] mashing A to interact with the console');
    for (let i = 0; i < 20; i++) {
      await client.pressKey('A', 4);
      await client.advanceFrames(40);
      if (i % 4 === 3) {
        await checkpoint(client, `14-console-interact-${String(i).padStart(3, '0')}`);
      }
    }
    await client.saveState(3);
  } else if (STAGE === 9) {
    await client.advanceFrames(10);
    await client.loadState(3);
    await client.advanceFrames(30);
    console.error('[probe] the console did nothing — walking tile-by-tile toward the Poke Ball item (down-left), verifying each step');
    const walkTiles = async (dir: string, tiles: number) => {
      for (let t = 0; t < tiles; t++) {
        const before = await client.getState();
        for (let tap = 0; tap < 6; tap++) {
          await client.pressKey(dir, 4);
          await client.advanceFrames(16);
          const after = await client.getState();
          if (after.playerX !== before.playerX || after.playerY !== before.playerY) break;
        }
      }
    };
    await walkTiles('LEFT', 2);
    await checkpoint(client, '15-after-left2');
    await walkTiles('DOWN', 2);
    await checkpoint(client, '16-after-down2');
    console.error('[probe] mashing A near the Poke Ball');
    for (let i = 0; i < 20; i++) {
      await client.pressKey('A', 4);
      await client.advanceFrames(40);
      if (i % 4 === 3) {
        await checkpoint(client, `17-ball-interact-${String(i).padStart(3, '0')}`);
      }
    }
    await client.saveState(4);
  } else if (STAGE === 11) {
    await client.advanceFrames(10);
    await client.loadState(5);
    await client.advanceFrames(30);
    await client.pressKey('START', 4);
    await client.advanceFrames(90);
    console.error('[probe] careful re-walk of the flashback, watching for a Yes/No or starter-choice menu');
    // Hypothesis: the previous blind mash(400) may have blown straight
    // through a starter-Pokémon choice and/or a "give a nickname?" Yes/No
    // prompt (mashing A on a menu just confirms whatever's highlighted —
    // likely the default "No"), which would explain why the CANCEL button
    // was never seen: we skipped the nickname keyboard entirely. Screenshot
    // every single step here (400 frames of margin per step) instead of
    // mashing blind, so any menu can be caught and answered deliberately.
    let lastText = false;
    for (let i = 0; i < 400; i++) {
      const before = await client.getState();
      await client.pressKey('A', 4);
      await client.advanceFrames(40);
      const after = await client.getState();
      if (after.textActive && !lastText) {
        console.error(`[probe] textActive turned ON at step ${i}`);
        await checkpoint(client, `20-textstart-${String(i).padStart(3, '0')}`);
      }
      if (!after.textActive && lastText) {
        console.error(`[probe] textActive turned OFF at step ${i}`);
      }
      lastText = Boolean(after.textActive);
      if (i % 20 === 19) {
        await checkpoint(client, `20-careful-${String(i).padStart(3, '0')}`);
      }
      if (after.mapNumber !== before.mapNumber) {
        console.error(`[probe] MAP CHANGED at step ${i}: ${before.mapGroup}.${before.mapNumber} -> ${after.mapGroup}.${after.mapNumber}`);
        await checkpoint(client, `20-mapchange-${String(i).padStart(3, '0')}`);
        await client.saveState(0);
      }
    }
    await client.saveState(6);
  } else if (STAGE === 12) {
    await client.advanceFrames(10);
    await client.loadState(5);
    await client.advanceFrames(30);
    await client.pressKey('START', 4);
    await client.advanceFrames(90);
    console.error('[probe] replaying identical mash up to step 190 (same deterministic sequence as stage 11)');
    for (let i = 0; i < 190; i++) {
      await client.pressKey('A', 4);
      await client.advanceFrames(40);
    }
    console.error('[probe] fine-grained single-press stepping through the map 4.1 bedroom window');
    for (let i = 190; i < 215; i++) {
      await client.pressKey('A', 4);
      await client.advanceFrames(40);
      await checkpoint(client, `21-fine-${String(i).padStart(3, '0')}`);
    }
    await client.saveState(7);
  } else if (STAGE === 10) {
    await client.advanceFrames(10);
    await client.loadState(1);
    await client.advanceFrames(30);
    console.error('[probe] extending the flood-fill walk further to cover unexplored territory');
    await preferUnvisited(client, 300, '18-flood2');
    await checkpoint(client, '19-post-flood2');
    await client.saveState(1);
  } else {
    throw new Error(`unknown stage ${STAGE}`);
  }

  console.error('[probe] done — inspect', OUT_DIR);
  await client.stop();
}

main().catch((e) => {
  console.error('[probe] FATAL', e);
  process.exit(1);
});
