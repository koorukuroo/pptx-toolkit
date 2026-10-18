'use strict';
// 슬라이드 프레임: 마스터(배경·푸터·쪽번호), 킥커/트래커, 액션 타이틀, 스티커, 본문 영역 계산, 출처·노트.
const { fitText, spacingMultiple } = require('./text');
const P = require('./primitives');

const ROMAN = ['Ⅰ', 'Ⅱ', 'Ⅲ', 'Ⅳ', 'Ⅴ', 'Ⅵ', 'Ⅶ', 'Ⅷ', 'Ⅸ', 'Ⅹ', 'Ⅺ', 'Ⅻ'];

function numeralText(ctx, n, style) {
  const s = style || (ctx.tok.title.chip_numerals === 'roman' ? 'roman' : (ctx.tok.list.numbering[0] === '01' ? 'pad' : 'plain'));
  if (s === 'roman') return ROMAN[(n - 1) % ROMAN.length];
  if (s === 'pad') return String(n).padStart(2, '0');
  return String(n);
}

function palette(tok, bg) {
  const c = tok.colors;
  if (bg === 'dark') {
    return Object.assign({}, c, {
      background: c.dark_background, ink: c.on_dark, ink_muted: 'C7D0D8', ink_faint: '94A3B3', line: '3A4A5A', line_faint: '2A3845',
      surface: shade(c.dark_background, 12), surface_strong: shade(c.dark_background, 22), primary: c.light_background ? c.primary : 'FFFFFF',
      primary_soft: shade(c.dark_background, 18), on_primary: c.dark_background, accent: c.accent, accent_soft: shade(c.dark_background, 18), dark: true,
    });
  }
  if (bg === 'surface') return Object.assign({}, c, { background: c.surface, surface: c.surface_strong, primary_soft: c.primary_soft });
  if (c.light_background && c.light_ink && bg === 'light' && c.background === c.dark_background) {
    // 키노트 프로파일은 기본이 어두움. 'light' 요청 시 밝은 팔레트
    return Object.assign({}, c, { background: c.light_background, ink: c.light_ink, ink_muted: '5B6977', ink_faint: '8A97A4', line: 'D5DBE1', line_faint: 'E9EDF1', surface: 'F3F5F7', surface_strong: 'E6EAEE', primary: '0F4C81', primary_soft: 'DCE8F3', on_primary: 'FFFFFF' });
  }
  return Object.assign({}, c);
}

function shade(hex, amount) {
  const n = parseInt(hex, 16);
  const r = Math.min(255, ((n >> 16) & 255) + amount), g = Math.min(255, ((n >> 8) & 255) + amount), b = Math.min(255, (n & 255) + amount);
  return [r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('').toUpperCase();
}

function defaultBackground(ctx, slideSpec) {
  if (slideSpec.background) return slideSpec.background;
  const bgs = ctx.tok.backgrounds || {};
  const a = slideSpec.archetype;
  if (bgs.all) return bgs.all;
  if (a === 'cover') return bgs.cover || (ctx.tok.cover.variant.startsWith('dark') || ctx.tok.cover.variant === 'image-or-dark' ? 'dark' : 'light');
  if (bgs[a]) return bgs[a];
  if (a === 'section_divider') return 'surface';
  if (a === 'statement') return 'dark';
  return bgs.default || 'light';
}

// 마스터 정의 — 배경별 1개. 푸터·쪽번호는 마스터에, 제목은 placeholder.
function defineMasters(ctx) {
  const tok = ctx.tok;
  const W = tok.canvas.width, H = tok.canvas.height;
  const M = tok.canvas.margin;
  const F = tok.footer;
  const meta = ctx.spec.metadata;
  const chipShift = tok.title.style === 'chip' ? 0.68 : 0;
  for (const bg of ['light', 'dark', 'surface']) {
    const pal = palette(tok, bg);
    const objects = [];
    const footY = H - 0.42, footH = 0.28;
    const leftText = F.left === 'organization' ? (meta.organization || '') : F.left === 'document_title' ? (meta.title || '') : '';
    const footOpts = { fontSize: Math.max(8, ctx.scale.source - 1), color: pal.ink_faint, fontFace: ctx.font.body, margin: 0, valign: 'middle', lang: 'ko-KR' };
    if (leftText && !['cover'].includes(bg)) objects.push({ text: { text: leftText, options: Object.assign({ x: M.left, y: footY, w: W * 0.45, h: footH, align: 'left' }, footOpts) } });
    if (F.confidentiality && meta.confidentiality) objects.push({ text: { text: meta.confidentiality, options: Object.assign({ x: W * 0.35, y: footY, w: W * 0.3, h: footH, align: 'center' }, footOpts) } });
    const titleY = M.top + (tok.title.kicker !== 'none' ? 0.3 : 0);
    const titleH = (2 * ctx.scale.title * tok.typography.line_height.title) / 72 + 0.08;
    objects.push({ placeholder: { options: { name: 'title', type: 'title', x: M.left + chipShift, y: titleY, w: W - M.left - M.right - chipShift - (meta.sticker ? 1.4 : 0), h: titleH, bold: tok.fonts.titleBold, color: pal.ink, fontFace: ctx.font.display, margin: 0, valign: 'top', align: tok.title.align || 'left', lang: 'ko-KR' }, text: '' } });
    const def = { title: `TK_${bg.toUpperCase()}`, background: { color: pal.background }, objects };
    if (F.right === 'page_number') def.slideNumber = { x: W - M.right - 0.6, y: footY, w: 0.6, h: footH, fontSize: Math.max(8, ctx.scale.source - 1), color: pal.ink_faint, fontFace: ctx.font.body, align: 'right', margin: 0, valign: 'middle' };
    ctx.pres.defineSlideMaster(def);
    ctx.masters[bg] = { name: def.title, titleY, titleH, chipShift };
  }
}

// 슬라이드 시작: 배경·킥커·제목·스티커를 그리고 본문 영역을 돌려준다
function begin(ctx, slideSpec, opts = {}) {
  const tok = ctx.tok;
  const W = tok.canvas.width, H = tok.canvas.height, M = tok.canvas.margin;
  const bg = defaultBackground(ctx, slideSpec);
  ctx.pal = palette(tok, bg);
  const master = ctx.masters[bg];
  const slide = ctx.pres.addSlide({ masterName: master.name, sectionTitle: ctx.currentSection || undefined });
  const isChrome = !['cover', 'section_divider', 'statement'].includes(slideSpec.archetype) && !opts.noChrome;
  const hasSource = !!(slideSpec.source_note && slideSpec.source_note.trim());
  const sourceH = 0.3;
  const sourceY = H - 0.42 - sourceH - 0.02;
  const frame = { left: M.left, right: W - M.right, width: W - M.left - M.right, top: M.top, H, W, sourceY, sourceH, footerY: H - 0.42 };
  ctx.frame = frame;
  ctx.slide = slide;
  ctx.slideSpec = slideSpec;
  const body = { x: M.left, y: M.top, w: frame.width, h: (hasSource ? sourceY - 0.12 : frame.footerY - 0.2) - M.top };
  if (!isChrome) return { slide, body, bg };

  // 킥커 / 트래커 / exhibit
  const kickerY = M.top - 0.02;
  const kickerParts = [];
  if (tok.title.kicker === 'section' && slideSpec.section) kickerParts.push(slideSpec.section);
  if (tok.title.kicker === 'tracker' && slideSpec.section) kickerParts.push(slideSpec.section);
  if (slideSpec.kicker) kickerParts.push(slideSpec.kicker);
  if (tok.footer.exhibit_numbers && slideSpec.exhibit != null) kickerParts.unshift(typeof slideSpec.exhibit === 'number' ? `Exhibit ${slideSpec.exhibit}` : String(slideSpec.exhibit));
  if (tok.title.kicker !== 'none' && kickerParts.length) {
    P.label(ctx, slide, kickerParts.join('  ·  '), { x: M.left, y: kickerY, w: frame.width - 1.6, h: 0.24 }, { color: ctx.pal.ink_muted });
    if (tok.title.kicker === 'tracker' && ctx.sections.length > 1) drawTracker(ctx, slide, slideSpec, { x: W - M.right - 1.5, y: kickerY + 0.06, w: 1.5, h: 0.12 });
  }
  // 스티커 (DRAFT / 초안 / 예시)
  const sticker = slideSpec.sticker || ctx.spec.metadata.sticker;
  if (sticker) {
    const sw = Math.max(0.9, Math.min(1.6, sticker.length * 0.12 + 0.3));
    const sx = W - M.right - sw, sy = master.titleY + 0.02;
    P.rect(ctx, slide, { x: sx, y: sy, w: sw, h: 0.26 }, { line: ctx.pal.accent, lineWidth: 0.75, radius: 0 });
    P.ctxText(ctx, slide, sticker, { x: sx, y: sy, w: sw, h: 0.26, fontSize: Math.max(8, ctx.scale.kicker - 1), bold: true, color: ctx.pal.accent, align: 'center', valign: 'middle', charSpacing: 1 });
  }
  // 칩 (정부형: Ⅰ Ⅱ 번호)
  if (tok.title.style === 'chip') {
    const n = slideSpec._sectionIndex || 0;
    if (n > 0) {
      const chipH = (ctx.scale.title * 1.25) / 72;
      P.rect(ctx, slide, { x: M.left, y: master.titleY + 0.01, w: 0.54, h: chipH }, { fill: ctx.pal.primary, radius: 0 });
      P.ctxText(ctx, slide, numeralText(ctx, n, 'roman'), { x: M.left, y: master.titleY + 0.01, w: 0.54, h: chipH, fontSize: Math.round(ctx.scale.title * 0.72), bold: true, color: ctx.pal.on_primary, align: 'center', valign: 'middle', fontFace: ctx.font.numeral });
    }
  }
  // 제목 (액션 타이틀) — 2줄 안에 들어가도록 title pt에서 최대 6pt까지 축소
  const title = (slideSpec.title || '').trim();
  const titleW = W - M.left - M.right - master.chipShift - (sticker ? 1.5 : 0);
  const tlh = tok.typography.line_height.title;
  const fit = fitText([title], titleW, master.titleH, ctx.scale.title, ctx.scale.title - 6, { lineHeight: tlh, paraGapEm: 0, face: ctx.font.display, bold: tok.fonts.titleBold });
  if (!fit.fits || fit.lines > 2) ctx.warn(`제목이 2줄을 넘음(추정 ${fit.lines}줄, ${fit.pt}pt): "${title.slice(0, 40)}…" — 45자 이내로 줄인다`, {});
  if (fit.pt < ctx.scale.title) ctx.info(`제목 ${ctx.scale.title}→${fit.pt}pt 축소 (2줄 맞춤): "${title.slice(0, 30)}…"`);
  const trk = Math.round(fit.pt * (tok.typography.tracking_em.display || 0) * 10) / 10;
  slide.addText(title, Object.assign({ placeholder: 'title', fontSize: fit.pt, lineSpacingMultiple: spacingMultiple(tlh, ctx.font.display, tok.fonts.titleBold), lang: 'ko-KR' }, trk ? { charSpacing: trk } : {}));
  const bodyTop = master.titleY + master.titleH + (opts.bodyGap != null ? opts.bodyGap : 0.22);
  body.y = bodyTop;
  body.h = (hasSource ? sourceY - 0.1 : frame.footerY - 0.18) - bodyTop;
  return { slide, body, bg };
}

function drawTracker(ctx, slide, slideSpec, box) {
  const n = ctx.sections.length;
  const gap = 0.06;
  const w = (box.w - gap * (n - 1)) / n;
  ctx.sections.forEach((sec, i) => {
    const active = sec === slideSpec.section;
    P.rect(ctx, slide, { x: box.x + i * (w + gap), y: box.y, w, h: box.h }, { fill: active ? ctx.pal.primary : ctx.pal.line_faint, radius: 0 });
  });
}

// 슬라이드 끝: 출처·노트
function end(ctx, slideSpec) {
  const slide = ctx.slide;
  if (slideSpec.source_note) P.sourceNote(ctx, slide, slideSpec.source_note);
  const notes = [];
  if (slideSpec.speaker_notes) notes.push(slideSpec.speaker_notes);
  else if (slideSpec.takeaway) notes.push(`요지: ${slideSpec.takeaway}`);
  if (notes.length) slide.addNotes(notes.join('\n'));
}

module.exports = { defineMasters, begin, end, palette, numeralText, ROMAN };
