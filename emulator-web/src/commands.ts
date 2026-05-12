export type CommandType =
  | 'LOAD_ROM'
  | 'READ_MEMORY'
  | 'WRITE_MEMORY'
  | 'KEY_DOWN'
  | 'KEY_UP'
  | 'ADVANCE_FRAMES'
  | 'GET_STATE'
  | 'SCREENSHOT'
  | 'SAVE_STATE'
  | 'LOAD_STATE'
  | 'FAST_FORWARD'
  | 'PAUSE'
  | 'RESUME';

export interface ParsedCommand {
  type: CommandType;
  args: string[];
}

const VALID_KEYS = new Set([
  'A', 'B', 'START', 'SELECT',
  'UP', 'DOWN', 'LEFT', 'RIGHT',
  'L', 'R',
]);

const NO_ARG_COMMANDS = new Set<CommandType>([
  'GET_STATE', 'SCREENSHOT', 'SAVE_STATE', 'LOAD_STATE', 'PAUSE', 'RESUME',
]);

export function parseCommand(raw: string): ParsedCommand {
  const trimmed = raw.trim();
  if (!trimmed) {
    throw new CommandError('Empty command');
  }

  const parts = trimmed.split(/\s+/);
  const type = parts[0].toUpperCase() as CommandType;
  const args = parts.slice(1);

  switch (type) {
    case 'LOAD_ROM':
      if (args.length < 1) throw new CommandError('LOAD_ROM requires a path argument');
      return { type, args: [args.join(' ')] };

    case 'READ_MEMORY':
      if (args.length < 2) throw new CommandError('READ_MEMORY requires <addr> <len>');
      validateHexOrNumber(args[0], 'address');
      validatePositiveInt(args[1], 'length');
      return { type, args };

    case 'WRITE_MEMORY':
      if (args.length < 2) throw new CommandError('WRITE_MEMORY requires <addr> <hex>');
      validateHexOrNumber(args[0], 'address');
      if (!/^[0-9a-fA-F]+$/.test(args[1])) {
        throw new CommandError('WRITE_MEMORY hex data must be valid hex string');
      }
      return { type, args };

    case 'KEY_DOWN':
    case 'KEY_UP':
      if (args.length < 1) throw new CommandError(`${type} requires a key name`);
      if (!VALID_KEYS.has(args[0].toUpperCase())) {
        throw new CommandError(`Invalid key: ${args[0]}. Valid: ${[...VALID_KEYS].join(', ')}`);
      }
      return { type, args: [args[0].toUpperCase()] };

    case 'ADVANCE_FRAMES':
      if (args.length < 1) throw new CommandError('ADVANCE_FRAMES requires <n>');
      validatePositiveInt(args[0], 'frame count');
      return { type, args };

    case 'FAST_FORWARD':
      if (args.length < 1) throw new CommandError('FAST_FORWARD requires <enabled>');
      if (!['true', 'false', '1', '0'].includes(args[0].toLowerCase())) {
        throw new CommandError('FAST_FORWARD enabled must be true/false/1/0');
      }
      return { type, args: [args[0].toLowerCase()] };

    case 'GET_STATE':
    case 'SCREENSHOT':
    case 'SAVE_STATE':
    case 'LOAD_STATE':
    case 'PAUSE':
    case 'RESUME':
      return { type, args: [] };

    default:
      throw new CommandError(`Unknown command: ${type}`);
  }
}

function validateHexOrNumber(value: string, name: string): void {
  if (/^0x[0-9a-fA-F]+$/.test(value)) return;
  if (/^\d+$/.test(value)) return;
  throw new CommandError(`${name} must be a hex (0x...) or decimal number, got: ${value}`);
}

function validatePositiveInt(value: string, name: string): void {
  const num = parseInt(value, 10);
  if (isNaN(num) || num <= 0) {
    throw new CommandError(`${name} must be a positive integer, got: ${value}`);
  }
}

export class CommandError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'CommandError';
  }
}

export { VALID_KEYS };
