'use strict';
// 공통 그리기 프리미티브. 모든 좌표 inch, 글자 pt, 색 6자리 hex.
const { fitText, heightFor, linesFor, spacingMultiple } = require('./text');

// 타이포 옵션: 종류별 행간(절대 em)·폰트·굵기 → fitText/heightFor 의 opts 와 lineSpacingMultiple
function typo(ctx, kind, face, bold) {
  const T = ctx.tok.typography;
  const lh = T.line_height[kind] || T.line_height.body;
  const f = face || (kind === 'title' || kind === 'heading' ? ctx.font.display : ctx.font.body);
  return { lineHeight: lh, face: f, bold: !!bold, multiple: spacingMultiple(lh, f, !!bold) };
}

function ctxText(ctx, slide, text, opts) {
  const o = Object.assign({ isTextBox: true, margin: 0, fontFace: ctx.font.body, color: ctx.pal.ink, lang: 'ko-KR', valign: 'top', align: 'left' }, opts);
  if (o.font === 'display') { o.fontFace = ctx.font.display; delete o.font; }
  if (o.font === 'numeral') { o.fontFace = ctx.font.numeral; delete o.font; }
  if (o.italic && ctx.tok.typography && !ctx.tok.typography.italic_hangul && /[가-힣]/.test(JSON.stringify(text))) { delete o.italic; ctx.info('한글 기울임 제거 (CJK 규칙)'); }
  // 단일 행 라벨: 줄바꿈 금지 + 폭 여유 — 한 글자만 다음 줄로 떨어지는 사고 방지
  if (o.singleLine) { o.wrap = false; delete o.singleLine; }
  slide.addText(text, o);
  return o;
}

// 상자에 맞춰 글자 크기를 정해 쓰는 텍스트 (문단 배열 또는 문자열). 넘치면 ctx.warn.
function fitBox(ctx, slide, paragraphs, box, opts = {}) {
  const paras = Array.isArray(paragraphs) ? paragraphs : [String(paragraphs || '')];
  const maxPt = opts.maxPt || ctx.scale.body;
  const minPt = opts.minPt || ctx.scale.body_min;
  const to = opts.textOptions || {};
  const face = to.fontFace || (to.font === 'display' ? ctx.font.display : ctx.font.body);
  const ty = typo(ctx, opts.kind || 'body', face, to.bold);
  const lh = opts.lineHeight || ty.lineHeight;
  const paraGapEm = opts.paraGapEm == null ? 0.4 : opts.paraGapEm;
  const r = fitText(paras, box.w, box.h, maxPt, minPt, { lineHeight: lh, paraGapEm, face, bold: ty.bold });
  if (!r.fits) ctx.warn(`텍스트 넘침 추정: ${box.name || ''} 필요 ${r.needIn.toFixed(2)}in > 상자 ${box.h.toFixed(2)}in (최소 ${minPt}pt). 글자를 줄이거나 슬라이드를 나눈다`, { text: paras.join(' ').slice(0, 50) });
  const runs = paras.map((p, i) => ({ text: p, options: Object.assign({ breakLine: i < paras.length - 1 }, opts.runOptions ? opts.runOptions(i, p) : {}) }));
  const o = Object.assign({ x: box.x, y: box.y, w: box.w, h: box.h, fontSize: r.pt, lineSpacingMultiple: spacingMultiple(lh, face, ty.bold), paraSpaceAfter: Math.round(r.pt * paraGapEm) }, to);
  if (opts.bullets) {
    runs.forEach((run, i) => { run.options.bullet = opts.bullets(i) || true; run.options.indentLevel = opts.indent ? opts.indent(i) : 0; });
    delete o.paraSpaceAfter;
    runs.forEach((run) => { run.options.paraSpaceAfter = Math.round(r.pt * paraGapEm); });
  }
  ctxText(ctx, slide, runs, o);
  return r;
}

// 글머리 목록: items = [{text, level?, bold?}] 또는 string[]
function bulletList(ctx, slide, items, box, opts = {}) {
  const list = items.map((it) => (typeof it === 'string' ? { text: it, level: 0 } : it));
  const markers = ctx.tok.list.markers || ['•', '–', '·'];
  const codes = markers.map((m) => m.codePointAt(0).toString(16).toUpperCase().padStart(4, '0'));
  const maxPt = opts.maxPt || ctx.scale.body;
  const minPt = opts.minPt || ctx.scale.body_min;
  const face = (opts.textOptions && opts.textOptions.fontFace) || ctx.font.body;
  const lh = opts.lineHeight || ctx.tok.typography.line_height.body;
  const paraGapEm = opts.paraGapEm == null ? 0.45 : opts.paraGapEm;
  // 들여쓰기 폭 고려: 레벨당 0.28in
  const r = fitText(list.map((it) => it.text), box.w - 0.3, box.h, maxPt, minPt, { lineHeight: lh, paraGapEm, face, bold: list.some((it) => it.bold) });
  if (!r.fits) ctx.warn(`목록 넘침 추정: ${box.name || ''} 필요 ${r.needIn.toFixed(2)}in > 상자 ${box.h.toFixed(2)}in`, { text: list[0].text.slice(0, 40) });
  const runs = list.map((it, i) => ({
    text: it.text,
    options: {
      breakLine: i < list.length - 1,
      bullet: opts.numbered && (it.level || 0) === 0 ? { type: 'number' } : { code: codes[Math.min(it.level || 0, codes.length - 1)] },
      indentLevel: it.level || 0,
      bold: !!it.bold,
      color: it.color || opts.color || ctx.pal.ink,
      paraSpaceAfter: Math.round(r.pt * paraGapEm),
      fontSize: (it.level || 0) > 0 ? Math.max(minPt, r.pt - 1) : r.pt,
    },
  }));
  ctxText(ctx, slide, runs, Object.assign({ x: box.x, y: box.y, w: box.w, h: box.h, fontSize: r.pt, lineSpacingMultiple: spacingMultiple(lh, face, false) }, opts.textOptions || {}));
  return r;
}

function rect(ctx, slide, box, opts = {}) {
  const o = { x: box.x, y: box.y, w: box.w, h: box.h };
  if (opts.fill) o.fill = typeof opts.fill === 'string' ? { color: opts.fill } : opts.fill;
  if (opts.line) o.line = typeof opts.line === 'string' ? { color: opts.line, width: opts.lineWidth || ctx.tok.geometry.line_width } : opts.line;
  else o.line = { type: 'none' };
  const radius = opts.radius != null ? opts.radius : ctx.tok.geometry.radius;
  if (radius > 0) { o.rectRadius = radius / 72; slide.addShape(ctx.pres.ShapeType.roundRect, o); }
  else slide.addShape(ctx.pres.ShapeType.rect, o);
}

function hline(ctx, slide, x, y, w, opts = {}) {
  slide.addShape(ctx.pres.ShapeType.line, { x, y, w, h: 0, line: { color: opts.color || ctx.pal.line, width: opts.width || ctx.tok.geometry.line_width, dashType: opts.dash || 'solid' } });
}

function vline(ctx, slide, x, y, h, opts = {}) {
  slide.addShape(ctx.pres.ShapeType.line, { x, y, w: 0, h, line: { color: opts.color || ctx.pal.line, width: opts.width || ctx.tok.geometry.line_width, dashType: opts.dash || 'solid' } });
}

function arrow(ctx, slide, x1, y1, x2, y2, opts = {}) {
  slide.addShape(ctx.pres.ShapeType.line, { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1), h: Math.abs(y2 - y1), flipH: x2 < x1, flipV: y2 < y1, line: { color: opts.color || ctx.pal.ink_muted, width: opts.width || 1, endArrowType: 'triangle' } });
}

// 큰 숫자 + 단위 (Paperlogy: 숫자는 강력한 시각 요소)
function bigNumber(ctx, slide, value, unit, box, opts = {}) {
  const pt = opts.pt || ctx.scale.hero_number;
  const unitPt = Math.round(pt * 0.38);
  const runs = [{ text: String(value), options: { fontSize: pt, bold: true, color: opts.color || ctx.pal.primary, fontFace: ctx.font.numeral, charSpacing: Math.round(pt * (ctx.tok.typography.tracking_em.numeral || 0) * 10) / 10 } }];
  if (unit) runs.push({ text: unit, options: { fontSize: unitPt, bold: true, color: opts.color || ctx.pal.primary, fontFace: ctx.font.numeral } });
  ctxText(ctx, slide, runs, { x: box.x, y: box.y, w: box.w, h: box.h, valign: opts.valign || 'bottom', align: opts.align || 'left', lineSpacingMultiple: 0.9, fontSize: pt });
}

// 번호 라벨 (01, 1, Ⅰ) — 둥근 배지 대신 큰 숫자 타이포그래피
function numeral(ctx, slide, n, box, opts = {}) {
  ctxText(ctx, slide, String(n), { x: box.x, y: box.y, w: box.w, h: box.h, fontSize: opts.pt || Math.round(ctx.scale.title * 1.1), bold: true, color: opts.color || ctx.pal.primary, fontFace: ctx.font.numeral, valign: opts.valign || 'top', align: opts.align || 'left' });
}

// 작은 대문자 라벨 (kicker / 섹션 라벨 / exhibit)
function label(ctx, slide, text, box, opts = {}) {
  ctxText(ctx, slide, text, { x: box.x, y: box.y, w: box.w, h: box.h, fontSize: opts.pt || ctx.scale.kicker, bold: opts.bold != null ? opts.bold : true, color: opts.color || ctx.pal.ink_muted, charSpacing: opts.spacing == null ? Math.round((opts.pt || ctx.scale.kicker) * ctx.tok.typography.tracking_em.kicker * 10) / 10 : opts.spacing, valign: 'middle', align: opts.align || 'left', fontFace: ctx.font.body, singleLine: !opts.wrap });
}

// 헤딩 + 본문 블록 — 세로로 heading 아래 detail. 반환: 실제 사용 높이
function headingDetail(ctx, slide, heading, detail, box, opts = {}) {
  const hPt = opts.headingPt || Math.round(ctx.scale.body + 2);
  const dPt = opts.detailPt || ctx.scale.body - 1;
  const dMin = opts.detailMin || ctx.scale.body_min;
  const ht = typo(ctx, 'heading', ctx.font.display, true);
  const hH = heightFor([heading], box.w, hPt, { lineHeight: ht.lineHeight, face: ht.face, bold: true }) + 0.04;
  ctxText(ctx, slide, heading, { x: box.x, y: box.y, w: box.w, h: hH, fontSize: hPt, bold: true, color: opts.headingColor || ctx.pal.ink_strong || ctx.pal.ink, fontFace: ctx.font.display, lineSpacingMultiple: ht.multiple });
  let used = hH;
  if (detail) {
    const dBox = { x: box.x, y: box.y + hH + 0.06, w: box.w, h: Math.max(0.3, box.h - hH - 0.06), name: box.name };
    const r = fitBox(ctx, slide, Array.isArray(detail) ? detail : [detail], dBox, { maxPt: dPt, minPt: dMin, textOptions: { color: opts.detailColor || ctx.pal.ink_muted } });
    used += 0.06 + Math.min(dBox.h, r.needIn);
  }
  return used;
}

// 출처·주석 라인 (슬라이드 하단, 푸터 위)
function sourceNote(ctx, slide, text) {
  if (!text) return;
  const f = ctx.frame;
  ctxText(ctx, slide, text, { x: f.left, y: f.sourceY, w: f.width, h: f.sourceH, fontSize: ctx.scale.source, color: ctx.pal.ink_faint, valign: 'bottom' });
}

// 콜아웃: 왼쪽 굵은 세로선 + 텍스트 (장식 스트라이프가 아니라 인용/강조 의미)
function callout(ctx, slide, text, box, opts = {}) {
  vline(ctx, slide, box.x, box.y + 0.03, box.h - 0.06, { color: opts.color || ctx.pal.accent, width: 2.25 });
  return fitBox(ctx, slide, Array.isArray(text) ? text : [text], { x: box.x + 0.16, y: box.y, w: box.w - 0.16, h: box.h, name: 'callout' }, { maxPt: opts.maxPt || ctx.scale.body, minPt: opts.minPt || ctx.scale.body_min, textOptions: { color: opts.textColor || ctx.pal.ink, bold: !!opts.bold, valign: opts.valign || 'top' } });
}

// 표 — 헤더 하단 굵은 선, 행 하단 얇은 선, 세로선 없음 (컨설팅·정부 공통 관행)
function table(ctx, slide, columns, rows, box, opts = {}) {
  const pt = opts.pt || ctx.scale.table;
  const n = columns.length;
  let colW = opts.colW;
  if (!colW) {
    const weights = columns.map((_, ci) => Math.max(3, ...[columns[ci], ...rows.map((r) => String(r[ci] == null ? '' : r[ci]))].map((s) => Math.min(28, s.length))));
    const tot = weights.reduce((a, b) => a + b, 0);
    colW = weights.map((w) => (w / tot) * box.w);
  }
  const align = opts.align || columns.map((_, ci) => (rows.every((r) => /^[\d,.%+\-–—억만원천조$₩ ]*$/.test(String(r[ci] == null ? '' : r[ci]))) ? 'right' : 'left'));
  const B = (pt_, color) => ({ type: 'solid', pt: pt_, color });
  const none = { type: 'none' };
  // 표 토큰 (프로파일 tokens.table): header_fill·header_color·first_col_fill·zebra·grid(rows|all)
  const TT = Object.assign({ header_fill: 'surface', header_color: 'ink', first_col_fill: null, zebra: false, grid: 'rows' }, ctx.tok.table || {}, opts.style || {});
  const col = (v, fb) => (!v ? fb : /^[0-9A-Fa-f]{6}$/.test(v) ? v.toUpperCase() : (ctx.pal[v] || fb));
  const headFill = opts.headFill || col(TT.header_fill, ctx.pal.surface);
  const headColor = col(TT.header_color, ctx.pal.ink);
  const headBorderColor = headFill === ctx.pal.surface ? ctx.pal.ink : ctx.pal.background;
  const vb = TT.grid === 'all' ? B(0.5, ctx.pal.line) : none; // 세로 경계
  const styleOf = (ri, ci) => (typeof opts.cellStyle === 'function' ? opts.cellStyle(ri, ci) || {} : {});
  const header = columns.map((c, ci) => ({ text: String(c), options: Object.assign({ bold: true, color: headColor, fill: { color: headFill }, align: TT.header_align || align[ci], valign: 'middle', border: [none, vb, B(headFill === ctx.pal.surface ? 1.25 : 0.5, headBorderColor), vb] }, styleOf(-1, ci)) }));
  const firstFill = col(TT.first_col_fill, null);
  const body = rows.map((r, ri) => r.map((cell, ci) => {
    const hl = (opts.highlightRows || []).includes(ri);
    const zebra = TT.zebra && ri % 2 === 1;
    const fill = hl ? ctx.pal.primary_soft : (ci === 0 && firstFill) ? firstFill : zebra ? ctx.pal.surface : ctx.pal.background;
    const o = { bold: hl || (opts.boldFirstCol && ci === 0), color: hl ? ctx.pal.primary : (ci === 0 && opts.boldFirstCol ? ctx.pal.ink_strong : ctx.pal.ink), fill: { color: fill }, align: align[ci], valign: 'middle', border: [none, vb, B(0.5, ctx.pal.line), vb] };
    return { text: String(cell == null ? '' : cell), options: Object.assign(o, styleOf(ri, ci)) };
  }));
  const rowH = opts.rowH || Math.min(opts.maxRowH || 0.5, Math.max(0.32, (box.h - 0.1) / (rows.length + 1)));
  const est = rowH * (rows.length + 1);
  if (est > box.h + 0.05) ctx.warn(`표가 상자보다 큼: ${rows.length}행 ×${rowH.toFixed(2)}in = ${est.toFixed(2)}in > ${box.h.toFixed(2)}in. 행을 줄이거나 부록으로`, {});
  slide.addTable([header, ...body], { x: box.x, y: box.y, w: box.w, colW, rowH, fontSize: pt, fontFace: ctx.font.body, color: ctx.pal.ink, margin: [0.04, 0.1, 0.04, 0.1], autoPage: false, lang: 'ko-KR' });
  return est;
}

// 문자열 안의 강조 구간(emphasis 문자열 또는 배열)을 다른 색 run 으로 쪼갠다
function emphasisRuns(text, emphasis, color, extra = {}) {
  const words = (Array.isArray(emphasis) ? emphasis : [emphasis]).filter(Boolean);
  if (!words.length) return [{ text, options: Object.assign({}, extra) }];
  const re = new RegExp(`(${words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'g');
  return String(text).split(re).filter((p) => p.length).map((p) => ({ text: p, options: Object.assign({}, extra, words.includes(p) ? { color } : {}) }));
}

// 이미지 (cover 크롭) + 선택적 스크림
function image(ctx, slide, assetId, box, opts = {}) {
  const p = ctx.asset(assetId);
  if (!p) { ctx.warn(`이미지 자산 '${assetId}' 없음 — 회색 자리표시`, {}); rect(ctx, slide, box, { fill: ctx.pal.surface_strong }); ctxText(ctx, slide, `이미지: ${assetId}`, { x: box.x, y: box.y, w: box.w, h: box.h, align: 'center', valign: 'middle', fontSize: ctx.scale.caption, color: ctx.pal.ink_faint }); return false; }
  slide.addImage({ path: p, x: box.x, y: box.y, w: box.w, h: box.h, sizing: { type: opts.sizing || 'cover', w: box.w, h: box.h }, objectName: opts.name || assetId });
  if (opts.scrim) rect(ctx, slide, box, { fill: { color: ctx.tok.imagery.scrim, transparency: opts.scrimTransparency != null ? opts.scrimTransparency : ctx.tok.imagery.scrim_transparency }, radius: 0 });
  return true;
}

module.exports = { ctxText, fitBox, bulletList, rect, hline, vline, arrow, bigNumber, numeral, label, headingDetail, sourceNote, callout, table, image, heightFor, linesFor, typo, emphasisRuns };
