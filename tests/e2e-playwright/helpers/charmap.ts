export const POKEMON_TERMINATOR = 0xff;
export const POKEMON_NEWLINE = 0xfe;

const BYTE_TO_CHAR: Map<number, string> = new Map([
  [0x00, ' '],
  // Digits
  [0xa1, '0'], [0xa2, '1'], [0xa3, '2'], [0xa4, '3'], [0xa5, '4'],
  [0xa6, '5'], [0xa7, '6'], [0xa8, '7'], [0xa9, '8'], [0xaa, '9'],
  // Punctuation
  [0xab, '!'], [0xac, '?'], [0xad, '.'], [0xae, '-'], [0xb0, '"'],
  [0xb4, "'"], [0xb8, ','], [0xba, '/'], [0xf0, ':'],
  // Uppercase
  [0xbb, 'A'], [0xbc, 'B'], [0xbd, 'C'], [0xbe, 'D'], [0xbf, 'E'],
  [0xc0, 'F'], [0xc1, 'G'], [0xc2, 'H'], [0xc3, 'I'], [0xc4, 'J'],
  [0xc5, 'K'], [0xc6, 'L'], [0xc7, 'M'], [0xc8, 'N'], [0xc9, 'O'],
  [0xca, 'P'], [0xcb, 'Q'], [0xcc, 'R'], [0xcd, 'S'], [0xce, 'T'],
  [0xcf, 'U'], [0xd0, 'V'], [0xd1, 'W'], [0xd2, 'X'], [0xd3, 'Y'],
  [0xd4, 'Z'],
  // Lowercase
  [0xd5, 'a'], [0xd6, 'b'], [0xd7, 'c'], [0xd8, 'd'], [0xd9, 'e'],
  [0xda, 'f'], [0xdb, 'g'], [0xdc, 'h'], [0xdd, 'i'], [0xde, 'j'],
  [0xdf, 'k'], [0xe0, 'l'], [0xe1, 'm'], [0xe2, 'n'], [0xe3, 'o'],
  [0xe4, 'p'], [0xe5, 'q'], [0xe6, 'r'], [0xe7, 's'], [0xe8, 't'],
  [0xe9, 'u'], [0xea, 'v'], [0xeb, 'w'], [0xec, 'x'], [0xed, 'y'],
  [0xee, 'z'],
  // Accented (CFRU/Unbound extended)
  [0x82, 'À'], [0x83, 'È'], [0x84, 'É'],
  [0x16, 'à'], [0x17, 'á'], [0x19, 'ç'], [0x1a, 'è'], [0x1b, 'é'],
  [0x20, 'î'], [0x23, 'ó'], [0x27, 'ú'], [0x29, 'ñ'],
  [0x68, 'â'], [0x7f, 'ù'],
  // Newline
  [0xfe, '\n'],
]);

const CHAR_TO_BYTE: Map<string, number> = new Map();
for (const [byte, char] of BYTE_TO_CHAR) {
  if (!CHAR_TO_BYTE.has(char)) {
    CHAR_TO_BYTE.set(char, byte);
  }
}

const MULTI_BYTE_LEADERS = new Set([0xfc, 0xfd, 0xf8, 0xf9, 0xf7]);

function controlCodeLength(leader: number): number {
  switch (leader) {
    case 0xfc: return 2;
    case 0xfd: return 2;
    case 0xf8: return 2;
    case 0xf9: return 2;
    case 0xf7: return 3;
    default: return 1;
  }
}

export function decodePokemonText(data: Uint8Array): string {
  const result: string[] = [];
  let i = 0;
  while (i < data.length) {
    const byte = data[i];
    if (byte === POKEMON_TERMINATOR) break;

    if (MULTI_BYTE_LEADERS.has(byte)) {
      i += controlCodeLength(byte);
      continue;
    }

    const char = BYTE_TO_CHAR.get(byte);
    if (char !== undefined) {
      result.push(char);
    } else {
      result.push('?');
    }
    i++;
  }
  return result.join('');
}

export function encodePokemonText(text: string): Uint8Array {
  const bytes: number[] = [];
  for (const char of text) {
    const byte = CHAR_TO_BYTE.get(char);
    if (byte !== undefined) {
      bytes.push(byte);
    } else {
      bytes.push(0xac); // '?' fallback
    }
  }
  bytes.push(POKEMON_TERMINATOR);
  return new Uint8Array(bytes);
}

export function hexToBytes(hex: string): Uint8Array {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) {
    bytes[i / 2] = parseInt(hex.substring(i, i + 2), 16);
  }
  return bytes;
}
