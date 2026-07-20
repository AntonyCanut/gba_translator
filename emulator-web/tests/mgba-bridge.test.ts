import { describe, expect, it } from 'vitest';
import { buildMgbaCommand } from '../src/mgba-bridge.js';

describe('buildMgbaCommand', () => {
  it('configures every writable mGBA path next to the ROM', () => {
    // Arrange
    const romPath = '/private/var/folders/test run/game.gba';

    // Act
    const command = buildMgbaCommand(
      '/opt/homebrew/bin/mgba',
      '/project/bridge.lua',
      romPath,
      true,
    );

    // Assert
    expect(command).toEqual([
      '/opt/homebrew/bin/mgba',
      '--script',
      '/project/bridge.lua',
      '-C',
      'audioSync=0',
      '-C',
      'videoSync=0',
      '-C',
      'mute=1',
      '-C',
      'savegamePath=/private/var/folders/test run',
      '-C',
      'savestatePath=/private/var/folders/test run',
      '-C',
      'screenshotPath=/private/var/folders/test run',
      '-C',
      'cheatsPath=/private/var/folders/test run',
      romPath,
    ]);
  });
});
