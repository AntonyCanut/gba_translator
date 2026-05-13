// Browser entry point for gbajs GBA emulator
// Bundled with esbuild for use in index.html

// Shim Node.js Buffer global so gbajs memory-view.js doesn't break
if (typeof window !== 'undefined' && !window.Buffer) {
  window.Buffer = { isBuffer: function() { return false; } };
}

var GameBoyAdvance = require('gbajs');

var GBA_KEYS = {
  A: 0, B: 1, SELECT: 2, START: 3,
  RIGHT: 4, LEFT: 5, UP: 6, DOWN: 7,
  R: 8, L: 9,
};

function GBAEmulatorReal(canvas) {
  this.canvas = canvas;
  this.gba = new GameBoyAdvance();
  this.frameCount = 0;
  this.romLoaded = false;
  this.paused = false;
  this.fastForwardEnabled = false;
  this.keysDown = new Set();
  this.savedFrost = null;

  this.gba.logLevel = this.gba.LOG_ERROR;
  this.gba.setLogger(function(level, msg) {
    if (level & 1) console.error('[GBA]', msg);
  });

  // Set up canvas rendering — use setCanvasDirect to avoid
  // offsetWidth/offsetHeight issues in headless browsers
  if (canvas && canvas.getContext) {
    var ctx = canvas.getContext('2d');
    this.gba.setCanvasDirect(canvas);
    this.gba.video.finishDraw = function(pixelData) {
      ctx.putImageData(pixelData, 0, 0);
      this.drawCallback();
    };
  }

  // Load the stub BIOS (HLE mode)
  var biosBuffer = new ArrayBuffer(0x4000);
  this.gba.setBios(biosBuffer, false);
}

GBAEmulatorReal.prototype.loadRom = function(url) {
  var self = this;
  return fetch(url)
    .then(function(r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.arrayBuffer();
    })
    .then(function(buffer) {
      var result = self.gba.setRom(buffer);
      if (!result) throw new Error('Invalid ROM');
      self.romLoaded = true;
      self.frameCount = 0;

      // Skip BIOS boot: initialize CPU state as if BIOS had run
      self.gba.cpu.gprs[13] = 0x03007F00; // SP_usr/sys
      self.gba.cpu.gprs[self.gba.cpu.PC] = 0x08000000 + self.gba.cpu.WORD_SIZE_ARM;
      self.gba.cpu.instruction = null;
      self.gba.irq.resetSP();
      self.gba.cpu.loadInstruction = self.gba.cpu.loadInstructionArm;
      self.gba.cpu.execMode = self.gba.cpu.MODE_ARM;
      self.gba.cpu.instructionWidth = self.gba.cpu.WORD_SIZE_ARM;

      // Render first frame
      self.gba.advanceFrame();
      self.frameCount = 1;

      return true;
    });
};

GBAEmulatorReal.prototype.readMemory = function(address, length) {
  var result = new Uint8Array(length);
  for (var i = 0; i < length; i++) {
    try {
      result[i] = this.gba.mmu.loadU8((address + i) >>> 0) & 0xFF;
    } catch (e) {
      result[i] = 0;
    }
  }
  return result;
};

GBAEmulatorReal.prototype.writeMemory = function(address, data) {
  for (var i = 0; i < data.length; i++) {
    try {
      this.gba.mmu.store8((address + i) >>> 0, data[i]);
    } catch (e) {
      // Ignore write errors to read-only regions
    }
  }
};

GBAEmulatorReal.prototype.readU8 = function(address) {
  try {
    return this.gba.mmu.loadU8(address >>> 0) & 0xFF;
  } catch (e) {
    return 0;
  }
};

GBAEmulatorReal.prototype.readU16 = function(address) {
  try {
    return this.gba.mmu.loadU16(address >>> 0) & 0xFFFF;
  } catch (e) {
    return 0;
  }
};

GBAEmulatorReal.prototype.readU32 = function(address) {
  try {
    var val = this.gba.mmu.load32(address >>> 0);
    return val >>> 0;
  } catch (e) {
    return 0;
  }
};

GBAEmulatorReal.prototype.keyDown = function(key) {
  var keyIndex = GBA_KEYS[key.toUpperCase()];
  if (keyIndex !== undefined) {
    this.keysDown.add(key.toUpperCase());
    this.gba.keypad.keydown(keyIndex);
  }
};

GBAEmulatorReal.prototype.keyUp = function(key) {
  var keyIndex = GBA_KEYS[key.toUpperCase()];
  if (keyIndex !== undefined) {
    this.keysDown.delete(key.toUpperCase());
    this.gba.keypad.keyup(keyIndex);
  }
};

GBAEmulatorReal.prototype.advanceFrames = function(count) {
  for (var i = 0; i < count; i++) {
    try {
      this.gba.advanceFrame();
    } catch (e) {
      // Non-fatal: gbajs may hit unimplemented features.
      // Reset the frame state so the next frame can proceed.
      this.gba.seenFrame = true;
    }
    this.frameCount++;
  }
};

GBAEmulatorReal.prototype.screenshot = function() {
  return this.canvas.toDataURL('image/png');
};

GBAEmulatorReal.prototype.saveState = function() {
  try {
    this.savedFrost = this.gba.freeze();
  } catch (e) {
    console.error('[GBA] Save state error:', e);
  }
};

GBAEmulatorReal.prototype.loadSavedState = function() {
  if (!this.savedFrost) return false;
  try {
    this.gba.defrost(this.savedFrost);
    return true;
  } catch (e) {
    console.error('[GBA] Load state error:', e);
    return false;
  }
};

GBAEmulatorReal.prototype.getState = function() {
  var ADDR = {
    callback1:  0x030030f0,
    mapGroup:   0x02036dfc,
    mapNumber:  0x02036dfe,
    playerX:    0x02037078,
    playerY:    0x0203707a,
    battleFlag: 0x02023e8a,
    textFlag:   0x020375c0,
  };
  return {
    frameCount: this.frameCount,
    romLoaded: this.romLoaded,
    paused: this.paused,
    fastForward: this.fastForwardEnabled,
    keysDown: Array.from(this.keysDown),
    hasSavedState: !!this.savedFrost,
    callback1: this.readU32(ADDR.callback1),
    mapGroup: this.readU16(ADDR.mapGroup),
    mapNumber: this.readU16(ADDR.mapNumber),
    playerX: this.readU16(ADDR.playerX),
    playerY: this.readU16(ADDR.playerY),
    inBattle: this.readU8(ADDR.battleFlag) !== 0,
    textActive: this.readU8(ADDR.textFlag) !== 0,
  };
};

GBAEmulatorReal.prototype.pause = function() {
  this.paused = true;
  this.gba.pause();
};

GBAEmulatorReal.prototype.resume = function() {
  this.paused = false;
};

GBAEmulatorReal.prototype.setFastForward = function(enabled) {
  this.fastForwardEnabled = enabled;
};

// Expose globally
window.GBAEmulatorReal = GBAEmulatorReal;
