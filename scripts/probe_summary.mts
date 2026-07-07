/**
 * probe_summary.mts — Screenshot the Pokémon Summary "Info" page (team list
 * → A → A) to verify the level-prefix text (B-236: « Lv »→« N. »).
 *
 * Navigation mirrors probe_summary_page2_header.mts: savestate slot 2
 * (overworld with a Pokémon in the party) → open START menu → Pokémon →
 * select slot 0 → Summary "Info" page, which shows the "Lv10" header next
 * to the icon and the "Rencontré à ..., au Lv 10." memo at the bottom.
 *
 * Run:  MGBA_PATH=/opt/homebrew/bin/mgba npx tsx scripts/probe_summary.mts <rom> <out.png>
 */
import path from 'path';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.js';

const ROM = path.resolve(process.argv[2] ?? 'output/roms/GenedRom-fr.gba');
const OUT = path.resolve(process.argv[3] ?? 'output/proofs/summary-info.png');

async function main(): Promise<void> {
  const client = new MgbaBridgeClient();
  console.error(`[probe] booting ${ROM}`);
  await client.startMgba(ROM);

  await client.advanceFrames(600);
  await client.loadState(2);
  await client.advanceFrames(30);

  for (let i = 0; i < 3; i++) {
    await client.pressKey('B', 4);
    await client.advanceFrames(20);
  }
  await client.pressKey('START', 4);
  await client.advanceFrames(40);
  await client.pressKey('A', 4);
  await client.advanceFrames(90);
  await client.pressKey('A', 4);
  await client.advanceFrames(30);
  await client.pressKey('A', 4);
  await client.advanceFrames(90);

  await client.screenshot(OUT);
  console.error(`[probe] screenshot -> ${OUT}`);

  await client.stop();
  console.error('[probe] done');
}

main().catch((e) => {
  console.error('[probe] FATAL', e);
  process.exit(1);
});
