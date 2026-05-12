import { describe, it, expect } from 'vitest';
import { decodePokemonText, encodePokemonText, POKEMON_TERMINATOR } from '../src/charmap.js';

describe('decodePokemonText', () => {
  it('decodes uppercase letters', () => {
    const data = new Uint8Array([0xbb, 0xbc, 0xbd, POKEMON_TERMINATOR]);
    expect(decodePokemonText(data)).toBe('ABC');
  });

  it('decodes lowercase letters', () => {
    const data = new Uint8Array([0xd5, 0xd6, 0xd7, POKEMON_TERMINATOR]);
    expect(decodePokemonText(data)).toBe('abc');
  });

  it('decodes digits', () => {
    const data = new Uint8Array([0xa1, 0xa2, 0xa3, POKEMON_TERMINATOR]);
    expect(decodePokemonText(data)).toBe('012');
  });

  it('decodes spaces', () => {
    const data = new Uint8Array([0xbb, 0x00, 0xbc, POKEMON_TERMINATOR]);
    expect(decodePokemonText(data)).toBe('A B');
  });

  it('decodes punctuation', () => {
    const data = new Uint8Array([0xab, 0xac, 0xad, 0xae, 0xb8, POKEMON_TERMINATOR]);
    expect(decodePokemonText(data)).toBe('!?.-,');
  });

  it('decodes accented characters (French/Spanish)', () => {
    const data = new Uint8Array([0x84, 0xe0, 0xdd, 0xe7, 0xd9, POKEMON_TERMINATOR]); // É l i s e
    expect(decodePokemonText(data)).toBe('Élise');
  });

  it('stops at terminator', () => {
    const data = new Uint8Array([0xbb, 0xbc, POKEMON_TERMINATOR, 0xbd, 0xbe]);
    expect(decodePokemonText(data)).toBe('AB');
  });

  it('handles empty data (just terminator)', () => {
    const data = new Uint8Array([POKEMON_TERMINATOR]);
    expect(decodePokemonText(data)).toBe('');
  });

  it('handles newline byte', () => {
    const data = new Uint8Array([0xbb, 0xfe, 0xbc, POKEMON_TERMINATOR]);
    expect(decodePokemonText(data)).toBe('A\nB');
  });

  it('skips FC control codes (2 bytes)', () => {
    const data = new Uint8Array([0xbb, 0xfc, 0x01, 0xbc, POKEMON_TERMINATOR]);
    expect(decodePokemonText(data)).toBe('AB');
  });

  it('skips FD control codes (2 bytes)', () => {
    const data = new Uint8Array([0xbb, 0xfd, 0x02, 0xbc, POKEMON_TERMINATOR]);
    expect(decodePokemonText(data)).toBe('AB');
  });

  it('skips F7 control codes (3 bytes)', () => {
    const data = new Uint8Array([0xbb, 0xf7, 0x01, 0x02, 0xbc, POKEMON_TERMINATOR]);
    expect(decodePokemonText(data)).toBe('AB');
  });

  it('preserves unknown bytes when flag is set', () => {
    const data = new Uint8Array([0xbb, 0x99, 0xbc, POKEMON_TERMINATOR]);
    expect(decodePokemonText(data, true)).toBe('A<0x99>B');
  });

  it('replaces unknown bytes with ? by default', () => {
    const data = new Uint8Array([0xbb, 0x99, 0xbc, POKEMON_TERMINATOR]);
    expect(decodePokemonText(data)).toBe('A?B');
  });

  it('decodes a full Pokemon-style string', () => {
    // "Hello!" in Pokemon encoding
    const data = new Uint8Array([
      0xc2, 0xd9, 0xe0, 0xe0, 0xe3, 0xab, POKEMON_TERMINATOR,
    ]);
    expect(decodePokemonText(data)).toBe('Hello!');
  });

  it('decodes accented French characters', () => {
    const data = new Uint8Array([0x16, POKEMON_TERMINATOR]); // à
    expect(decodePokemonText(data)).toBe('à');

    const data2 = new Uint8Array([0x19, POKEMON_TERMINATOR]); // ç
    expect(decodePokemonText(data2)).toBe('ç');

    const data3 = new Uint8Array([0x1a, POKEMON_TERMINATOR]); // è
    expect(decodePokemonText(data3)).toBe('è');
  });
});

describe('encodePokemonText', () => {
  it('encodes basic text', () => {
    const result = encodePokemonText('AB');
    expect(result).toEqual(new Uint8Array([0xbb, 0xbc, POKEMON_TERMINATOR]));
  });

  it('encodes lowercase', () => {
    const result = encodePokemonText('abc');
    expect(result).toEqual(new Uint8Array([0xd5, 0xd6, 0xd7, POKEMON_TERMINATOR]));
  });

  it('encodes spaces', () => {
    const result = encodePokemonText('A B');
    expect(result).toEqual(new Uint8Array([0xbb, 0x00, 0xbc, POKEMON_TERMINATOR]));
  });

  it('roundtrips text', () => {
    const original = 'Hello World!';
    const encoded = encodePokemonText(original);
    const decoded = decodePokemonText(encoded);
    expect(decoded).toBe(original);
  });

  it('adds terminator', () => {
    const result = encodePokemonText('A');
    expect(result[result.length - 1]).toBe(POKEMON_TERMINATOR);
  });
});
