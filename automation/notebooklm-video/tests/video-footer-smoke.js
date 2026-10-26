"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const footer = require("../video-footer.js");

async function main() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "video-footer-smoke-"));
  try {
    assert.equal(footer.FOOTER_SECONDS, 5);
    assert.equal(footer.FOOTER_FILENAME, "_footer-vid.png");
    const src = path.join(dir, "original.mp4");
    const img = path.join(dir, "_footer-vid.png");
    const dst = path.join(dir, "output.mp4");
    fs.writeFileSync(src, "synthetic nonempty mp4");
    fs.writeFileSync(img, "not a png");
    await assert.rejects(footer.appendFooter({
      sourcePath: src, footerPath: img, outputPath: dst, rootDir: dir,
    }), /не является PNG/);
    assert.equal(fs.existsSync(dst), false);
    fs.writeFileSync(img, Buffer.from("89504e470d0a1a0a", "hex"));
    fs.writeFileSync(dst, "operator-owned file");
    await assert.rejects(footer.appendFooter({
      sourcePath: src, footerPath: img, outputPath: dst, rootDir: dir,
    }), /уже существует/);
    assert.equal(fs.readFileSync(dst, "utf8"), "operator-owned file");
    await assert.rejects(footer.appendFooter({
      sourcePath: src, footerPath: img, outputPath: src, rootDir: dir,
    }), /разными файлами/);

    const worker = fs.readFileSync(path.join(__dirname, "..", "worker.js"), "utf8");
    const download = worker.indexOf("await download.saveAs(downloadPath)");
    const checkpoint = worker.indexOf('job.status = "DOWNLOADED"');
    const finalize = worker.indexOf("await finalizeDownloadedVideo(config, publication, job, state);", checkpoint);
    assert(download >= 0 && download < checkpoint && checkpoint < finalize);
    const f = worker.slice(worker.indexOf("async function finalizeDownloadedVideo("),
      worker.indexOf("async function checkAndDownload("));
    assert(f.indexOf("videoFooter.appendFooter") < f.indexOf('job.status = "DONE"'));
    assert(f.indexOf('job.status = "DONE"') < f.indexOf("ensureSuccessRegistryEntry"));
    assert(f.indexOf("ensureSuccessRegistryEntry") < f.indexOf("ensureFtpDelivery"));
    assert(worker.includes('if (job?.status === "DOWNLOADED") {'));
    assert(worker.includes('if (job?.status === "DONE") {'));
    console.log("PASS: video-footer safe input checks and download/processing/FTP ordering.");
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
