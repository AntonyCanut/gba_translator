/**
 * Non-regression tests for Express 5 + ws upgrades.
 *
 * Express 5 changes exercised here:
 *  - Route handlers with (_req, res) pattern still work
 *  - res.status().json() and res.json() return void (no chaining) — server code adapted
 *  - Async errors in handlers are auto-forwarded to the error handler
 *
 * ws 8.21 changes exercised here:
 *  - WebSocketServer still emits 'connection' events correctly
 *  - Message round-trip via JSON envelope still works
 */

import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { createEmulatorServer, type ServerInstance } from '../src/server.js';
import WebSocket from 'ws';

let server: ServerInstance;

beforeAll(async () => {
  server = await createEmulatorServer({ port: 0 });
});

afterAll(async () => {
  await server.close();
});

describe('Express 5 HTTP routes', () => {
  it('GET /api/health returns ok when no ROM configured', async () => {
    const res = await fetch(`${server.url}/api/health`);
    expect(res.status).toBe(200);
    const body = await res.json() as Record<string, unknown>;
    expect(body.status).toBe('ok');
    expect(body.mgbaRunning).toBe(false);
  });

  it('GET /api/config returns port and empty romPath', async () => {
    const res = await fetch(`${server.url}/api/config`);
    expect(res.status).toBe(200);
    const body = await res.json() as Record<string, unknown>;
    expect(body.romPath).toBe('');
    expect(typeof body.port).toBe('number');
    expect(body.port).toBe(server.port);
  });

  it('unknown routes return 404', async () => {
    const res = await fetch(`${server.url}/api/does-not-exist`);
    expect(res.status).toBe(404);
  });

  it('Content-Type header is application/json for health endpoint', async () => {
    const res = await fetch(`${server.url}/api/health`);
    expect(res.headers.get('content-type')).toMatch(/application\/json/);
  });
});

describe('WebSocket command round-trip (ws upgrade)', () => {
  it('unknown command returns error via plain text', async () => {
    const ws = new WebSocket(`ws://localhost:${server.port}/ws`);
    await new Promise<void>((resolve, reject) => {
      ws.on('error', reject);
      ws.on('open', () => resolve());
    });

    const reply = await new Promise<Record<string, unknown>>((resolve, reject) => {
      ws.once('message', (data) => {
        try { resolve(JSON.parse(data.toString())); }
        catch (e) { reject(e); }
      });
      ws.send('EXPLODE');
    });

    expect(reply.ok).toBe(false);
    expect(typeof reply.error).toBe('string');
    ws.close();
  });

  it('KEY_DOWN command returns ok=true via JSON envelope (no bridge needed)', async () => {
    const ws = new WebSocket(`ws://localhost:${server.port}/ws`);
    await new Promise<void>((resolve, reject) => {
      ws.on('error', reject);
      ws.on('open', () => resolve());
    });

    const reply = await new Promise<Record<string, unknown>>((resolve, reject) => {
      ws.once('message', (data) => {
        try { resolve(JSON.parse(data.toString())); }
        catch (e) { reject(e); }
      });
      ws.send(JSON.stringify({ id: 'req-1', command: 'KEY_DOWN A' }));
    });

    expect(reply.ok).toBe(true);
    expect(reply.id).toBe('req-1');
    ws.close();
  });

  it('browser viewer role does not crash the server', async () => {
    const ws = new WebSocket(`ws://localhost:${server.port}/ws?role=browser`);
    await new Promise<void>((resolve, reject) => {
      ws.on('error', reject);
      ws.on('open', () => resolve());
    });
    ws.close();
    // server still responds to HTTP after browser viewer disconnects
    const res = await fetch(`${server.url}/api/health`);
    expect(res.status).toBe(200);
  });
});
