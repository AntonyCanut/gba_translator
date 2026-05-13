import { build } from 'esbuild';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outfile = path.join(__dirname, 'src/public/gba-bundle.js');

// Patch gbajs bugs and compatibility issues before bundling
const patchPlugin = {
  name: 'gbajs-patch',
  setup(build) {
    build.onLoad({ filter: /gbajs[\\/]js[\\/]video[\\/]software\.js$/ }, async (args) => {
      let contents = fs.readFileSync(args.path, 'utf8');
      // Fix comma-instead-of-dot typo: `this,objwinActive` -> `this.objwinActive`
      contents = contents.replace('this,objwinActive', 'this.objwinActive');
      return { contents, loader: 'js' };
    });

    build.onLoad({ filter: /gbajs[\\/]js[\\/]irq\.js$/ }, async (args) => {
      let contents = fs.readFileSync(args.path, 'utf8');
      // Replace crash on unimplemented SWI with a warning log.
      // Games (especially ROM hacks) may use non-standard SWI calls.
      contents = contents.replace(
        'throw "Unimplemented software interrupt: 0x" + opcode.toString(16);',
        'this.core.WARN("Unimplemented software interrupt: 0x" + opcode.toString(16)); break;'
      );
      return { contents, loader: 'js' };
    });
  },
};

const result = await build({
  entryPoints: [path.join(__dirname, 'src/browser-gba.js')],
  bundle: true,
  write: false,
  platform: 'browser',
  format: 'iife',
  target: 'es2020',
  alias: {
    'fs': path.join(__dirname, 'src/browser-shims/fs.cjs'),
    'pngjs': path.join(__dirname, 'src/browser-shims/pngjs.cjs'),
    'buffer-dataview': path.join(__dirname, 'src/browser-shims/buffer-dataview.cjs'),
  },
  define: {
    'global': 'window',
  },
  plugins: [patchPlugin],
  logLevel: 'info',
});

// gbajs uses implicit globals (addr, etc.) that break under strict mode.
// Remove the "use strict" directive so the emulator runs correctly.
let code = new TextDecoder().decode(result.outputFiles[0].contents);
code = code.replace(/^"use strict";\n/, '');
fs.writeFileSync(outfile, code);
console.log(`  ${outfile}  ${(code.length / 1024).toFixed(1)}kb`);
