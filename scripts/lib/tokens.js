'use strict';
// 스타일 프로파일 로드·병합, 전달 모드별 타입 스케일, 폰트 가용성 확인
const fs = require('fs');
const os = require('os');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const PROFILES = JSON.parse(fs.readFileSync(path.join(ROOT, 'references', 'style-profiles.json'), 'utf8')).profiles;
const ARCHETYPES = JSON.parse(fs.readFileSync(path.join(ROOT, 'references', 'slide-archetypes.json'), 'utf8')).archetypes;

function deepMerge(base, over) {
  const out = JSON.parse(JSON.stringify(base));
  for (const [k, v] of Object.entries(over || {})) {
    if (v && typeof v === 'object' && !Array.isArray(v) && out[k] && typeof out[k] === 'object' && !Array.isArray(out[k])) out[k] = deepMerge(out[k], v);
    else out[k] = JSON.parse(JSON.stringify(v));
  }
  return out;
}

function fontDirs() {
  const home = os.homedir();
  const p = process.platform;
  const dirs = p === 'darwin'
    ? [path.join(home, 'Library/Fonts'), '/Library/Fonts', '/System/Library/Fonts', '/System/Library/Fonts/Supplemental']
    : p === 'win32'
      ? [path.join(process.env.WINDIR || 'C:/Windows', 'Fonts'), path.join(home, 'AppData/Local/Microsoft/Windows/Fonts')]
      : [path.join(home, '.fonts'), path.join(home, '.local/share/fonts'), '/usr/share/fonts', '/usr/local/share/fonts'];
  return dirs.filter((d) => fs.existsSync(d));
}

let _fontFiles = null;
function fontFiles() {
  if (_fontFiles) return _fontFiles;
  const out = [];
  const walk = (d, depth) => {
    if (depth > 3) return;
    let ents = [];
    try { ents = fs.readdirSync(d, { withFileTypes: true }); } catch { return; }
    for (const e of ents) {
      const f = path.join(d, e.name);
      if (e.isDirectory()) walk(f, depth + 1);
      else if (/\.(ttf|otf|ttc)$/i.test(e.name)) out.push(e.name.toLowerCase());
    }
  };
  for (const d of fontDirs()) walk(d, 0);
  _fontFiles = out;
  return out;
}

const ALIASES = {
  paperlogy: ['paperlogy'],
  pretendard: ['pretendard'],
  'noto sans kr': ['notosanskr', 'notosanscjkkr', 'notosanscjk'],
  'noto sans cjk kr': ['notosanscjkkr', 'notosanscjk'],
  'apple sd gothic neo': ['applesdgothicneo'],
  'malgun gothic': ['malgun'],
  arial: ['arial'],
};

function hasFont(family) {
  const key = family.toLowerCase().replace(/[\s_-]+/g, ' ').trim();
  const needles = ALIASES[key] || [key.replace(/\s+/g, '')];
  const files = fontFiles();
  return needles.some((n) => files.some((f) => f.replace(/[\s_-]+/g, '').startsWith(n)));
}

function resolveFont(preferred, fallback) {
  const chain = [preferred, ...(fallback || [])];
  for (const f of chain) if (f && hasFont(f)) return { use: f, requested: preferred, substituted: f !== preferred };
  return { use: preferred, requested: preferred, substituted: false, missing: true };
}

function weightToBold(w) {
  return ['bold', 'semibold', 'extrabold', 'black', 'heavy'].includes(String(w || '').toLowerCase());
}

function resolveTokens(spec) {
  const name = spec.route && spec.route.style_profile;
  const prof = PROFILES[name];
  if (!prof) throw new Error(`알 수 없는 style_profile: ${name} (가능: ${Object.keys(PROFILES).join(', ')})`);
  const t = deepMerge(prof.tokens, spec.design_tokens || {});
  const mode = spec.metadata.delivery_mode || 'hybrid';
  t.mode = mode;
  t.scale = t.type[mode] || t.type.hybrid;
  t.profile = name;
  const disp = resolveFont(t.fonts.display, t.fonts.fallback);
  const body = resolveFont(t.fonts.body, t.fonts.fallback);
  t.fonts.resolved = {
    display: disp.use,
    body: body.use,
    numeral: resolveFont(t.fonts.numeral || t.fonts.display, t.fonts.fallback).use,
    warnings: [disp, body].filter((r) => r.substituted || r.missing).map((r) => (r.missing ? `폰트 '${r.requested}'와 대체 폰트 모두 미설치 — 수신 PC 폰트로 렌더됨` : `폰트 '${r.requested}' 미설치 → '${r.use}' 사용`)),
  };
  t.fonts.titleBold = weightToBold(t.fonts.weights && t.fonts.weights.title);
  return t;
}

module.exports = { PROFILES, ARCHETYPES, ROOT, deepMerge, resolveTokens, hasFont, resolveFont };
