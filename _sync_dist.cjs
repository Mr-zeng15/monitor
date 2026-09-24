/* eslint-disable */
// 同步 frontend/dist → backend/static/frontend
// ★ 2026-09-23 重建（原 _sync_dist.js 已不在仓库里）。
//   ★ 不用 fs.cpSync：在部分 Node/Windows 组合上会静默漏拷 assets，改为显式 rm + 自写递归拷贝。
//   ★ 校验必须同时读 .js 与 .css chunk —— 作用域 CSS 的 :deep() 落在【独立 .css chunk】，
//     只查 .js 会误报 FAIL（上一轮踩过）。
const fs = require('fs');
const path = require('path');

const ROOT = __dirname;
const SRC = path.join(ROOT, 'frontend', 'dist');
const DST = path.join(ROOT, 'backend', 'static', 'frontend');

function die(msg) { console.error('SYNC FAIL: ' + msg); process.exit(1); }

if (!fs.existsSync(SRC)) die('源目录不存在: ' + SRC);
if (!fs.existsSync(path.join(SRC, 'index.html'))) die('源目录没有 index.html');

// 1) 清目标 + 全量拷贝
fs.rmSync(DST, { recursive: true, force: true });
fs.mkdirSync(DST, { recursive: true });

let copied = 0;
function walk(from, to) {
  fs.mkdirSync(to, { recursive: true });
  for (const e of fs.readdirSync(from, { withFileTypes: true })) {
    const s = path.join(from, e.name), d = path.join(to, e.name);
    if (e.isDirectory()) walk(s, d);
    else { fs.copyFileSync(s, d); copied++; }
  }
}
walk(SRC, DST);

function listExt(dir, ext, acc) {
  acc = acc || [];
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) listExt(p, ext, acc);
    else if (e.name.endsWith(ext)) acc.push(p);
  }
  return acc;
}

// 2) assets 必须齐全
const srcAssets = listExt(path.join(SRC, 'assets'), '').length;
const dstAssets = listExt(path.join(DST, 'assets'), '').length;
if (srcAssets === 0) die('源 dist/assets 为空');
if (srcAssets !== dstAssets) die(`assets 数量不一致 src=${srcAssets} dst=${dstAssets}`);

// 3) 产物不得残留 localhost:8000
const jsFiles = listExt(DST, '.js');
const cssFiles = listExt(DST, '.css');
const allFiles = jsFiles.concat(cssFiles);
if (!allFiles.length) die('目标里没有 .js/.css chunk');
const bad = allFiles.filter(f => fs.readFileSync(f, 'utf8').includes('localhost:8000'));
if (bad.length) die('产物残留 localhost:8000 → ' + bad.join(', '));

// 4) 必须含相对路径 /api
const hasApi = allFiles.some(f => fs.readFileSync(f, 'utf8').includes('"/api"') || fs.readFileSync(f, 'utf8').includes("'/api'"));
if (!hasApi) die('产物里找不到 "/api"（前端 API 相对路径丢失）');

const idx = path.join(DST, 'index.html');
if (!fs.existsSync(idx)) die('目标缺少 index.html');

console.log('SYNC GREEN');
console.log('  copied files = ' + copied);
console.log('  assets       = ' + dstAssets);
console.log('  js chunks    = ' + jsFiles.length);
console.log('  css chunks   = ' + cssFiles.length);
console.log('  index.html   = ok');
