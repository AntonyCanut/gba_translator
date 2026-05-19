import express from 'express';
import { createServer } from 'http';
import { WebSocketServer, WebSocket } from 'ws';
import path from 'path';
import { fileURLToPath } from 'url';
import { parseCommand, CommandError } from './commands.js';
import { MgbaBridgeClient } from './mgba-bridge.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = parseInt(process.env.PORT ?? '3000', 10);
const ROM_PATH = process.env.ROM_PATH ?? '';

export interface ServerInstance {
  close(): Promise<void>;
  port: number;
  url: string;
}

const KEY_NAME_TO_ID: Record<string, number> = {
  A: 0, B: 1, SELECT: 2, START: 3,
  RIGHT: 4, LEFT: 5, UP: 6, DOWN: 7,
  R: 8, L: 9,
};

export function createEmulatorServer(options?: {
  port?: number;
  romPath?: string;
}): Promise<ServerInstance> {
  const port = options?.port ?? PORT;
  const romPath = options?.romPath ?? ROM_PATH;

  const app = express();
  const server = createServer(app);
  const bridge = new MgbaBridgeClient();

  let bridgeReady = false;
  let bridgeError: string | null = null;

  const heldKeys = new Set<string>();

  if (romPath) {
    console.log(`[server] Auto-starting mGBA with ROM: ${romPath}`);
    bridge.startMgba(romPath).then(() => {
      bridgeReady = true;
      console.log('[server] mGBA bridge ready');
    }).catch((err) => {
      bridgeError = String(err);
      console.error(`[server] mGBA bridge failed: ${bridgeError}`);
    });
  }

  app.get('/api/health', (_req, res) => {
    if (bridgeError) {
      res.status(503).json({ status: 'error', error: bridgeError });
    } else if (!romPath) {
      res.json({ status: 'ok', romPath: '', mgbaRunning: false });
    } else if (bridgeReady) {
      res.json({ status: 'ok', romPath, mgbaRunning: true });
    } else {
      res.status(503).json({ status: 'starting', romPath });
    }
  });

  app.get('/api/config', (_req, res) => {
    res.json({ romPath, port });
  });

  const publicDir = path.resolve(__dirname, '../src/public');
  const distPublicDir = path.resolve(__dirname, 'public');
  app.use(express.static(distPublicDir));
  app.use(express.static(publicDir));

  if (romPath) {
    app.use('/rom', express.static(path.dirname(romPath)));
  }

  const wss = new WebSocketServer({ server, path: '/ws' });

  async function handleCommand(
    ws: WebSocket,
    raw: string,
    requestId?: string,
  ): Promise<void> {
    const respond = (data?: unknown) => {
      const resp: Record<string, unknown> = { ok: true };
      if (requestId) resp.id = requestId;
      if (data !== undefined) resp.data = data;
      ws.send(JSON.stringify(resp));
    };

    const respondError = (error: string) => {
      const resp: Record<string, unknown> = { ok: false, error };
      if (requestId) resp.id = requestId;
      ws.send(JSON.stringify(resp));
    };

    try {
      const cmd = parseCommand(raw);

      switch (cmd.type) {
        case 'LOAD_ROM': {
          if (!bridge.isConnected) {
            await bridge.startMgba(cmd.args[0]);
            bridgeReady = true;
          }
          respond();
          break;
        }

        case 'READ_MEMORY': {
          const addr = cmd.args[0].startsWith('0x')
            ? parseInt(cmd.args[0], 16)
            : parseInt(cmd.args[0], 10);
          const len = parseInt(cmd.args[1], 10);
          const bytes = await bridge.readMemory(addr, len);
          const hex = Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
          respond(hex);
          break;
        }

        case 'WRITE_MEMORY': {
          const wAddr = cmd.args[0].startsWith('0x')
            ? parseInt(cmd.args[0], 16)
            : parseInt(cmd.args[0], 10);
          const hexStr = cmd.args[1];
          const wBytes = new Uint8Array(hexStr.length / 2);
          for (let i = 0; i < hexStr.length; i += 2) {
            wBytes[i / 2] = parseInt(hexStr.substring(i, i + 2), 16);
          }
          await bridge.writeMemory(wAddr, wBytes);
          respond();
          break;
        }

        case 'KEY_DOWN': {
          const keyName = cmd.args[0].toUpperCase();
          heldKeys.add(keyName);
          respond();
          break;
        }

        case 'KEY_UP': {
          const keyName = cmd.args[0].toUpperCase();
          heldKeys.delete(keyName);
          respond();
          break;
        }

        case 'ADVANCE_FRAMES': {
          const n = parseInt(cmd.args[0], 10);
          if (heldKeys.size === 1) {
            const key = [...heldKeys][0];
            await bridge.pressKeyAndAdvance(key, n);
          } else if (heldKeys.size > 1) {
            const keys = [...heldKeys];
            await bridge.pressKey(keys[0], n);
            await bridge.advanceFrames(n);
          } else {
            await bridge.advanceFrames(n);
          }
          respond();
          break;
        }

        case 'GET_STATE': {
          const state = await bridge.getState();
          respond(state);
          break;
        }

        case 'SCREENSHOT': {
          const png = await bridge.screenshot();
          respond(png);
          break;
        }

        case 'SAVE_STATE': {
          await bridge.saveState();
          respond();
          break;
        }

        case 'LOAD_STATE': {
          await bridge.loadState();
          respond();
          break;
        }

        case 'FAST_FORWARD':
        case 'PAUSE':
        case 'RESUME': {
          respond();
          break;
        }
      }
    } catch (err) {
      respondError(err instanceof CommandError ? err.message : String(err));
    }
  }

  wss.on('connection', (ws, req) => {
    const url = req.url ?? '';

    if (url.includes('role=browser')) {
      console.log('[server] Browser viewer connected');
      ws.on('close', () => console.log('[server] Browser viewer disconnected'));
      return;
    }

    console.log('[server] Test client connected');

    ws.on('message', (data) => {
      const raw = data.toString();
      let requestId: string | undefined;
      let commandStr = raw;

      try {
        if (raw.trimStart().startsWith('{')) {
          const envelope = JSON.parse(raw);
          requestId = envelope.id;
          commandStr = envelope.command ?? raw;
        }
      } catch { /* not JSON */ }

      handleCommand(ws, commandStr, requestId).catch((err) => {
        const resp: Record<string, unknown> = { ok: false, error: String(err) };
        if (requestId) resp.id = requestId;
        ws.send(JSON.stringify(resp));
      });
    });

    ws.on('close', () => console.log('[server] Test client disconnected'));
  });

  return new Promise((resolve) => {
    server.listen(port, () => {
      console.log(`[server] GBA Emulator Web (mGBA backend) on http://localhost:${port}`);
      console.log(`[server] ROM path: ${romPath || '(none configured)'}`);

      resolve({
        port,
        url: `http://localhost:${port}`,
        close: async () => {
          await bridge.stop();
          await new Promise<void>((res) => {
            wss.close();
            server.close(() => res());
          });
        },
      });
    });
  });
}

const isMainModule = process.argv[1] &&
  (process.argv[1].endsWith('server.ts') || process.argv[1].endsWith('server.js'));

if (isMainModule) {
  createEmulatorServer().then((srv) => {
    console.log(`[server] Listening on ${srv.url}`);
  });
}
