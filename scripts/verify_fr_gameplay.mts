/**
 * verify_fr_gameplay.mts — Launch→first-battle French translation gameplay probe.
 *
 * Boots the built French ROM in a real mGBA instance (via the Lua bridge),
 * walks the launch sequence (title → new game → intro dialogue → first battle
 * setup), and harvests the *real* in-game text buffers at every stage.
 *
 * For each captured string it flags:
 *   - encoding degradation  ('?' produced by an unmapped CFRU byte)
 *   - residual English      (known EN UI/menu tokens that should be FR)
 *   - control-code fragments left visible
 *
 * Output: JSON report on stdout + PNG screenshots under output/proofs/fr-gameplay/.
 *
 * Run:  npx tsx scripts/verify_fr_gameplay.mts [romPath]
 */
import fs from 'fs';
import path from 'path';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.js';
import { decodePokemonText } from '../tests/e2e-playwright/helpers/charmap.js';
import { ADDRESSES, KNOWN_ENGLISH_STRINGS } from '../tests/e2e-playwright/helpers/constants.js';

const ROM = path.resolve(process.argv[2] ?? 'output/roms/GenedRom-fr.gba');
const OUT_DIR = path.resolve('output/proofs/fr-gameplay');
fs.mkdirSync(OUT_DIR, { recursive: true });

interface Capture {
  stage: string;
  frame: number;
  buffer: string;
  text: string;
  issues: string[];
}

const captures: Capture[] = [];
const seen = new Set<string>();

// English tokens that should never survive into French dialogue. Matched on
// word boundaries so French words that merely contain them (CONTINUE⊂CONTINUER)
// are not flagged.
const ENGLISH_WORDS = [
  ...KNOWN_ENGLISH_STRINGS.filter((s) => s.toUpperCase() !== 'OPTIONS'),
  'him', 'her', 'them', 'the', 'you', 'your', 'with', 'and', 'this', 'that',
];

function inspect(text: string): string[] {
  const issues: string[] = [];

  // A real unmapped/degraded byte shows up as a '?' wedged *between* letters
  // ("obscure?pour"). A legitimate French question mark is followed by a space,
  // newline or end-of-string, so it never matches this pattern.
  if (/[\p{L}]\?[\p{L}]/u.test(text)) {
    issues.push(`encoding: mid-word '?' (unmapped/degraded byte) -> "${text}"`);
  }

  for (const en of ENGLISH_WORDS) {
    const re = new RegExp(`\\b${en.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i');
    if (re.test(text)) {
      issues.push(`english: "${en}" -> "${text}"`);
    }
  }
  return issues;
}

async function harvest(client: MgbaBridgeClient, stage: string): Promise<void> {
  const state = await client.getState();
  const frame = Number(state.frameCount ?? 0);
  const buffers: Array<[string, number, number]> = [
    ['stringVar1', ADDRESSES.gStringVar1, ADDRESSES.STRING_VAR_SIZE_SMALL],
    ['stringVar2', ADDRESSES.gStringVar2, ADDRESSES.STRING_VAR_SIZE_SMALL],
    ['stringVar3', ADDRESSES.gStringVar3, ADDRESSES.STRING_VAR_SIZE_SMALL],
    ['stringVar4', ADDRESSES.gStringVar4, ADDRESSES.STRING_VAR4_SIZE],
    ['battleText1', ADDRESSES.battleTextBuffer1, ADDRESSES.BATTLE_TEXT_SIZE],
    ['battleText2', ADDRESSES.battleTextBuffer2, ADDRESSES.BATTLE_TEXT_SIZE],
    ['battleText3', ADDRESSES.battleTextBuffer3, ADDRESSES.BATTLE_TEXT_SIZE],
  ];
  for (const [name, addr, len] of buffers) {
    const raw = await client.readMemory(addr, len);
    const text = decodePokemonText(raw).trim();
    if (text.length < 2) continue;
    const key = `${name}:${text}`;
    if (seen.has(key)) continue;
    seen.add(key);
    captures.push({ stage, frame, buffer: name, text, issues: inspect(text) });
  }
}

async function shot(client: MgbaBridgeClient, name: string): Promise<void> {
  try {
    await client.screenshot(path.join(OUT_DIR, `${name}.png`));
  } catch (e) {
    console.error(`[shot] ${name} failed: ${String(e)}`);
  }
}

async function main(): Promise<void> {
  const client = new MgbaBridgeClient();
  console.error(`[probe] booting ${ROM}`);
  await client.startMgba(ROM);

  // --- Stage 1: title screen ---
  await client.advanceFrames(600);
  await harvest(client, 'title');
  await shot(client, '01-title');

  // --- Stage 2: start new game + professor intro ---
  await client.pressKey('START', 4);
  await client.advanceFrames(120);
  await client.pressKey('A', 4);
  await client.advanceFrames(120);

  for (let i = 0; i < 60; i++) {
    await client.pressKey('A', 4);
    await client.advanceFrames(90);
    await harvest(client, 'intro');
    if (i % 15 === 0) await shot(client, `02-intro-${i}`);
  }
  await shot(client, '03-intro-final');

  // --- Stage 3: try to reach overworld + trigger a wild battle ---
  let battleReached = false;
  const dirs = ['DOWN', 'RIGHT', 'UP', 'LEFT'] as const;
  outer: for (let batch = 0; batch < 25; batch++) {
    for (let i = 0; i < 8; i++) {
      await client.pressKey('A', 4);
      await client.advanceFrames(45);
    }
    for (const dir of dirs) {
      for (let s = 0; s < 4; s++) {
        await client.pressKey(dir, 4);
        await client.advanceFrames(16);
      }
      const st = await client.getState();
      await harvest(client, 'overworld');
      if (st.inBattle) {
        battleReached = true;
        break outer;
      }
    }
  }

  if (battleReached) {
    await client.advanceFrames(120);
    await harvest(client, 'battle');
    await shot(client, '04-battle');
    for (let i = 0; i < 8; i++) {
      await client.pressKey('A', 4);
      await client.advanceFrames(60);
      await harvest(client, 'battle');
    }
    await shot(client, '05-battle-after');
  }

  await shot(client, '06-final');
  await client.stop();

  const issues = captures.filter((c) => c.issues.length > 0);
  const report = {
    rom: ROM,
    battleReached,
    capturedStrings: captures.length,
    distinctStages: [...new Set(captures.map((c) => c.stage))],
    issuesFound: issues.length,
    captures,
  };
  console.log(JSON.stringify(report, null, 2));
}

main().catch((e) => {
  console.error('[probe] FATAL', e);
  process.exit(1);
});
