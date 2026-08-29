"use strict";

// Backward-compatible manual diagnostic entrypoint kept under the filename used
// during the live 2026-08-29 experiment. The production implementation lives in
// dzen-collections.js so local overlays do not accumulate versioned debug files.
const collections = require("./dzen-collections");

if (require.main === module) {
  collections.main(process.argv.slice(2)).catch((error) => {
    console.error(error.stack || error.message);
    process.exitCode = 1;
  });
}
