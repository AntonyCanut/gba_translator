import { describe, it, expect } from 'vitest';
import { MemoryAccess, ADDRESSES, type MemoryReader } from '../src/memory.js';
import { encodePokemonText, POKEMON_TERMINATOR } from '../src/charmap.js';

function createMockReader(memoryContents: Map<number, Uint8Array> = new Map()): MemoryReader {
  const memory = new Uint8Array(0x04000000);

  for (const [addr, data] of memoryContents) {
    memory.set(data, addr);
  }

  return {
    read(address: number, length: number): Uint8Array {
      return memory.slice(address, address + length);
    },
    readU8(address: number): number {
      return memory[address];
    },
    readU16(address: number): number {
      return memory[address] | (memory[address + 1] << 8);
    },
    readU32(address: number): number {
      return (
        memory[address] |
        (memory[address + 1] << 8) |
        (memory[address + 2] << 16) |
        (memory[address + 3] << 24)
      ) >>> 0;
    },
    write(address: number, data: Uint8Array): void {
      memory.set(data, address);
    },
  };
}

describe('ADDRESSES', () => {
  it('has correct gStringVar addresses', () => {
    expect(ADDRESSES.gStringVar1).toBe(0x02021d18);
    expect(ADDRESSES.gStringVar2).toBe(0x02021d28);
    expect(ADDRESSES.gStringVar3).toBe(0x02021d38);
    expect(ADDRESSES.gStringVar4).toBe(0x02021d48);
  });

  it('has correct game state addresses', () => {
    expect(ADDRESSES.callback1).toBe(0x030030f0);
    expect(ADDRESSES.mapGroup).toBe(0x02036dfc);
    expect(ADDRESSES.mapNumber).toBe(0x02036dfe);
    expect(ADDRESSES.battleFlag).toBe(0x02023e8a);
  });
});

describe('MemoryAccess', () => {
  it('reads gStringVar1', () => {
    const text = encodePokemonText('Hello');
    const reader = createMockReader(new Map([[ADDRESSES.gStringVar1, text]]));
    const mem = new MemoryAccess(reader);
    expect(mem.readStringVar1()).toBe('Hello');
  });

  it('reads gStringVar2', () => {
    const text = encodePokemonText('World');
    const reader = createMockReader(new Map([[ADDRESSES.gStringVar2, text]]));
    const mem = new MemoryAccess(reader);
    expect(mem.readStringVar2()).toBe('World');
  });

  it('reads gStringVar3', () => {
    const text = encodePokemonText('Test');
    const reader = createMockReader(new Map([[ADDRESSES.gStringVar3, text]]));
    const mem = new MemoryAccess(reader);
    expect(mem.readStringVar3()).toBe('Test');
  });

  it('reads gStringVar4', () => {
    const text = encodePokemonText('Long text buffer');
    const reader = createMockReader(new Map([[ADDRESSES.gStringVar4, text]]));
    const mem = new MemoryAccess(reader);
    expect(mem.readStringVar4()).toBe('Long text buffer');
  });

  it('reads battle text buffers', () => {
    const text0 = encodePokemonText('Atk');
    const text1 = encodePokemonText('Def');
    const text2 = encodePokemonText('Spd');
    const reader = createMockReader(new Map([
      [ADDRESSES.battleTextBuffer1, text0],
      [ADDRESSES.battleTextBuffer2, text1],
      [ADDRESSES.battleTextBuffer3, text2],
    ]));
    const mem = new MemoryAccess(reader);
    expect(mem.readBattleTextBuffer(0)).toBe('Atk');
    expect(mem.readBattleTextBuffer(1)).toBe('Def');
    expect(mem.readBattleTextBuffer(2)).toBe('Spd');
  });

  it('reads game state', () => {
    const contents = new Map<number, Uint8Array>();
    // mapGroup = 3
    contents.set(ADDRESSES.mapGroup, new Uint8Array([3]));
    // mapNumber = 5
    contents.set(ADDRESSES.mapNumber, new Uint8Array([5]));
    // playerX = 10 (little-endian u16)
    contents.set(ADDRESSES.playerX, new Uint8Array([10, 0]));
    // playerY = 20 (little-endian u16)
    contents.set(ADDRESSES.playerY, new Uint8Array([20, 0]));
    // battleFlag = 0 (not in battle)
    contents.set(ADDRESSES.battleFlag, new Uint8Array([0, 0]));
    // textFlag = 1 (text active)
    contents.set(ADDRESSES.textFlag, new Uint8Array([1]));
    // callback1 = 0x08001234
    contents.set(ADDRESSES.callback1, new Uint8Array([0x34, 0x12, 0x00, 0x08]));

    const reader = createMockReader(contents);
    const mem = new MemoryAccess(reader);
    const state = mem.getGameState(100);

    expect(state.frameCount).toBe(100);
    expect(state.mapGroup).toBe(3);
    expect(state.mapNumber).toBe(5);
    expect(state.playerX).toBe(10);
    expect(state.playerY).toBe(20);
    expect(state.inBattle).toBe(false);
    expect(state.textActive).toBe(true);
    expect(state.callback1).toBe(0x08001234);
  });

  it('detects battle state', () => {
    const contents = new Map<number, Uint8Array>();
    contents.set(ADDRESSES.battleFlag, new Uint8Array([1, 0]));
    const reader = createMockReader(contents);
    const mem = new MemoryAccess(reader);
    const state = mem.getGameState(0);
    expect(state.inBattle).toBe(true);
  });

  it('reads text at arbitrary address', () => {
    const text = encodePokemonText('Custom');
    const addr = 0x02040000;
    const reader = createMockReader(new Map([[addr, text]]));
    const mem = new MemoryAccess(reader);
    expect(mem.readTextAtAddress(addr)).toBe('Custom');
  });

  it('handles empty string vars (terminator at start)', () => {
    const reader = createMockReader(new Map([
      [ADDRESSES.gStringVar1, new Uint8Array([POKEMON_TERMINATOR])],
    ]));
    const mem = new MemoryAccess(reader);
    expect(mem.readStringVar1()).toBe('');
  });
});
