#!/usr/bin/env node
'use strict';
/* deck-spec.json → .pptx
 *   node scripts/build.js deck-spec.json -o out.pptx [--hooks hooks.js] [--only 1-3,7]
 * 마지막 stdout 줄에 JSON 요약을 쓴다: {ok, output, slides, warnings[], infos[], fonts}
 * hooks.js: module.exports = { 5: (slide, ctx, slideSpec, body) => {...}, afterSlide(slide, ctx, slideSpec, body), afterDeck(pres, ctx) }
 */
const fs = require('fs');
const path = require('path');
const pptxgen = require('pptxgenjs');
const { resolveTokens, ARCHETYPES } = require('./lib/tokens');
const frame = require('./lib/frame');
const archetypes = require('./lib/archetypes');
const { applyTheme } = require('./lib/theme');

function parseArgs(argv) {
  const a = { spec: null, out: null, hooks: null, only: null };
  for (let i = 0; i < argv.length; i++) {
    const v = argv[i];
    if (v === '-o' || v === '--out') a.out = argv[++i];
    else if (v === '--hooks') a.hooks = argv[++i];
    else if (v === '--only') a.only = argv[++i];
    else if (!a.spec) a.spec = v;
  }
  if (!a.spec || !a.out) { console.error('usage: build.js deck-spec.json -o out.pptx [--hooks hooks.js] [--only 1-3,7]'); process.exit(2); }
  return a;
}

function parseOnly(s) {
  if (!s) return null;
  const set = new Set();
  for (const part of s.split(',')) {
    const m = part.trim().match(/^(\d+)(?:-(\d+))?$/);
    if (!m) continue;
    const lo = Number(m[1]), hi = m[2] ? Number(m[2]) : lo;
    for (let i = lo; i <= hi; i++) set.add(i);
  }
  return set;
}

async function build(specPath, outPath, { hooksPath, only } = {}) {
  const spec = JSON.parse(fs.readFileSync(specPath, 'utf8'));
  const specDir = path.dirname(path.resolve(specPath));
  const tok = resolveTokens(spec);
  const pres = new pptxgen();
  pres.layout = tok.canvas.layout || 'LAYOUT_WIDE';
  pres.lang = 'ko-KR';
  pres.title = spec.metadata.title || '';
  pres.subject = spec.metadata.subtitle || '';
  pres.author = spec.metadata.presenter || spec.metadata.organization || '';
  pres.company = (spec.metadata.organization || '').replace(/&/g, '&amp;');
  pres.theme = { headFontFace: tok.fonts.resolved.display, bodyFontFace: tok.fonts.resolved.body };

  const warnings = [], infos = [];
  const assets = Object.assign({}, (spec.assets && spec.assets.images) || {});
  if (spec.assets && spec.assets.logo) assets.logo = spec.assets.logo;
  const ctx = {
    pres, spec, tok, scale: tok.scale, masters: {}, hooks: null,
    font: { display: tok.fonts.resolved.display, body: tok.fonts.resolved.body, numeral: tok.fonts.resolved.numeral, mono: tok.fonts.resolved.mono || null },
    slideIndex: 0, slideTotal: 0,
    sections: [], currentSection: null,
    warn: (msg, extra) => warnings.push(Object.assign({ slide: ctx.slideSpec ? ctx.slideSpec.number : null, message: msg }, extra || {})),
    info: (msg) => infos.push({ slide: ctx.slideSpec ? ctx.slideSpec.number : null, message: msg }),
    asset: (id) => {
      if (!id) return null;
      const p = assets[id] || id;
      const abs = path.isAbsolute(p) ? p : path.resolve(specDir, p);
      return fs.existsSync(abs) ? abs : null;
    },
  };
  for (const w of tok.fonts.resolved.warnings || []) warnings.push({ slide: null, message: w });
  if (hooksPath) ctx.hooks = require(path.resolve(hooksPath));

  // 섹션 목록·인덱스 (슬라이드 등장 순서)
  const slides = spec.slides.slice().sort((a, b) => a.number - b.number);
  for (const s of slides) if (s.section && !ctx.sections.includes(s.section)) ctx.sections.push(s.section);
  for (const s of slides) s._sectionIndex = s.section ? ctx.sections.indexOf(s.section) + 1 : 0;

  frame.defineMasters(ctx);

  const onlySet = parseOnly(only);
  ctx.slideTotal = onlySet ? slides.filter((s) => onlySet.has(s.number)).length : slides.length;
  let built = 0;
  let lastSection = null;
  for (const s of slides) {
    if (onlySet && !onlySet.has(s.number)) continue;
    if (s.section && s.section !== lastSection) { pres.addSection({ title: s.section }); lastSection = s.section; ctx.currentSection = s.section; }
    else if (!s.section && lastSection !== null && !ctx.currentSection) { /* 섹션 없는 슬라이드는 기본 섹션 */ }
    const render = archetypes[s.archetype];
    if (!render) { warnings.push({ slide: s.number, message: `알 수 없는 아키타입 '${s.archetype}' — 건너뜀 (가능: ${Object.keys(ARCHETYPES).join(', ')})` }); continue; }
    ctx.slideIndex = built + 1;
    const { slide, body } = frame.begin(ctx, s);
    try {
      render(ctx, slide, s, body);
    } catch (e) {
      warnings.push({ slide: s.number, message: `렌더 예외 (${s.archetype}): ${e.message}` });
    }
    if (ctx.hooks) {
      const h = ctx.hooks[s.number] || ctx.hooks[String(s.number)];
      if (typeof h === 'function') { try { h(slide, ctx, s, body); } catch (e) { warnings.push({ slide: s.number, message: `hook 예외: ${e.message}` }); } }
      if (typeof ctx.hooks.afterSlide === 'function') ctx.hooks.afterSlide(slide, ctx, s, body);
    }
    frame.end(ctx, s);
    built += 1;
  }
  if (ctx.hooks && typeof ctx.hooks.afterDeck === 'function') ctx.hooks.afterDeck(pres, ctx);
  if (!built) throw new Error('생성된 슬라이드가 없다');

  await pres.writeFile({ fileName: outPath });
  const c = tok.colors;
  await applyTheme(outPath, {
    headFont: tok.fonts.resolved.display, bodyFont: tok.fonts.resolved.body, name: `pptx-toolkit ${tok.profile}`,
    colors: { dk1: c.ink, lt1: c.background === c.dark_background ? (c.light_background || 'FFFFFF') : c.background, dk2: c.primary, lt2: c.surface, accent1: c.primary, accent2: c.secondary, accent3: c.accent, accent4: c.positive, accent5: c.warning, accent6: c.negative, hlink: c.secondary, folHlink: c.ink_muted },
  });
  return { ok: true, output: outPath, slides: built, profile: tok.profile, mode: tok.mode, fonts: { display: tok.fonts.resolved.display, body: tok.fonts.resolved.body }, warnings, infos };
}

if (require.main === module) {
  const a = parseArgs(process.argv.slice(2));
  build(a.spec, a.out, { hooksPath: a.hooks, only: a.only })
    .then((r) => { console.log(JSON.stringify(r)); process.exit(0); })
    .catch((e) => { console.log(JSON.stringify({ ok: false, error: e.message, stack: (e.stack || '').split('\n').slice(0, 4) })); process.exit(1); });
}

module.exports = { build };
