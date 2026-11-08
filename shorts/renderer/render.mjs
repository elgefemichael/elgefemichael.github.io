// Frame-exact renderer: loads index.html in headless Chromium, seeks every frame,
// pipes JPEG screenshots into ffmpeg.  Usage:
//   node render.mjs <timeline.json> <out_video.mp4> [--fps 30] [--from 0] [--to <sec>] [--still t1,t2 --still-dir dir]
import { chromium } from "playwright";
import { spawn } from "node:child_process";
import { readFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const [timelinePath, outPath] = args;
if (!timelinePath || !outPath) { console.error("usage: node render.mjs timeline.json out.mp4"); process.exit(2); }

const ep = JSON.parse(readFileSync(timelinePath, "utf8"));
const fps = Number(opt("--fps", ep.fps || 30));
const from = Number(opt("--from", 0));
const to = Number(opt("--to", ep.duration));
const stills = opt("--still", null);

const launchOpts = process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {};
const browser = await chromium.launch(launchOpts);
const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
page.on("pageerror", e => console.error("[page]", e.message));
await page.goto(pathToFileURL(resolve(here, "index.html")).href, { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);
// clip paths in the timeline are relative to the timeline file
for (const sc of ep.scenes) if (sc.clip) sc.clip.src = pathToFileURL(resolve(dirname(timelinePath), sc.clip.src)).href;
await page.evaluate(ep => window.__load(ep), ep);
await page.evaluate(() => window.__ready());

if (stills) {
  const dir = opt("--still-dir", dirname(outPath));
  mkdirSync(dir, { recursive: true });
  for (const s of stills.split(",").map(Number)) {
    await page.evaluate(t => window.__seek(t), s);
    await page.screenshot({ path: `${dir}/still_${s.toFixed(2)}.png` });
  }
  await browser.close();
  process.exit(0);
}

const ff = spawn("ffmpeg", ["-y", "-v", "error", "-f", "image2pipe", "-framerate", String(fps), "-c:v", "mjpeg", "-i", "-",
  "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", outPath],
  { stdio: ["pipe", "inherit", "inherit"] });

const total = Math.round((to - from) * fps);
const t0 = Date.now();
for (let f = 0; f < total; f++) {
  const t = from + f / fps;
  await page.evaluate(t => window.__seek(t), t);
  const buf = await page.screenshot({ type: "jpeg", quality: 92 });
  if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once("drain", r));
  if (f % (fps * 5) === 0) console.log(`frame ${f}/${total}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
}
ff.stdin.end();
await new Promise((res, rej) => ff.on("close", c => (c === 0 ? res() : rej(new Error("ffmpeg exit " + c)))));
await browser.close();
console.log(`rendered ${total} frames in ${((Date.now() - t0) / 1000).toFixed(0)}s -> ${outPath}`);
