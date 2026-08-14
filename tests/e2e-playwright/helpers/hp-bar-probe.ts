/**
 * Drive mGBA from the issue #84 save up to the second tab of a Pokémon's
 * status — the « Capacités Pokémon » / « Pokémon Skills » page that carries the
 * HP bar — and capture the framebuffer. The party menu crossed on the way is
 * captured too, as `<screenshot>.party.png`, because it carries six more HP
 * bars drawn from a different tile sheet.
 *
 * The main-menu entry that opens the party is *searched*, not hardcoded: for
 * each candidate the probe restores a save-state, walks the cursor down, opens
 * the entry, picks the first party slot, opens its summary, flips to the second
 * page and compares two stat-icon/value bands to a reference crop. Those
 * pixels are stable for the exact save fixture in every translated build,
 * share no pixel with the translated word-images and share no pixel with the
 * HP bar the test asserts on.
 *
 * Waiting a fixed number of frames after loading the save is not enough: the
 * quest reminder that pops up over the overworld does not appear at the same
 * frame in every build, and a `START` swallowed by it leaves the probe pressing
 * `A` at a signpost instead of walking the menu (that is exactly how the German
 * ROM used to fail). Every transition therefore waits for the framebuffer to
 * stop changing rather than for a frame count.
 *
 * Usage: hp-bar-probe.ts <rom> <screenshot.png> <stat-labels-anchor.png>
 */

import fs from 'fs';
import path from 'path';
import { MgbaBridgeClient } from '../../../emulator-web/src/mgba-bridge.js';
import { PNG } from 'pngjs';
import {
  PAGE_ANCHOR_REGIONS,
  partyScreenshotPath,
  cropRegions,
  readAnchorReference,
  readScreen,
  screenDiffRatio,
} from './hp-bar-regions.js';

const KEY_PRESS_FRAMES = 4;
const INITIAL_BOOT_FRAMES = 300;
const CONTINUE_SEQUENCE_FRAMES = [60, 60, 120, 120] as const;
const MENU_CURSOR_FRAMES = 20;
const PARTY_RENDER_FRAMES = 120;
const CONTEXT_MENU_FRAMES = 90;
const SUMMARY_RENDER_FRAMES = 150;
const PAGE_FLIP_FRAMES = 120;
const SETTLE_STEP_FRAMES = 30;
const SETTLE_MAX_STEPS = 16;
const SETTLE_TOLERANCE = 0.01;
// A transition can happen to look quiet across one sampling interval, so two
// consecutive quiet intervals are required before the screen is called stable.
const SETTLE_STABLE_STEPS = 2;
// Entry 5 of the main menu is « Sauvegarder »: opening it writes the battery
// save for real, so the search deliberately stops before ever reaching it.
const MAX_MAIN_MENU_ENTRIES = 4;

export interface ProbeResult {
  playerX: number;
  playerY: number;
  searchedMenuEntries: number;
}

/**
 * Advance until the framebuffer stops moving — i.e. until whatever animation,
 * fade or pop-up is running has finished. Throws rather than moving on blindly
 * if the screen never settles.
 *
 * "Stops moving" cannot mean "two identical captures": the main menu draws a
 * live clock and a blinking cursor, so it never repeats itself. Measured over
 * the English, French and German builds, that idle churn stays under 0.7 % of
 * the screen while a real transition moves 1.5 % (menu opening) to 7 % (the
 * quest reminder popping up) — hence the 1 % threshold.
 */
async function settle(client: MgbaBridgeClient, scratchPath: string,
                      what: string): Promise<void> {
  let previous: PNG | null = null;
  let quietSteps = 0;
  for (let step = 0; step < SETTLE_MAX_STEPS; step++) {
    await client.advanceFrames(SETTLE_STEP_FRAMES);
    await client.screenshot(scratchPath);
    const current = readScreen(scratchPath);
    if (previous !== null && screenDiffRatio(current, previous) <= SETTLE_TOLERANCE) {
      quietSteps++;
      if (quietSteps >= SETTLE_STABLE_STEPS) {
        fs.rmSync(scratchPath, { force: true });
        return;
      }
    } else {
      quietSteps = 0;
    }
    previous = current;
  }
  fs.rmSync(scratchPath, { force: true });
  throw new Error(
    `L'écran ne se stabilise pas après ${SETTLE_MAX_STEPS * SETTLE_STEP_FRAMES} `
    + `frames (${what})`,
  );
}

async function openSummarySkillsPage(client: MgbaBridgeClient): Promise<void> {
  // Party screen → first slot → « Résumé » (first context entry) → page 2.
  await client.pressKey('A', KEY_PRESS_FRAMES);
  await client.advanceFrames(CONTEXT_MENU_FRAMES);
  await client.pressKey('A', KEY_PRESS_FRAMES);
  await client.advanceFrames(SUMMARY_RENDER_FRAMES);
  await client.pressKey('RIGHT', KEY_PRESS_FRAMES);
  await client.advanceFrames(PAGE_FLIP_FRAMES);
}

async function findSkillsPage(
  client: MgbaBridgeClient,
  screenshotPath: string,
  anchorPath: string,
): Promise<number> {
  const anchor = readAnchorReference(anchorPath, PAGE_ANCHOR_REGIONS);
  const scratchPath = `${screenshotPath}.settle.png`;
  await client.saveState(1);

  for (let index = 0; index < MAX_MAIN_MENU_ENTRIES; index++) {
    if (index > 0) {
      await client.loadState(1);
      await client.advanceFrames(MENU_CURSOR_FRAMES);
    }

    for (let cursorMove = 0; cursorMove < index; cursorMove++) {
      await client.pressKey('DOWN', KEY_PRESS_FRAMES);
      await client.advanceFrames(MENU_CURSOR_FRAMES);
    }

    await client.pressKey('A', KEY_PRESS_FRAMES);
    await client.advanceFrames(PARTY_RENDER_FRAMES);
    // Grab the party menu on the way through; it is only kept if this
    // candidate turns out to be the right one.
    const partyCandidatePath = `${screenshotPath}.party-${index}.png`;
    await client.screenshot(partyCandidatePath);

    await openSummarySkillsPage(client);
    await settle(client, scratchPath, `entrée ${index} du menu`);

    const candidatePath = `${screenshotPath}.menu-${index}.png`;
    await client.screenshot(candidatePath);
    const candidate = cropRegions(readScreen(candidatePath), PAGE_ANCHOR_REGIONS);

    if (candidate.equals(anchor)) {
      fs.renameSync(candidatePath, screenshotPath);
      fs.renameSync(partyCandidatePath, partyScreenshotPath(screenshotPath));
      return index + 1;
    }

    fs.rmSync(candidatePath, { force: true });
    fs.rmSync(partyCandidatePath, { force: true });
  }

  throw new Error(
    `Page « Capacités » introuvable après ${MAX_MAIN_MENU_ENTRIES} entrées du menu`,
  );
}

async function captureSkillsPage(
  client: MgbaBridgeClient,
  screenshotPath: string,
  anchorPath: string,
): Promise<ProbeResult> {
  await client.advanceFrames(INITIAL_BOOT_FRAMES);

  // Title → Continue → overworld, using the battery save next to the ROM.
  for (const frames of CONTINUE_SEQUENCE_FRAMES) {
    await client.pressKey('A', KEY_PRESS_FRAMES);
    await client.advanceFrames(frames);
  }

  // Let the quest reminder that pops up over the overworld finish before
  // touching START, otherwise the menu never opens and every `A` afterwards
  // talks to whatever the player is facing.
  await settle(client, `${screenshotPath}.settle.png`, 'chargement de la partie');

  const overworld = await client.getState();
  const playerX = Number(overworld.playerX);
  const playerY = Number(overworld.playerY);
  if (playerX <= 0 || playerY <= 0) {
    throw new Error(`La save n'a pas chargé le joueur (${playerX}, ${playerY})`);
  }

  await client.pressKey('START', KEY_PRESS_FRAMES);
  await settle(client, `${screenshotPath}.settle.png`, 'ouverture du menu principal');
  const searchedMenuEntries = await findSkillsPage(client, screenshotPath, anchorPath);

  return { playerX, playerY, searchedMenuEntries };
}

async function withBridge<T>(
  romPath: string,
  run: (client: MgbaBridgeClient) => Promise<T>,
  attempts = 3,
): Promise<T> {
  let lastError: unknown;

  for (let attempt = 1; attempt <= attempts; attempt++) {
    const client = new MgbaBridgeClient();
    try {
      await client.startMgba(romPath);
      return await run(client);
    } catch (error) {
      lastError = error;
    } finally {
      await client.stop();
    }

    if (attempt < attempts) {
      await new Promise((resolve) => setTimeout(resolve, 1_000));
    }
  }

  throw lastError instanceof Error ? lastError : new Error(String(lastError));
}

async function main(): Promise<void> {
  const romPath = path.resolve(process.argv[2]);
  const screenshotPath = path.resolve(process.argv[3]);
  const anchorPath = path.resolve(process.argv[4]);
  const state = await withBridge(romPath, (client) => (
    captureSkillsPage(client, screenshotPath, anchorPath)
  ));
  console.log(JSON.stringify(state));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
