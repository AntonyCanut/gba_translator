/**
 * probe_read_bgregs.mts — Load the naming-keyboard savestate (slot 5) and
 * dump BG control registers + scroll offsets, to map screen pixel positions
 * to VRAM charblock/screenblock addresses for tile-level sprite analysis
 * (ticket F-109).
 *
 * Run: npx tsx scripts/probe_read_bgregs.mts [rom]
 */
import path from 'path';
import { MgbaBridgeClient } from '../emulator-web/src/mgba-bridge.js';

const ROM = path.resolve(process.argv[2] ?? 'output/roms/GenedRom-fr.gba');

function u16(buf: Uint8Array, off = 0): number {
  return buf[off] | (buf[off + 1] << 8);
}

async function main(): Promise<void> {
  const client = new MgbaBridgeClient();
  await client.startMgba(ROM);
  await client.advanceFrames(10);
  await client.loadState(5);
  await client.advanceFrames(10);

  const regs: Record<string, number> = {};
  const names: Array<[string, number]> = [
    ['DISPCNT', 0x04000000],
    ['BG0CNT', 0x04000008],
    ['BG1CNT', 0x0400000a],
    ['BG2CNT', 0x0400000c],
    ['BG3CNT', 0x0400000e],
    ['BG0HOFS', 0x04000010],
    ['BG0VOFS', 0x04000012],
    ['BG1HOFS', 0x04000014],
    ['BG1VOFS', 0x04000016],
    ['BG2HOFS', 0x04000018],
    ['BG2VOFS', 0x0400001a],
    ['BG3HOFS', 0x0400001c],
    ['BG3VOFS', 0x0400001e],
  ];
  for (const [name, addr] of names) {
    const buf = await client.readMemory(addr, 2);
    regs[name] = u16(buf);
  }
  for (const [name, val] of Object.entries(regs)) {
    console.log(`${name} = 0x${val.toString(16).padStart(4, '0')}`);
  }
  const bgcnt = ['BG0CNT', 'BG1CNT', 'BG2CNT', 'BG3CNT'];
  for (const name of bgcnt) {
    const v = regs[name];
    const charBase = (v >> 2) & 0x3;
    const screenBase = (v >> 8) & 0x1f;
    const size = (v >> 14) & 0x3;
    const priority = v & 0x3;
    console.log(
      `${name}: priority=${priority} charBase=${charBase}(0x${(charBase * 0x4000).toString(16)}) ` +
        `screenBase=${screenBase}(0x${(screenBase * 0x800).toString(16)}) size=${size} raw=0x${v.toString(16)}`,
    );
  }
  await client.stop();
}

main().catch((e) => {
  console.error('[probe] FATAL', e);
  process.exit(1);
});
