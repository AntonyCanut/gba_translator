import net from 'net';
import { ChildProcess, spawn, execSync } from 'child_process';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';
import { type EmulatorControl } from './api.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const BRIDGE_PORT = 55234;
const BRIDGE_HOST = '127.0.0.1';
const CONNECT_TIMEOUT = 30_000;
const COMMAND_TIMEOUT = 30_000;

const KEY_MAP: Record<string, number> = {
  A: 0, B: 1, SELECT: 2, START: 3,
  RIGHT: 4, LEFT: 5, UP: 6, DOWN: 7,
  R: 8, L: 9,
};

function findMgba(): string {
  const candidates = [
    '/Applications/mGBA.app/Contents/MacOS/mGBA',
    '/opt/homebrew/bin/mgba',
  ];

  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }

  for (const name of ['mgba-qt', 'mgba']) {
    try {
      const found = execSync(`which ${name}`, { encoding: 'utf8' }).trim();
      if (found) return found;
    } catch { /* not found */ }
  }

  throw new Error('mGBA not found. Install with: brew install mgba');
}

function mgbaSupportsScript(mgbaPath: string): boolean {
  try {
    const out = execSync(`"${mgbaPath}" --help 2>&1`, {
      encoding: 'utf8',
      timeout: 5000,
    });
    return out.includes('--script');
  } catch (e: unknown) {
    const stderr = (e as { stderr?: string })?.stderr ?? '';
    const stdout = (e as { stdout?: string })?.stdout ?? '';
    return stderr.includes('--script') || stdout.includes('--script');
  }
}

export class MgbaBridgeClient {
  private process: ChildProcess | null = null;
  private socket: net.Socket | null = null;
  private recvBuffer = '';
  private frameCount = 0;
  private romLoaded = false;
  private currentRomPath = '';
  private lineResolvers: Array<(line: string) => void> = [];

  async startMgba(romPath: string): Promise<void> {
    if (this.process) {
      await this.stop();
    }

    const rom = path.resolve(romPath);
    if (!fs.existsSync(rom)) {
      throw new Error(`ROM not found: ${rom}`);
    }

    await this.killStaleBridge();

    const mgbaPath = findMgba();

    const bridgeLua = path.resolve(__dirname, '..', 'src', 'lua', 'bridge.lua');
    const bridgeLuaDist = path.resolve(__dirname, 'lua', 'bridge.lua');
    const luaPath = fs.existsSync(bridgeLua) ? bridgeLua : bridgeLuaDist;

    if (!fs.existsSync(luaPath)) {
      throw new Error(`bridge.lua not found at ${bridgeLua} or ${bridgeLuaDist}`);
    }

    const useScriptFlag = mgbaSupportsScript(mgbaPath);

    const cmd = [mgbaPath];
    if (useScriptFlag) {
      cmd.push('--script', luaPath);
    }
    // NOTE: do NOT pass `-C fpsTarget=0`. On mGBA-qt 0.11 macOS it freezes the
    // emulator after frame 1 (no further frame callbacks fire), so the bridge
    // never advances. Native 60 fps is fine — `FRAMES|N` already runs frames
    // synchronously via the Lua callback.
    cmd.push(
      '-C', 'audioSync=0',
      '-C', 'videoSync=0',
      rom,
    );

    console.log(`[mgba] Launching: ${cmd.join(' ')}`);
    this.process = spawn(cmd[0], cmd.slice(1), {
      stdio: ['pipe', 'pipe', 'pipe'],
      detached: true,
    });

    this.process.stderr?.on('data', (data: Buffer) => {
      if (process.env.DEBUG) {
        process.stderr.write(`[mgba-stderr] ${data}`);
      }
    });

    this.process.stdout?.on('data', (data: Buffer) => {
      if (process.env.DEBUG) {
        process.stdout.write(`[mgba-stdout] ${data}`);
      }
    });

    this.process.on('exit', (code) => {
      console.log(`[mgba] Process exited with code ${code}`);
      this.process = null;
    });

    if (!useScriptFlag) {
      await this.loadScriptViaAppleScript(luaPath);
    }

    await this.connectToBridge();
    this.currentRomPath = romPath;
    this.romLoaded = true;
    this.frameCount = 0;
    console.log('[mgba] Bridge connected and ready');
  }

  private async loadScriptViaAppleScript(scriptPath: string): Promise<void> {
    await new Promise(resolve => setTimeout(resolve, 2000));

    const applescript = `
      tell application "System Events"
        tell process "mGBA"
          set frontmost to true
          delay 0.5
          click menu item "Scripting..." of menu "Tools" of menu bar 1
          delay 1.0
          click menu item "Load script..." of menu "File" of menu bar 1 of window "Scripting"
          delay 1.0
          keystroke "g" using {command down, shift down}
          delay 0.5
          keystroke "${scriptPath}"
          delay 0.3
          keystroke return
          delay 0.5
          keystroke return
        end tell
      end tell
    `;

    try {
      execSync(`osascript -e '${applescript.replace(/'/g, "'\\''")}'`, { timeout: 15000 });
    } catch (e) {
      console.warn('[mgba] AppleScript automation failed, bridge may not load:', e);
    }
  }

  private async killStaleBridge(): Promise<void> {
    try {
      const pids = execSync(`lsof -ti tcp:${BRIDGE_PORT}`, {
        encoding: 'utf8',
        timeout: 5000,
      }).trim().split('\n').filter(Boolean);

      const myPid = process.pid;
      for (const pidStr of pids) {
        const pid = parseInt(pidStr);
        if (pid && pid !== myPid) {
          console.log(`[mgba] Killing stale bridge process PID ${pid}`);
          try { process.kill(pid, 'SIGTERM'); } catch { /* already dead */ }
        }
      }
      if (pids.length > 0) {
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    } catch { /* no stale process */ }
  }

  private async connectToBridge(): Promise<void> {
    const deadline = Date.now() + CONNECT_TIMEOUT;

    while (Date.now() < deadline) {
      if (this.process && this.process.exitCode !== null) {
        throw new Error('mGBA process exited unexpectedly');
      }

      try {
        await this.tryConnect();
        const resp = await this.sendCommand('PING');
        if (resp.includes('pong')) {
          return;
        }
        this.disconnectSocket();
      } catch {
        this.disconnectSocket();
      }
      await new Promise(resolve => setTimeout(resolve, 500));
    }

    throw new Error(`Could not connect to mGBA bridge after ${CONNECT_TIMEOUT}ms`);
  }

  private tryConnect(): Promise<void> {
    return new Promise((resolve, reject) => {
      const sock = new net.Socket();
      sock.setTimeout(COMMAND_TIMEOUT);

      sock.on('connect', () => {
        this.socket = sock;
        this.recvBuffer = '';
        this.setupSocketListeners();
        resolve();
      });

      sock.on('error', (err) => {
        sock.destroy();
        reject(err);
      });

      sock.on('timeout', () => {
        sock.destroy();
        reject(new Error('Connection timeout'));
      });

      sock.connect(BRIDGE_PORT, BRIDGE_HOST);
    });
  }

  private setupSocketListeners(): void {
    if (!this.socket) return;

    this.socket.on('data', (data: Buffer) => {
      this.recvBuffer += data.toString('utf-8');
      this.processBuffer();
    });

    this.socket.on('close', () => {
      this.socket = null;
      for (const resolver of this.lineResolvers) {
        resolver('ERR|Connection closed');
      }
      this.lineResolvers = [];
    });

    this.socket.on('error', () => {
      this.disconnectSocket();
    });
  }

  private processBuffer(): void {
    while (this.recvBuffer.includes('\n')) {
      const nlIdx = this.recvBuffer.indexOf('\n');
      const line = this.recvBuffer.slice(0, nlIdx).trim();
      this.recvBuffer = this.recvBuffer.slice(nlIdx + 1);

      if (line && this.lineResolvers.length > 0) {
        const resolver = this.lineResolvers.shift()!;
        resolver(line);
      }
    }
  }

  private sendCommand(command: string): Promise<string> {
    return new Promise((resolve, reject) => {
      if (!this.socket || this.socket.destroyed) {
        reject(new Error('Not connected to bridge'));
        return;
      }

      const timer = setTimeout(() => {
        const idx = this.lineResolvers.indexOf(lineResolver);
        if (idx >= 0) this.lineResolvers.splice(idx, 1);
        reject(new Error(`Command timeout: ${command}`));
      }, COMMAND_TIMEOUT);

      const lineResolver = (line: string) => {
        clearTimeout(timer);
        resolve(line);
      };

      this.lineResolvers.push(lineResolver);
      this.socket.write(command + '\n');
    });
  }

  private parseResponse(resp: string): { ok: boolean; data: string } {
    if (resp.startsWith('OK|')) {
      return { ok: true, data: resp.slice(3) };
    }
    if (resp === 'OK') {
      return { ok: true, data: '' };
    }
    if (resp.startsWith('ERR|')) {
      return { ok: false, data: resp.slice(4) };
    }
    return { ok: false, data: resp };
  }

  private disconnectSocket(): void {
    if (this.socket) {
      try { this.socket.destroy(); } catch { /* ignore */ }
      this.socket = null;
    }
  }

  async readMemory(address: number, length: number): Promise<Uint8Array> {
    const addrHex = address.toString(16).toUpperCase();
    const resp = await this.sendCommand(`READ|${addrHex}|${length}`);
    const parsed = this.parseResponse(resp);
    if (!parsed.ok) {
      throw new Error(`READ failed: ${parsed.data}`);
    }
    const hexParts = parsed.data.split(' ').filter(Boolean);
    const bytes = new Uint8Array(hexParts.length);
    for (let i = 0; i < hexParts.length; i++) {
      bytes[i] = parseInt(hexParts[i], 16);
    }
    return bytes;
  }

  async writeMemory(address: number, data: Uint8Array): Promise<void> {
    const addrHex = address.toString(16).toUpperCase();
    const hexBytes = Array.from(data).map(b => b.toString(16).padStart(2, '0')).join(' ');
    const resp = await this.sendCommand(`WRITE|${addrHex}|${hexBytes}`);
    const parsed = this.parseResponse(resp);
    if (!parsed.ok) {
      throw new Error(`WRITE failed: ${parsed.data}`);
    }
  }

  async pressKey(keyName: string, frames = 2): Promise<void> {
    const keyId = KEY_MAP[keyName.toUpperCase()];
    if (keyId === undefined) {
      throw new Error(`Unknown key: ${keyName}`);
    }
    const resp = await this.sendCommand(`KEY|${keyId}|${frames}`);
    const parsed = this.parseResponse(resp);
    if (!parsed.ok) {
      throw new Error(`KEY failed: ${parsed.data}`);
    }
  }

  async pressKeyAndAdvance(keyName: string, frames: number): Promise<void> {
    const keyId = KEY_MAP[keyName.toUpperCase()];
    if (keyId === undefined) {
      throw new Error(`Unknown key: ${keyName}`);
    }
    const resp = await this.sendCommand(`KEYFRAMES|${keyId}|${frames}`);
    const parsed = this.parseResponse(resp);
    if (!parsed.ok) {
      throw new Error(`KEYFRAMES failed: ${parsed.data}`);
    }
    const frameMatch = parsed.data.match(/frame=(\d+)/);
    if (frameMatch) {
      this.frameCount = parseInt(frameMatch[1]);
    } else {
      this.frameCount += frames;
    }
  }

  async advanceFrames(count: number): Promise<void> {
    const resp = await this.sendCommand(`FRAMES|${count}`);
    const parsed = this.parseResponse(resp);
    if (!parsed.ok) {
      throw new Error(`FRAMES failed: ${parsed.data}`);
    }
    const frameMatch = parsed.data.match(/frame=(\d+)/);
    if (frameMatch) {
      this.frameCount = parseInt(frameMatch[1]);
    } else {
      this.frameCount += count;
    }
  }

  async getState(): Promise<Record<string, unknown>> {
    const resp = await this.sendCommand('STATE');
    const parsed = this.parseResponse(resp);
    if (!parsed.ok) {
      throw new Error(`STATE failed: ${parsed.data}`);
    }

    const parts = parsed.data.split('|');
    const state: Record<string, string> = {};
    for (const part of parts) {
      const eq = part.indexOf('=');
      if (eq >= 0) {
        state[part.slice(0, eq)] = part.slice(eq + 1);
      }
    }

    const frame = parseInt(state.frame ?? '0');
    this.frameCount = frame;

    const mapParts = (state.map ?? '0.0').split('.');
    const mapGroup = parseInt(mapParts[0] ?? '0');
    const mapNumber = parseInt(mapParts[1] ?? '0');

    const callback1 = parseInt(state.cb1 ?? '0', 16);

    // Read player position via gSaveBlock1Ptr (pointer at 0x03005008)
    const sb1PtrData = await this.readMemory(0x03005008, 4);
    const sb1Ptr = sb1PtrData[0] | (sb1PtrData[1] << 8) | (sb1PtrData[2] << 16) | (sb1PtrData[3] << 24);

    let playerX = 0;
    let playerY = 0;
    if (sb1Ptr >= 0x02000000 && sb1Ptr < 0x03000000) {
      playerX = await this.readU16(sb1Ptr);
      playerY = await this.readU16(sb1Ptr + 2);
    }

    const battleFlag = await this.readU8(0x030022C8);
    const textFlag = await this.readU8(0x020375c0);

    return {
      frameCount: frame,
      romLoaded: this.romLoaded,
      paused: false,
      fastForward: false,
      keysDown: [],
      hasSavedState: false,
      callback1,
      mapGroup,
      mapNumber,
      playerX,
      playerY,
      inBattle: battleFlag !== 0,
      textActive: textFlag !== 0,
    };
  }

  private async readU8(address: number): Promise<number> {
    const data = await this.readMemory(address, 1);
    return data[0] ?? 0;
  }

  private async readU16(address: number): Promise<number> {
    const data = await this.readMemory(address, 2);
    return (data[0] ?? 0) | ((data[1] ?? 0) << 8);
  }

  async screenshot(outputPath?: string): Promise<string> {
    const tmpPath = outputPath ?? `/tmp/mgba-screenshot-${Date.now()}.png`;

    try { fs.unlinkSync(tmpPath); } catch { /* ignore */ }

    const resp = await this.sendCommand(`SCREENSHOT|${tmpPath}`);
    const parsed = this.parseResponse(resp);
    if (!parsed.ok) {
      throw new Error(`SCREENSHOT failed: ${parsed.data}`);
    }

    for (let i = 0; i < 20; i++) {
      await new Promise(resolve => setTimeout(resolve, 50));
      try {
        const stat = fs.statSync(tmpPath);
        if (stat.size > 100) break;
      } catch { /* file not ready yet */ }
    }

    const imgData = fs.readFileSync(tmpPath);
    const base64 = imgData.toString('base64');

    if (!outputPath) {
      try { fs.unlinkSync(tmpPath); } catch { /* ignore */ }
    }

    return `data:image/png;base64,${base64}`;
  }

  async saveState(slot = 1): Promise<void> {
    const resp = await this.sendCommand(`SAVESTATE|${slot}`);
    const parsed = this.parseResponse(resp);
    if (!parsed.ok) {
      throw new Error(`SAVESTATE failed: ${parsed.data}`);
    }
  }

  async loadState(slot = 1): Promise<void> {
    const resp = await this.sendCommand(`LOADSTATE|${slot}`);
    const parsed = this.parseResponse(resp);
    if (!parsed.ok) {
      throw new Error(`LOADSTATE failed: ${parsed.data}`);
    }
  }

  async stop(): Promise<void> {
    this.disconnectSocket();

    if (this.process) {
      const proc = this.process;
      this.process = null;
      try { proc.kill('SIGTERM'); } catch { /* already exited */ }
      await new Promise<void>((resolve) => {
        const timer = setTimeout(() => {
          try { proc.kill('SIGKILL'); } catch { /* ignore */ }
          resolve();
        }, 2000);

        proc.on('exit', () => {
          clearTimeout(timer);
          resolve();
        });
      });
    }

    // On macOS, `mgba` shells out to `open -na mGBA.app --args ...` which
    // detaches the GUI process. Kill anything still bound to our TCP port so
    // the next test can start a fresh emulator cleanly.
    await this.killStaleBridge();

    this.romLoaded = false;
    this.frameCount = 0;
  }

  get isRunning(): boolean {
    return this.process !== null && this.process.exitCode === null;
  }

  get isConnected(): boolean {
    return this.socket !== null && !this.socket.destroyed;
  }

  get currentFrame(): number {
    return this.frameCount;
  }

  createEmulatorControl(): EmulatorControl {
    return {
      loadRom: async (romPath: string) => {
        await this.startMgba(romPath);
      },
      readMemory: (_address: number, length: number): Uint8Array => {
        return new Uint8Array(length);
      },
      writeMemory: () => {},
      keyDown: (key: string) => {
        this.pressKey(key, 2).catch(() => {});
      },
      keyUp: () => {},
      advanceFrames: async (count: number) => {
        await this.advanceFrames(count);
      },
      getState: () => ({
        frameCount: this.frameCount,
        romLoaded: this.romLoaded,
        paused: false,
      }),
      screenshot: async () => {
        return await this.screenshot();
      },
      saveState: async () => {
        await this.saveState();
      },
      loadState: async () => {
        await this.loadState();
      },
      setFastForward: () => {},
      pause: () => {},
      resume: () => {},
    };
  }
}
