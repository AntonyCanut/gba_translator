import { decodePokemonText } from './charmap.js';

export interface MemoryReader {
  read(address: number, length: number): Uint8Array;
  readU8(address: number): number;
  readU16(address: number): number;
  readU32(address: number): number;
  write(address: number, data: Uint8Array): void;
}

export const ADDRESSES = {
  gStringVar1: 0x02021d18,
  gStringVar2: 0x02021d28,
  gStringVar3: 0x02021d38,
  gStringVar4: 0x02021d48,
  STRING_VAR_SIZE_SMALL: 16,
  STRING_VAR4_SIZE: 1000,

  battleTextBuffer1: 0x02022e4c,
  battleTextBuffer2: 0x02022e5c,
  battleTextBuffer3: 0x02022e6c,
  BATTLE_TEXT_SIZE: 16,

  callback1: 0x030030f0,
  mapGroup: 0x02036dfc,
  mapNumber: 0x02036dfe,
  playerX: 0x02037078,
  playerY: 0x0203707a,
  battleFlag: 0x02023e8a,
  textFlag: 0x020375c0,
} as const;

export interface GameState {
  frameCount: number;
  mapGroup: number;
  mapNumber: number;
  playerX: number;
  playerY: number;
  inBattle: boolean;
  textActive: boolean;
  callback1: number;
}

export class MemoryAccess {
  constructor(private reader: MemoryReader) {}

  readStringVar1(): string {
    const data = this.reader.read(ADDRESSES.gStringVar1, ADDRESSES.STRING_VAR_SIZE_SMALL);
    return decodePokemonText(data);
  }

  readStringVar2(): string {
    const data = this.reader.read(ADDRESSES.gStringVar2, ADDRESSES.STRING_VAR_SIZE_SMALL);
    return decodePokemonText(data);
  }

  readStringVar3(): string {
    const data = this.reader.read(ADDRESSES.gStringVar3, ADDRESSES.STRING_VAR_SIZE_SMALL);
    return decodePokemonText(data);
  }

  readStringVar4(): string {
    const data = this.reader.read(ADDRESSES.gStringVar4, ADDRESSES.STRING_VAR4_SIZE);
    return decodePokemonText(data);
  }

  readBattleTextBuffer(index: 0 | 1 | 2): string {
    const base = [
      ADDRESSES.battleTextBuffer1,
      ADDRESSES.battleTextBuffer2,
      ADDRESSES.battleTextBuffer3,
    ][index];
    const data = this.reader.read(base, ADDRESSES.BATTLE_TEXT_SIZE);
    return decodePokemonText(data);
  }

  readTextAtAddress(address: number, maxLen: number = 256): string {
    const data = this.reader.read(address, maxLen);
    return decodePokemonText(data);
  }

  getGameState(frameCount: number): GameState {
    return {
      frameCount,
      mapGroup: this.reader.readU8(ADDRESSES.mapGroup),
      mapNumber: this.reader.readU8(ADDRESSES.mapNumber),
      playerX: this.reader.readU16(ADDRESSES.playerX),
      playerY: this.reader.readU16(ADDRESSES.playerY),
      inBattle: this.reader.readU16(ADDRESSES.battleFlag) !== 0,
      textActive: this.reader.readU8(ADDRESSES.textFlag) !== 0,
      callback1: this.reader.readU32(ADDRESSES.callback1),
    };
  }
}
