"use strict";

// Offline, fail-closed video post-processing. No browser, API, state or publication access.
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const { spawn } = require("child_process");

const FOOTER_SECONDS = 5;
const FOOTER_FILENAME = "_footer-vid.png";

function findTool(name, rootDir) {
  const executable = `${name}${process.platform === "win32" ? ".exe" : ""}`;
  for (const candidate of [
    path.join(rootDir, "bin", executable),
    path.join(rootDir, "tools", "ffmpeg", "bin", executable),
  ]) {
    if (fs.existsSync(candidate)) return candidate;
  }
  // Fallback to PATH; caller sees a clear error if the binary is absent.
  return executable;
}

function runTool(command, args, timeoutMs) {
  return new Promise((resolve, reject) => {
    let output = "";
    let stderr = "";
    let finished = false;
    const child = spawn(command, args, { windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
    const timer = setTimeout(() => {
      child.kill();
      finish(new Error(`${path.basename(command)} превысил лимит ${timeoutMs} мс`));
    }, timeoutMs);
    function finish(error, result) {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      if (error) reject(error);
      else resolve(result);
    }
    child.stdout.on("data", (data) => { output = (output + data.toString()).slice(-65536); });
    child.stderr.on("data", (data) => { stderr = (stderr + data.toString()).slice(-8192); });
    child.on("error", (error) => finish(new Error(`Не удалось запустить ${command}: ${error.message}`)));
    child.on("close", (code) => finish(code === 0 ? null : new Error(
      `${path.basename(command)} завершился с кодом ${code}: ${stderr.slice(-1000)}`
    ), output));
  });
}

function assertFile(file, name) {
  const stat = fs.statSync(file, { throwIfNoEntry: false });
  if (!stat || !stat.isFile() || stat.size === 0) {
    throw new Error(`${name} отсутствует или пуст: ${file}`);
  }
}

async function probe(file, ffprobe) {
  const data = JSON.parse(await runTool(ffprobe, [
    "-v", "error", "-select_streams", "v:0", "-show_entries",
    "format=duration:stream=width,height", "-of", "json", file,
  ], 30000));
  const stream = data.streams && data.streams[0];
  const width = Number(stream && stream.width);
  const height = Number(stream && stream.height);
  const duration = Number(data.format && data.format.duration);
  if (!Number.isInteger(width) || width < 2 || width % 2 ||
      !Number.isInteger(height) || height < 2 || height % 2 ||
      !Number.isFinite(duration) || duration <= 0) {
    throw new Error(`Неверные параметры MP4: ${file}`);
  }
  return { width, height, duration };
}

function sha256(file) {
  return new Promise((resolve, reject) => {
    const digest = crypto.createHash("sha256");
    const stream = fs.createReadStream(file);
    stream.on("data", (block) => digest.update(block));
    stream.on("error", reject);
    stream.on("end", () => resolve(digest.digest("hex")));
  });
}

async function appendFooter({ sourcePath, footerPath, outputPath, rootDir }) {
  if (![sourcePath, footerPath, outputPath, rootDir].every((p) => typeof p === "string" && p.trim())) {
    throw new Error("Нужны sourcePath, footerPath, outputPath и rootDir");
  }
  const src = path.resolve(sourcePath);
  const img = path.resolve(footerPath);
  const dst = path.resolve(outputPath);
  if (new Set([src, img, dst]).size !== 3) throw new Error("Исходник, PNG и результат должны быть разными файлами");
  assertFile(src, "Оригинал MP4");
  assertFile(img, "PNG заставки");
  if (!fs.readFileSync(img).subarray(0, 8).equals(Buffer.from("89504e470d0a1a0a", "hex"))) {
    throw new Error(`Файл заставки не является PNG: ${img}`);
  }
  if (fs.existsSync(dst)) throw new Error(`Итоговый MP4 уже существует. Без перезаписи: ${dst}`);

  const ffmpeg = findTool("ffmpeg", rootDir);
  const ffprobe = findTool("ffprobe", rootDir);
  const input = await probe(src, ffprobe);
  const { width: w, height: h } = input;
  const normalize = `fps=30,scale=${w}:${h}:force_original_aspect_ratio=decrease:flags=lanczos,pad=${w}:${h}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p`;
  const filter = `[0:v:0]${normalize},setpts=PTS-STARTPTS[base];[1:v:0]${normalize},trim=duration=${FOOTER_SECONDS},setpts=PTS-STARTPTS[footer];[base][footer]concat=n=2:v=1:a=0[v]`;
  const temp = path.join(path.dirname(dst), `.${path.basename(dst)}.footer-${crypto.randomUUID()}.mp4`);
  try {
    await runTool(ffmpeg, [
      "-hide_banner", "-nostdin", "-nostats", "-loglevel", "error",
      "-i", src, "-loop", "1", "-framerate", "30", "-t", String(FOOTER_SECONDS), "-i", img,
      "-filter_complex", filter, "-map", "[v]", "-map", "0:a?",
      "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
      "-c:a", "copy", "-movflags", "+faststart", temp,
    ], 60 * 60 * 1000);
    assertFile(temp, "Собранный MP4");
    const result = await probe(temp, ffprobe);
    if (result.width !== w || result.height !== h ||
        Math.abs((result.duration - input.duration) - FOOTER_SECONDS) > 1.25) {
      throw new Error(`Некорректный финальный MP4: исходник ${input.duration.toFixed(2)} сек., результат ${result.duration.toFixed(2)} сек.`);
    }
    if (fs.existsSync(dst)) throw new Error(`Итоговый MP4 появился во время обработки: ${dst}`);
    // Same-directory rename publishes only a validated complete file.
    const footerSha256 = await sha256(img);
    fs.renameSync(temp, dst);
    return { originalDuration: input.duration, finalDuration: result.duration,
      width: w, height: h, footerSha256, durationSeconds: FOOTER_SECONDS };
  } finally {
    try { fs.rmSync(temp, { force: true }); } catch {}
  }
}

module.exports = { appendFooter, FOOTER_FILENAME, FOOTER_SECONDS, findTool, probe };
