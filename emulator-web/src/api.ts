import { WebSocket } from 'ws';
import { parseCommand, CommandError } from './commands.js';

export interface EmulatorControl {
  loadRom(path: string): Promise<void>;
  readMemory(address: number, length: number): Uint8Array;
  writeMemory(address: number, data: Uint8Array): void;
  keyDown(key: string): void;
  keyUp(key: string): void;
  advanceFrames(count: number): Promise<void>;
  getState(): object;
  screenshot(): Promise<string>;
  saveState(): Promise<void>;
  loadState(): Promise<void>;
  setFastForward(enabled: boolean): void;
  pause(): void;
  resume(): void;
}

interface WsResponse {
  id?: string;
  ok: boolean;
  data?: unknown;
  error?: string;
}

function parseAddress(value: string): number {
  return value.startsWith('0x') ? parseInt(value, 16) : parseInt(value, 10);
}

export function handleWebSocketMessage(
  emulator: EmulatorControl,
  ws: WebSocket,
  raw: string,
): void {
  let requestId: string | undefined;

  try {
    let commandStr = raw;

    // Support JSON envelope: { id: "...", command: "..." }
    if (raw.trimStart().startsWith('{')) {
      try {
        const envelope = JSON.parse(raw);
        requestId = envelope.id;
        commandStr = envelope.command ?? raw;
      } catch {
        // Not JSON, treat as raw command
      }
    }

    const cmd = parseCommand(commandStr);

    const respond = (data?: unknown) => {
      const resp: WsResponse = { ok: true };
      if (requestId) resp.id = requestId;
      if (data !== undefined) resp.data = data;
      ws.send(JSON.stringify(resp));
    };

    const respondError = (error: string) => {
      const resp: WsResponse = { ok: false, error };
      if (requestId) resp.id = requestId;
      ws.send(JSON.stringify(resp));
    };

    switch (cmd.type) {
      case 'LOAD_ROM':
        emulator.loadRom(cmd.args[0]).then(() => respond()).catch(e => respondError(String(e)));
        break;

      case 'READ_MEMORY': {
        const addr = parseAddress(cmd.args[0]);
        const len = parseInt(cmd.args[1], 10);
        const bytes = emulator.readMemory(addr, len);
        const hex = Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
        respond(hex);
        break;
      }

      case 'WRITE_MEMORY': {
        const addr = parseAddress(cmd.args[0]);
        const hexStr = cmd.args[1];
        const bytes = new Uint8Array(hexStr.length / 2);
        for (let i = 0; i < hexStr.length; i += 2) {
          bytes[i / 2] = parseInt(hexStr.substring(i, i + 2), 16);
        }
        emulator.writeMemory(addr, bytes);
        respond();
        break;
      }

      case 'KEY_DOWN':
        emulator.keyDown(cmd.args[0]);
        respond();
        break;

      case 'KEY_UP':
        emulator.keyUp(cmd.args[0]);
        respond();
        break;

      case 'ADVANCE_FRAMES': {
        const n = parseInt(cmd.args[0], 10);
        emulator.advanceFrames(n).then(() => respond()).catch(e => respondError(String(e)));
        break;
      }

      case 'GET_STATE':
        respond(emulator.getState());
        break;

      case 'SCREENSHOT':
        emulator.screenshot().then(png => respond(png)).catch(e => respondError(String(e)));
        break;

      case 'SAVE_STATE':
        emulator.saveState().then(() => respond()).catch(e => respondError(String(e)));
        break;

      case 'LOAD_STATE':
        emulator.loadState().then(() => respond()).catch(e => respondError(String(e)));
        break;

      case 'FAST_FORWARD': {
        const enabled = cmd.args[0] === 'true' || cmd.args[0] === '1';
        emulator.setFastForward(enabled);
        respond();
        break;
      }

      case 'PAUSE':
        emulator.pause();
        respond();
        break;

      case 'RESUME':
        emulator.resume();
        respond();
        break;
    }
  } catch (err) {
    const resp: WsResponse = {
      ok: false,
      error: err instanceof CommandError ? err.message : String(err),
    };
    if (requestId) resp.id = requestId;
    ws.send(JSON.stringify(resp));
  }
}
