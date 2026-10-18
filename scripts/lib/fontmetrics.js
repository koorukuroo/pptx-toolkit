'use strict';
// 설치 폰트(TTF/OTF/TTC)의 실제 글자 폭·행간 — core/fontmetrics.py 와 같은 알고리즘·같은 캐시(~/.cache/pptx-toolkit/font-index.json).
// 빌드 시 넘침 추정이 '한글 1.0em' 평균 계수 대신 hmtx 폭을 쓰게 한다. 폰트 파일은 읽기만 한다.
const fs = require('fs');
const os = require('os');
const path = require('path');

const CACHE_DIR = process.env.PPTX_TOOLKIT_CACHE || path.join(os.homedir(), '.cache', 'pptx-toolkit');
const INDEX_PATH = path.join(CACHE_DIR, 'font-index.json');
const INDEX_VERSION = 1;

function heuristicEm(ch) {
  const o = ch.codePointAt(0);
  if (ch === ' ') return 0.3;
  if ((o >= 0xac00 && o <= 0xd7a3) || (o >= 0x3130 && o <= 0x318f) || (o >= 0x4e00 && o <= 0x9fff) || (o >= 0x3000 && o <= 0x303f) || (o >= 0xff00 && o <= 0xffef)) return 1.0;
  if (/\d/.test(ch)) return 0.58;
  if (/[A-Z]/.test(ch)) return 0.68;
  if ('.,:;\'|!il'.includes(ch)) return 0.3;
  return 0.55;
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

// ---------------------------------------------------------------- 파서
class Font {
  constructor(file, ttcIndex = 0) {
    this.path = file;
    this.ttcIndex = ttcIndex;
    const d = fs.readFileSync(file);
    this.d = d;
    let offset = 0;
    if (d.toString('latin1', 0, 4) === 'ttcf') {
      const n = d.readUInt32BE(8);
      if (ttcIndex >= n) throw new Error('ttc index out of range');
      offset = d.readUInt32BE(12 + 4 * ttcIndex);
    }
    const numTables = d.readUInt16BE(offset + 4);
    this.tables = {};
    for (let i = 0; i < numTables; i++) {
      const rec = offset + 12 + 16 * i;
      this.tables[d.toString('latin1', rec, rec + 4)] = [d.readUInt32BE(rec + 8), d.readUInt32BE(rec + 12)];
    }
    if (!this.tables.head || !this.tables.hmtx || !this.tables.cmap) throw new Error('필수 테이블 없음');
    this.unitsPerEm = d.readUInt16BE(this.tables.head[0] + 18) || 1000;
    this._cmap = null; this._widths = null; this._lh = null; this._names = null;
  }

  names() {
    if (this._names) return this._names;
    const out = {};
    if (this.tables.name) {
      const d = this.d;
      const no = this.tables.name[0];
      const count = d.readUInt16BE(no + 2);
      const strOff = no + d.readUInt16BE(no + 4);
      const best = {};
      for (let i = 0; i < count; i++) {
        const rec = no + 6 + 12 * i;
        const pid = d.readUInt16BE(rec), lid = d.readUInt16BE(rec + 4), nid = d.readUInt16BE(rec + 6), ln = d.readUInt16BE(rec + 8), so = d.readUInt16BE(rec + 10);
        const raw = d.subarray(strOff + so, strOff + so + ln);
        let s = '';
        if (pid === 3 || pid === 0) { for (let k = 0; k + 1 < raw.length; k += 2) s += String.fromCharCode(raw.readUInt16BE(k)); }
        else s = raw.toString('latin1');
        s = s.replace(/\0/g, '').trim();
        if (!s) continue;
        const score = pid === 3 && lid === 0x409 ? 4 : pid === 3 ? 3 : pid === 1 && lid === 0 ? 2 : 1;
        if (!best[nid] || score > best[nid][0]) best[nid] = [score, s];
      }
      for (const [k, v] of Object.entries(best)) out[k] = v[1];
    }
    this._names = out;
    return out;
  }

  get family() { const n = this.names(); return n[16] || n[1] || path.basename(this.path, path.extname(this.path)); }
  get subfamily() { const n = this.names(); return n[17] || n[2] || 'Regular'; }
  weight() { if (this.tables['OS/2']) { try { return this.d.readUInt16BE(this.tables['OS/2'][0] + 4); } catch (e) { /* ignore */ } } return 400; }
  italic() {
    if (this.tables['OS/2']) { try { return !!(this.d.readUInt16BE(this.tables['OS/2'][0] + 62) & 1); } catch (e) { /* ignore */ } }
    return !!(this.d.readUInt16BE(this.tables.head[0] + 44) & 2);
  }

  widths() {
    if (this._widths) return this._widths;
    const d = this.d;
    const n = d.readUInt16BE(this.tables.hhea[0] + 34);
    const hm = this.tables.hmtx[0];
    const w = new Array(n);
    for (let i = 0; i < n; i++) w[i] = d.readUInt16BE(hm + 4 * i);
    this._widths = w;
    return w;
  }

  cmap() {
    if (this._cmap) return this._cmap;
    const d = this.d;
    const co = this.tables.cmap[0];
    const n = d.readUInt16BE(co + 2);
    let best = null;
    for (let i = 0; i < n; i++) {
      const rec = co + 4 + 8 * i;
      const pid = d.readUInt16BE(rec), eid = d.readUInt16BE(rec + 2), off = d.readUInt32BE(rec + 4);
      const fmt = d.readUInt16BE(co + off);
      let score = 0;
      if (pid === 3 && eid === 10 && fmt === 12) score = 5;
      else if (pid === 0 && fmt === 12) score = 4;
      else if (pid === 3 && eid === 1 && fmt === 4) score = 3;
      else if (pid === 0 && fmt === 4) score = 2;
      if (score && (!best || score > best[0])) best = [score, co + off];
    }
    const cmap = new Map();
    if (best) {
      const o = best[1];
      const fmt = d.readUInt16BE(o);
      if (fmt === 4) {
        const segx2 = d.readUInt16BE(o + 6), seg = segx2 / 2;
        const ends = o + 14, starts = ends + segx2 + 2, deltas = starts + segx2, ranges = deltas + segx2;
        for (let s = 0; s < seg; s++) {
          const end = d.readUInt16BE(ends + 2 * s), start = d.readUInt16BE(starts + 2 * s), delta = d.readUInt16BE(deltas + 2 * s), ro = d.readUInt16BE(ranges + 2 * s);
          if (start > end || start === 0xffff) continue;
          for (let cp = start; cp <= end; cp++) {
            let g;
            if (ro === 0) g = (cp + delta) & 0xffff;
            else {
              const gi = ranges + 2 * s + ro + 2 * (cp - start);
              if (gi + 2 > d.length) continue;
              g = d.readUInt16BE(gi);
              if (g) g = (g + delta) & 0xffff;
            }
            if (g) cmap.set(cp, g);
          }
        }
      } else if (fmt === 12) {
        const ngroups = d.readUInt32BE(o + 12);
        for (let gi = 0; gi < ngroups; gi++) {
          const rec = o + 16 + 12 * gi;
          const sc = d.readUInt32BE(rec), ec = d.readUInt32BE(rec + 4), sg = d.readUInt32BE(rec + 8);
          if (ec - sc > 70000) continue;
          for (let cp = sc; cp <= ec; cp++) cmap.set(cp, sg + (cp - sc));
        }
      }
    }
    this._cmap = cmap;
    return cmap;
  }

  glyphWidthEm(ch) {
    const g = this.cmap().get(ch.codePointAt(0));
    if (g == null) return null;
    const w = this.widths();
    if (!w.length) return null;
    return (g < w.length ? w[g] : w[w.length - 1]) / this.unitsPerEm;
  }

  lineHeightEm() {
    if (this._lh != null) return this._lh;
    const d = this.d;
    const hh = this.tables.hhea[0];
    const asc = d.readInt16BE(hh + 4), desc = d.readInt16BE(hh + 6), gap = d.readInt16BE(hh + 8);
    let lh = (asc - desc + gap) / this.unitsPerEm;
    if (this.tables['OS/2']) {
      try { const o = this.tables['OS/2'][0]; lh = Math.max(lh, (d.readUInt16BE(o + 74) + d.readUInt16BE(o + 76)) / this.unitsPerEm); } catch (e) { /* ignore */ }
    }
    this._lh = lh >= 0.8 && lh <= 2.5 ? lh : 1.2;
    return this._lh;
  }
}

// ---------------------------------------------------------------- 색인
function scanFile(file) {
  const out = [];
  try {
    const fd = fs.openSync(file, 'r');
    const head = Buffer.alloc(16);
    fs.readSync(fd, head, 0, 16, 0);
    fs.closeSync(fd);
    let count = 1;
    if (head.toString('latin1', 0, 4) === 'ttcf') count = Math.min(head.readUInt32BE(8), 32);
    for (let i = 0; i < count; i++) {
      try {
        const ft = new Font(file, i);
        out.push({ path: file, index: i, family: ft.family, subfamily: ft.subfamily, weight: ft.weight(), italic: ft.italic() });
      } catch (e) { /* skip */ }
    }
  } catch (e) { /* skip */ }
  return out;
}

let _index = null;
function index(refresh = false) {
  if (_index && !refresh) return _index;
  let cache = {};
  if (!refresh && fs.existsSync(INDEX_PATH)) {
    try { cache = JSON.parse(fs.readFileSync(INDEX_PATH, 'utf8')); if (cache.version !== INDEX_VERSION) cache = {}; } catch (e) { cache = {}; }
  }
  const files = Object.assign({}, cache.files || {});
  const seen = new Set();
  let changed = false;
  const walk = (dir, depth) => {
    if (depth > 4) return;
    let ents = [];
    try { ents = fs.readdirSync(dir, { withFileTypes: true }); } catch (e) { return; }
    for (const e of ents) {
      const f = path.join(dir, e.name);
      if (e.isDirectory()) { walk(f, depth + 1); continue; }
      if (!/\.(ttf|otf|ttc)$/i.test(e.name)) continue;
      seen.add(f);
      let mt;
      try { mt = fs.statSync(f).mtimeMs / 1000; } catch (err) { continue; }
      const ent = files[f];
      if (ent && Math.abs(Number(ent.mtime) - mt) < 1e-6) continue;
      files[f] = { mtime: mt, fonts: scanFile(f) };
      changed = true;
    }
  };
  for (const d of fontDirs()) walk(d, 0);
  for (const k of Object.keys(files)) if (!seen.has(k)) { delete files[k]; changed = true; }
  if (changed || !cache.files) {
    try { fs.mkdirSync(CACHE_DIR, { recursive: true }); fs.writeFileSync(INDEX_PATH, JSON.stringify({ version: INDEX_VERSION, built: Date.now() / 1000, files })); } catch (e) { /* ignore */ }
  }
  _index = [];
  for (const ent of Object.values(files)) _index.push(...(ent.fonts || []));
  return _index;
}

const norm = (s) => String(s || '').replace(/[\s_-]+/g, '').toLowerCase();
const _find = new Map();
function find(family, bold = false) {
  const key = `${family}|${bold ? 1 : 0}`;
  if (_find.has(key)) return _find.get(key);
  const want = norm(family);
  const cands = index().filter((e) => { const fam = norm(e.family); return !e.italic && (fam === want || fam.startsWith(want) || (want.startsWith(fam) && fam.length >= 4)); });
  let res = null;
  if (cands.length) {
    const target = bold ? 700 : 400;
    cands.sort((a, b) => (Math.abs((a.weight || 400) - target) - Math.abs((b.weight || 400) - target)) || ((norm(a.family) === want ? 0 : 1) - (norm(b.family) === want ? 0 : 1)) || String(a.path).localeCompare(String(b.path)));
    res = [cands[0].path, cands[0].index || 0];
  }
  _find.set(key, res);
  return res;
}

const _fonts = new Map();
function load(family, bold = false) {
  const loc = find(family, bold);
  if (!loc) return null;
  const k = loc.join('#');
  if (!_fonts.has(k)) { try { _fonts.set(k, new Font(loc[0], loc[1])); } catch (e) { _fonts.set(k, null); } }
  return _fonts.get(k);
}

function widthEm(ch, family, bold = false) {
  if (family) { const ft = load(family, bold); if (ft) { const w = ft.glyphWidthEm(ch); if (w != null) return w; } }
  return heuristicEm(ch);
}

function lineHeightEm(family, bold = false) {
  if (family) { const ft = load(family, bold); if (ft) return ft.lineHeightEm(); }
  return 1.2;
}

function hasFamily(family) { return !!find(family, false) || !!find(family, true); }

module.exports = { Font, index, find, load, widthEm, lineHeightEm, heuristicEm, hasFamily, fontDirs };
