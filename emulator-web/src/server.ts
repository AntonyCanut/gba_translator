import express from 'express';
import { createServer } from 'http';
import { WebSocketServer, WebSocket } from 'ws';
import path from 'path';
import { fileURLToPath } from 'url';
import { handleWebSocketMessage, type EmulatorControl } from './api.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = parseInt(process.env.PORT ?? '3000', 10);
const ROM_PATH = process.env.ROM_PATH ?? '';

export interface ServerInstance {
  close(): Promise<void>;
  port: number;
  url: string;
}

export function createEmulatorServer(options?: {
  port?: number;
  romPath?: string;
}): Promise<ServerInstance> {
  const port = options?.port ?? PORT;
  const romPath = options?.romPath ?? ROM_PATH;

  const app = express();
  const server = createServer(app);

  app.get('/api/health', (_req, res) => {
    res.json({ status: 'ok', romPath });
  });

  app.get('/api/config', (_req, res) => {
    res.json({ romPath, port });
  });

  const publicDir = path.resolve(__dirname, '../src/public');
  const distPublicDir = path.resolve(__dirname, 'public');

  // Serve static files from public directory (try dist first, then src)
  app.use(express.static(distPublicDir));
  app.use(express.static(publicDir));

  if (romPath) {
    app.use('/rom', express.static(path.dirname(romPath)));
  }

  const wss = new WebSocketServer({ server, path: '/ws' });

  // The emulator runs in the browser. The server acts as a relay:
  // Playwright sends commands via WS → server forwards to browser page → browser executes on emulator
  // For this architecture, we use a browser-page WS connection as the emulator backend.

  let browserSocket: WebSocket | null = null;
  const pendingRequests = new Map<string, { resolve: (data: unknown) => void; reject: (err: Error) => void }>();
  let requestCounter = 0;

  function createBrowserProxy(): EmulatorControl {
    function sendToBrowser(command: string): Promise<unknown> {
      return new Promise((resolve, reject) => {
        if (!browserSocket || browserSocket.readyState !== WebSocket.OPEN) {
          reject(new Error('Browser emulator not connected'));
          return;
        }
        const id = `req_${++requestCounter}`;
        pendingRequests.set(id, { resolve, reject });
        browserSocket.send(JSON.stringify({ id, command, source: 'server' }));
        setTimeout(() => {
          if (pendingRequests.has(id)) {
            pendingRequests.delete(id);
            reject(new Error('Request timeout'));
          }
        }, 30000);
      });
    }

    return {
      async loadRom(romPath: string) { await sendToBrowser(`LOAD_ROM ${romPath}`); },
      readMemory(address: number, length: number): Uint8Array {
        // Synchronous read not possible through WS relay — this is handled async
        return new Uint8Array(length);
      },
      writeMemory(_address: number, _data: Uint8Array) {
        // Handled through browser
      },
      keyDown(key: string) { sendToBrowser(`KEY_DOWN ${key}`).catch(() => {}); },
      keyUp(key: string) { sendToBrowser(`KEY_UP ${key}`).catch(() => {}); },
      async advanceFrames(count: number) { await sendToBrowser(`ADVANCE_FRAMES ${count}`); },
      getState() { return { status: 'proxy', browserConnected: !!browserSocket }; },
      async screenshot() { const r = await sendToBrowser('SCREENSHOT'); return r as string; },
      async saveState() { await sendToBrowser('SAVE_STATE'); },
      async loadState() { await sendToBrowser('LOAD_STATE'); },
      setFastForward(enabled: boolean) { sendToBrowser(`FAST_FORWARD ${enabled}`).catch(() => {}); },
      pause() { sendToBrowser('PAUSE').catch(() => {}); },
      resume() { sendToBrowser('RESUME').catch(() => {}); },
    };
  }

  const proxy = createBrowserProxy();

  wss.on('connection', (ws, req) => {
    const url = req.url ?? '';

    if (url.includes('role=browser')) {
      browserSocket = ws;
      console.log('[server] Browser emulator connected');

      ws.on('message', (data) => {
        try {
          const msg = JSON.parse(data.toString());
          if (msg.id && pendingRequests.has(msg.id)) {
            const pending = pendingRequests.get(msg.id)!;
            pendingRequests.delete(msg.id);
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

      ws.on('close', () => {
        console.log('[server] Browser emulator disconnected');
        if (browserSocket === ws) browserSocket = null;
      });
      return;
    }

    // Client (Playwright test) connection
    console.log('[server] Test client connected');

    ws.on('message', (data) => {
      const raw = data.toString();

      // If browser is connected, relay commands through it
      if (browserSocket && browserSocket.readyState === WebSocket.OPEN) {
        const id = `req_${++requestCounter}`;
        let requestId: string | undefined;

        try {
          if (raw.trimStart().startsWith('{')) {
            const envelope = JSON.parse(raw);
            requestId = envelope.id;
          }
        } catch { /* ignore */ }

        pendingRequests.set(id, {
          resolve: (result) => {
            const resp: Record<string, unknown> = { ok: true, data: result };
            if (requestId) resp.id = requestId;
            ws.send(JSON.stringify(resp));
          },
          reject: (err) => {
            const resp: Record<string, unknown> = { ok: false, error: err.message };
            if (requestId) resp.id = requestId;
            ws.send(JSON.stringify(resp));
          },
        });

        let commandStr = raw;
        try {
          if (raw.trimStart().startsWith('{')) {
            const envelope = JSON.parse(raw);
            commandStr = envelope.command ?? raw;
          }
        } catch { /* ignore */ }

        browserSocket.send(JSON.stringify({ id, command: commandStr, source: 'server' }));
      } else {
        handleWebSocketMessage(proxy, ws, raw);
      }
    });

    ws.on('close', () => {
      console.log('[server] Test client disconnected');
    });
  });

  return new Promise((resolve) => {
    server.listen(port, () => {
      console.log(`[server] GBA Emulator Web running on http://localhost:${port}`);
      console.log(`[server] ROM path: ${romPath || '(none configured)'}`);

      resolve({
        port,
        url: `http://localhost:${port}`,
        close: () => new Promise<void>((res) => {
          wss.close();
          server.close(() => res());
        }),
      });
    });
  });
}

// Auto-start when run directly
const isMainModule = process.argv[1] &&
  (process.argv[1].endsWith('server.ts') || process.argv[1].endsWith('server.js'));

if (isMainModule) {
  createEmulatorServer().then((srv) => {
    console.log(`[server] Listening on ${srv.url}`);
  });
}
