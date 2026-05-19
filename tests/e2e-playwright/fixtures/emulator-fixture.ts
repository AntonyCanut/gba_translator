import { test as base, type Page } from '@playwright/test';
import { EmulatorClient } from './emulator-client.js';
import type { ChildProcess } from 'child_process';
import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.resolve(__dirname, '..', '..', '..');

export interface EmulatorFixture {
  client: EmulatorClient;
  page: Page;
  serverUrl: string;
}

interface ServerHandle {
  process: ChildProcess;
  url: string;
  port: number;
}

async function waitForServer(url: string, timeoutMs = 60_000): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const resp = await fetch(`${url}/api/health`);
      if (resp.ok) {
        const data = await resp.json() as { status: string };
        if (data.status === 'ok') return;
      }
    } catch {
      // Server not ready yet
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`Server did not become ready within ${timeoutMs}ms at ${url}`);
}

async function startServer(port: number): Promise<ServerHandle> {
  const romPath = process.env.ROM_PATH ?? process.env.TEST_ROM_PATH ?? '';
  const emulatorDir = path.join(PROJECT_ROOT, 'emulator-web');

  const env = {
    ...process.env,
    PORT: String(port),
    ROM_PATH: romPath,
    NODE_ENV: 'test',
  };

  const serverProcess = spawn('npx', ['tsx', 'src/server.ts'], {
    cwd: emulatorDir,
    env,
    stdio: 'pipe',
  });

  serverProcess.stdout?.on('data', (data) => {
    if (process.env.DEBUG) {
      process.stdout.write(`[emulator-server:${port}] ${data}`);
    }
  });

  serverProcess.stderr?.on('data', (data) => {
    if (process.env.DEBUG) {
      process.stderr.write(`[emulator-server:${port}] ${data}`);
    }
  });

  const url = `http://localhost:${port}`;
  await waitForServer(url);

  return { process: serverProcess, url, port };
}

async function stopServer(handle: ServerHandle): Promise<void> {
  if (handle.process && !handle.process.killed) {
    const exited = new Promise<void>((resolve) => {
      handle.process.on('exit', () => resolve());
      handle.process.on('error', () => resolve());
    });
    handle.process.kill('SIGTERM');
    const timeout = new Promise<void>((resolve) => setTimeout(resolve, 8000));
    await Promise.race([exited, timeout]);
    if (!handle.process.killed) {
      handle.process.kill('SIGKILL');
    }
  }
}

export const test = base.extend<EmulatorFixture>({
  serverUrl: [async ({}, use, testInfo) => {
    const hash = [...testInfo.testId].reduce((acc, c) => acc + c.charCodeAt(0), 0);
    const port = 3100 + (testInfo.parallelIndex * 100) + (hash % 100);
    const server = await startServer(port);

    await use(server.url);

    await stopServer(server);
  }, { scope: 'test' }],

  page: [async ({ browser, serverUrl }, use) => {
    const context = await browser.newContext({
      viewport: { width: 480, height: 320 },
    });
    const page = await context.newPage();

    await page.goto(serverUrl, { waitUntil: 'networkidle' });
    await page.waitForSelector('#screen', { state: 'visible', timeout: 10_000 });

    await use(page);

    await context.close();
  }, { scope: 'test' }],

  client: [async ({ serverUrl, page }, use) => {
    void page;
    const wsUrl = serverUrl.replace('http:', 'ws:') + '/ws';
    const client = new EmulatorClient(wsUrl);
    await client.connect();

    await use(client);

    await client.disconnect();
  }, { scope: 'test' }],
});

export { expect } from '@playwright/test';
