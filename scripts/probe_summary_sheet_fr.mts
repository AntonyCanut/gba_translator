/**
 * probe_summary_sheet_fr.mts — Relit en jeu les libellés de la planche
 * 0x00E9A460 (issue #145), la seule preuve fiable de leur rendu.
 *
 * La planche est un tileset linéaire : les mots y sont découpés en tuiles que
 * le tilemap de l'écran résumé recompose. Lire le PNG ne dit donc pas ce que
 * le joueur voit — il faut passer par l'écran.
 *
 * Navigation (identique à probe_summary_page2_header.mts) : savestate 2 →
 * START → Pokémon → premier slot → Résumé, puis RIGHT pour paginer et A pour
 * ouvrir le panneau de détail d'une attaque (POUVOIR / PRECIS.).
 *
 * Run:  MGBA_PATH=/opt/homebrew/bin/mgba npx tsx scripts/probe_summary_sheet_fr.mts [fr]
 */
import fs from 'fs';
import path from 'path';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.js';

const LANG = process.argv[2] ?? 'fr';
const ROM = path.resolve(`output/roms/GenedRom-${LANG}.gba`);
const OUT_DIR = path.resolve('output/proofs/summary-sheet');
fs.mkdirSync(OUT_DIR, { recursive: true });

async function shot(client: MgbaBridgeClient, name: string): Promise<void> {
  const out = path.join(OUT_DIR, `${LANG}-${name}.png`);
  await client.screenshot(out);
  console.error(`[shot] ${out}`);
}

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
  await shot(client, '01-info');

  await client.pressKey('RIGHT', 4);
  await client.advanceFrames(60);
  await shot(client, '02-skills');

  await client.pressKey('RIGHT', 4);
  await client.advanceFrames(60);
  await shot(client, '03-moves');

  // A ouvre le détail de l'attaque sélectionnée : POUVOIR / PRECIS.
  await client.pressKey('A', 4);
  await client.advanceFrames(60);
  await shot(client, '04-move-detail');

  await client.stop();
  console.error('[probe] done');
}

main().catch((e) => {
  console.error('[probe] FATAL', e);
  process.exit(1);
});
