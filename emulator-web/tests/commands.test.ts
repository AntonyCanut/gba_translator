import { describe, it, expect } from 'vitest';
import { parseCommand, CommandError } from '../src/commands.js';

describe('parseCommand', () => {
  describe('LOAD_ROM', () => {
    it('parses LOAD_ROM with path', () => {
      const cmd = parseCommand('LOAD_ROM /path/to/rom.gba');
      expect(cmd.type).toBe('LOAD_ROM');
      expect(cmd.args[0]).toBe('/path/to/rom.gba');
    });

    it('handles paths with spaces', () => {
      const cmd = parseCommand('LOAD_ROM /path/to/my rom.gba');
      expect(cmd.args[0]).toBe('/path/to/my rom.gba');
    });

    it('throws on missing path', () => {
      expect(() => parseCommand('LOAD_ROM')).toThrow(CommandError);
    });
  });

  describe('READ_MEMORY', () => {
    it('parses hex address', () => {
      const cmd = parseCommand('READ_MEMORY 0x02021D18 16');
      expect(cmd.type).toBe('READ_MEMORY');
      expect(cmd.args).toEqual(['0x02021D18', '16']);
    });

    it('parses decimal address', () => {
      const cmd = parseCommand('READ_MEMORY 33693976 16');
      expect(cmd.type).toBe('READ_MEMORY');
      expect(cmd.args).toEqual(['33693976', '16']);
    });

    it('throws on missing args', () => {
      expect(() => parseCommand('READ_MEMORY 0x1234')).toThrow(CommandError);
    });

    it('throws on invalid address', () => {
      expect(() => parseCommand('READ_MEMORY xyz 16')).toThrow(CommandError);
    });

    it('throws on non-positive length', () => {
      expect(() => parseCommand('READ_MEMORY 0x1234 0')).toThrow(CommandError);
    });
  });

  describe('WRITE_MEMORY', () => {
    it('parses valid write', () => {
      const cmd = parseCommand('WRITE_MEMORY 0x02021D18 48656C6C6F');
      expect(cmd.type).toBe('WRITE_MEMORY');
      expect(cmd.args).toEqual(['0x02021D18', '48656C6C6F']);
    });

    it('throws on invalid hex data', () => {
      expect(() => parseCommand('WRITE_MEMORY 0x1234 ZZZZ')).toThrow(CommandError);
    });
  });

  describe('KEY_DOWN / KEY_UP', () => {
    it('parses valid keys', () => {
      for (const key of ['A', 'B', 'START', 'SELECT', 'UP', 'DOWN', 'LEFT', 'RIGHT', 'L', 'R']) {
        const cmd = parseCommand(`KEY_DOWN ${key}`);
        expect(cmd.type).toBe('KEY_DOWN');
        expect(cmd.args[0]).toBe(key);
      }
    });

    it('normalizes key case', () => {
      const cmd = parseCommand('KEY_DOWN start');
      expect(cmd.args[0]).toBe('START');
    });

    it('throws on invalid key', () => {
      expect(() => parseCommand('KEY_DOWN X')).toThrow(CommandError);
    });

    it('throws on missing key', () => {
      expect(() => parseCommand('KEY_UP')).toThrow(CommandError);
    });
  });

  describe('ADVANCE_FRAMES', () => {
    it('parses frame count', () => {
      const cmd = parseCommand('ADVANCE_FRAMES 60');
      expect(cmd.type).toBe('ADVANCE_FRAMES');
      expect(cmd.args[0]).toBe('60');
    });

    it('throws on missing count', () => {
      expect(() => parseCommand('ADVANCE_FRAMES')).toThrow(CommandError);
    });

    it('throws on negative count', () => {
      expect(() => parseCommand('ADVANCE_FRAMES -1')).toThrow(CommandError);
    });
  });

  describe('FAST_FORWARD', () => {
    it('parses true/false', () => {
      expect(parseCommand('FAST_FORWARD true').args[0]).toBe('true');
      expect(parseCommand('FAST_FORWARD false').args[0]).toBe('false');
      expect(parseCommand('FAST_FORWARD 1').args[0]).toBe('1');
      expect(parseCommand('FAST_FORWARD 0').args[0]).toBe('0');
    });

    it('throws on invalid value', () => {
      expect(() => parseCommand('FAST_FORWARD maybe')).toThrow(CommandError);
    });
  });

  describe('No-arg commands', () => {
    for (const cmd of ['GET_STATE', 'SCREENSHOT', 'SAVE_STATE', 'LOAD_STATE', 'PAUSE', 'RESUME']) {
      it(`parses ${cmd}`, () => {
        const result = parseCommand(cmd);
        expect(result.type).toBe(cmd);
        expect(result.args).toEqual([]);
      });
    }
  });

  describe('Error handling', () => {
    it('throws on empty input', () => {
      expect(() => parseCommand('')).toThrow(CommandError);
      expect(() => parseCommand('   ')).toThrow(CommandError);
    });

    it('throws on unknown command', () => {
      expect(() => parseCommand('EXPLODE')).toThrow(CommandError);
    });

    it('is case-insensitive for command names', () => {
      const cmd = parseCommand('get_state');
      expect(cmd.type).toBe('GET_STATE');
    });
  });
});
