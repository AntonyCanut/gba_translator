import { WebSocket } from 'ws';
import { decodePokemonText, hexToBytes } from '../helpers/charmap.js';
import { ADDRESSES, type GBAKey, type ScreenType } from '../helpers/constants.js';

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

export interface TextBuffers {
  stringVar1: string;
  stringVar2: string;
  stringVar3: string;
  stringVar4: string;
  battleText1: string;
  battleText2: string;
  battleText3: string;
}

interface WsResponse {
  ok: boolean;
  data?: unknown;
  error?: string;
  id?: string;
}

export class EmulatorClient {
  private ws: WebSocket | null = null;
  private requestCounter = 0;
  private pendingRequests = new Map<string, {
    resolve: (data: unknown) => void;
    reject: (err: Error) => void;
  }>();
  private connected = false;

  constructor(private wsUrl: string) {}

  async connect(timeoutMs = 10_000): Promise<void> {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        reject(new Error(`WebSocket connection timeout after ${timeoutMs}ms`));
      }, timeoutMs);

      this.ws = new WebSocket(this.wsUrl);

      this.ws.on('open', () => {
        clearTimeout(timer);
        this.connected = true;
        resolve();
      });

      this.ws.on('message', (data) => {
        try {
          const msg: WsResponse = JSON.parse(data.toString());
          if (msg.id && this.pendingRequests.has(msg.id)) {
            const pending = this.pendingRequests.get(msg.id)!;
            this.pendingRequests.delete(msg.id);
            if (msg.ok) {
              pending.resolve(msg.data);
            } else {
              pending.reject(new Error(msg.error ?? 'Unknown error'));
            }
          }
        } catch {
          // Ignore malformed messages
        }
      });

      this.ws.on('error', (err) => {
        clearTimeout(timer);
        reject(err);
      });

      this.ws.on('close', () => {
        this.connected = false;
      });
    });
  }

  async disconnect(): Promise<void> {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
      this.connected = false;
    }
  }

  private sendCommand(command: string, timeoutMs = 30_000): Promise<unknown> {
    return new Promise((resolve, reject) => {
      if (!this.ws || !this.connected) {
        reject(new Error('WebSocket not connected'));
        return;
      }

      const id = `req_${++this.requestCounter}`;
      const timer = setTimeout(() => {
        this.pendingRequests.delete(id);
        reject(new Error(`Command timeout: ${command}`));
      }, timeoutMs);

      this.pendingRequests.set(id, {
        resolve: (data) => {
          clearTimeout(timer);
          resolve(data);
        },
        reject: (err) => {
          clearTimeout(timer);
          reject(err);
        },
      });

      this.ws.send(JSON.stringify({ id, command }));
    });
  }

  async loadRom(romPath: string): Promise<void> {
    await this.sendCommand(`LOAD_ROM ${romPath}`);
  }

  async readMemory(address: number, length: number): Promise<Uint8Array> {
    const hex = await this.sendCommand(
      `READ_MEMORY 0x${address.toString(16)} ${length}`,
    ) as string;
    return hexToBytes(hex);
  }

  async writeMemory(address: number, data: Uint8Array): Promise<void> {
    const hex = Array.from(data)
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('');
    await this.sendCommand(`WRITE_MEMORY 0x${address.toString(16)} ${hex}`);
  }

  async pressKey(key: GBAKey, frames = 4): Promise<void> {
    await this.sendCommand(`KEY_DOWN ${key}`);
    await this.advanceFrames(frames);
    await this.sendCommand(`KEY_UP ${key}`);
    await this.advanceFrames(2);
  }

  async pressSequence(keys: GBAKey[], gapFrames = 8): Promise<void> {
    for (const key of keys) {
      await this.pressKey(key);
      await this.advanceFrames(gapFrames);
    }
  }

  async advanceFrames(n: number): Promise<void> {
    await this.sendCommand(`ADVANCE_FRAMES ${n}`);
  }

  async screenshot(): Promise<Buffer> {
    const base64 = await this.sendCommand('SCREENSHOT') as string;
    const dataUrlPrefix = 'data:image/png;base64,';
    const raw = base64.startsWith(dataUrlPrefix)
      ? base64.slice(dataUrlPrefix.length)
      : base64;
    return Buffer.from(raw, 'base64');
  }

  async getState(): Promise<GameState> {
    const raw = await this.sendCommand('GET_STATE') as Record<string, unknown>;
    return {
      frameCount: Number(raw.frameCount ?? 0),
      mapGroup: Number(raw.mapGroup ?? 0),
      mapNumber: Number(raw.mapNumber ?? 0),
      playerX: Number(raw.playerX ?? 0),
      playerY: Number(raw.playerY ?? 0),
      inBattle: Boolean(raw.inBattle),
      textActive: Boolean(raw.textActive),
      callback1: Number(raw.callback1 ?? 0),
    };
  }

  async saveState(): Promise<void> {
    await this.sendCommand('SAVE_STATE');
  }

  async loadState(): Promise<void> {
    await this.sendCommand('LOAD_STATE');
  }

  async fastForward(enabled: boolean): Promise<void> {
    await this.sendCommand(`FAST_FORWARD ${enabled}`);
  }

  async pause(): Promise<void> {
    await this.sendCommand('PAUSE');
  }

  async resume(): Promise<void> {
    await this.sendCommand('RESUME');
  }

  async readText(address: number, maxLen = 256): Promise<string> {
    const data = await this.readMemory(address, maxLen);
    return decodePokemonText(data);
  }

  async readAllTextBuffers(): Promise<TextBuffers> {
    const [sv1, sv2, sv3, sv4, bt1, bt2, bt3] = await Promise.all([
      this.readMemory(ADDRESSES.gStringVar1, ADDRESSES.STRING_VAR_SIZE_SMALL),
      this.readMemory(ADDRESSES.gStringVar2, ADDRESSES.STRING_VAR_SIZE_SMALL),
      this.readMemory(ADDRESSES.gStringVar3, ADDRESSES.STRING_VAR_SIZE_SMALL),
      this.readMemory(ADDRESSES.gStringVar4, ADDRESSES.STRING_VAR4_SIZE),
      this.readMemory(ADDRESSES.battleTextBuffer1, ADDRESSES.BATTLE_TEXT_SIZE),
      this.readMemory(ADDRESSES.battleTextBuffer2, ADDRESSES.BATTLE_TEXT_SIZE),
      this.readMemory(ADDRESSES.battleTextBuffer3, ADDRESSES.BATTLE_TEXT_SIZE),
    ]);

    return {
      stringVar1: decodePokemonText(sv1),
      stringVar2: decodePokemonText(sv2),
      stringVar3: decodePokemonText(sv3),
      stringVar4: decodePokemonText(sv4),
      battleText1: decodePokemonText(bt1),
      battleText2: decodePokemonText(bt2),
      battleText3: decodePokemonText(bt3),
    };
  }

  async waitForScreen(
    type: ScreenType,
    timeoutMs = 30_000,
  ): Promise<void> {
    const start = Date.now();
    const frameStep = 30;

    while (Date.now() - start < timeoutMs) {
      await this.advanceFrames(frameStep);
      const state = await this.getState();

      switch (type) {
        case 'battle':
          if (state.inBattle) return;
          break;
        case 'dialogue':
          if (state.textActive) return;
          break;
        case 'overworld':
          if (!state.inBattle && !state.textActive && state.mapNumber > 0) return;
          break;
        case 'menu':
          if (state.textActive) return;
          break;
        case 'title':
          if (state.frameCount >= 300) return;
          break;
        case 'intro':
          if (state.mapNumber > 0) return;
          break;
      }
    }

    throw new Error(`Timeout waiting for screen type: ${type}`);
  }

  isConnected(): boolean {
    return this.connected;
  }
}
