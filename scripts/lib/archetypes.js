'use strict';
// 아키타입 렌더러. 각 함수 (ctx, slide, s, body) — s = 슬라이드 명세, body = 본문 영역 {x,y,w,h}
const P = require('./primitives');
const { buildChart } = require('./charts');
const { numeralText } = require('./frame');
const { heightFor, fitText, spacingMultiple, textWidthIn } = require('./text');

const D = (ctx, bold = true) => ({ face: ctx.font.display, bold });
const B = (ctx) => ({ face: ctx.font.body, bold: false });

const c = (s) => s.content || {};
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

// 열 분할: n개 열, gap
function columns(box, n, gap) {
  const w = (box.w - gap * (n - 1)) / n;
  return Array.from({ length: n }, (_, i) => ({ x: box.x + i * (w + gap), y: box.y, w, h: box.h }));
}

// ---------------------------------------------------------------- cover
function cover(ctx, slide, s, body) {
  const tok = ctx.tok, W = tok.canvas.width, H = tok.canvas.height, M = tok.canvas.margin;
  const k = c(s);
  const variant = tok.cover.variant;
  const meta = ctx.spec.metadata;
  const img = k.image;
  const dark = ctx.pal.dark;
  const titlePt = ctx.scale.cover_title;
  const lines = [meta.organization || k.organization, k.date || meta.date, k.presenter || meta.presenter].filter(Boolean);
  if (variant === 'light-left' || variant === 'image-or-dark' && !img && !dark) {
    // 오른쪽 색면(또는 이미지) + 왼쪽 타이포
    const fieldX = W * 0.62;
    if (img) P.image(ctx, slide, img, { x: fieldX, y: 0, w: W - fieldX, h: H }, { scrim: true, scrimTransparency: 55 });
    else P.rect(ctx, slide, { x: fieldX, y: 0, w: W - fieldX, h: H }, { fill: tok.cover.band_color || ctx.pal.primary, radius: 0 });
    const tw = fieldX - M.left - 0.5;
    if (k.tagline) P.label(ctx, slide, k.tagline, { x: M.left, y: H * 0.3 - 0.4, w: tw, h: 0.3 }, { color: ctx.pal.primary, pt: ctx.scale.kicker + 1 });
    const fit = fitText([s.title], tw, 2.6, titlePt, titlePt - 12, Object.assign({ lineHeight: 1.15 }, D(ctx)));
    P.ctxText(ctx, slide, s.title, { x: M.left, y: H * 0.3, w: tw, h: Math.min(2.6, fit.needIn) + 0.1, fontSize: fit.pt, bold: true, color: ctx.pal.primary, fontFace: ctx.font.display, valign: 'top', lineSpacingMultiple: spacingMultiple(1.15, ctx.font.display, true) });
    const subY = H * 0.3 + Math.min(2.6, fit.needIn) + 0.25;
    if (k.subtitle) P.fitBox(ctx, slide, [k.subtitle], { x: M.left, y: subY, w: tw, h: 1.0, name: 'cover subtitle' }, { maxPt: ctx.scale.subtitle + 2, minPt: ctx.scale.subtitle - 2, textOptions: { color: ctx.pal.ink_muted } });
    if (lines.length) P.ctxText(ctx, slide, lines.map((t, i) => ({ text: t, options: { breakLine: i < lines.length - 1, bold: i === 0 } })), { x: M.left, y: H - M.bottom - 1.0, w: tw, h: 0.9, fontSize: ctx.scale.caption + 1, color: ctx.pal.ink, valign: 'bottom', paraSpaceAfter: 2 });
    if (ctx.asset('logo')) slide.addImage({ path: ctx.asset('logo'), x: M.left, y: M.top, h: 0.5, w: 1.8, sizing: { type: 'contain', w: 1.8, h: 0.5 } });
    return;
  }
  // 어두운 배경 (dark-left / dark-center / image)
  if (img) P.image(ctx, slide, img, { x: 0, y: 0, w: W, h: H }, { scrim: true });
  const center = variant === 'dark-center';
  const tw = center ? W - 2 * M.left - 1.0 : W * 0.72;
  const tx = center ? (W - tw) / 2 : M.left;
  if (k.tagline) P.label(ctx, slide, k.tagline, { x: tx, y: H * 0.3 - 0.42, w: tw, h: 0.3 }, { color: ctx.pal.accent, pt: ctx.scale.kicker + 1, align: center ? 'center' : 'left' });
  const fit = fitText([s.title], tw, 2.6, titlePt, titlePt - 12, Object.assign({ lineHeight: 1.15 }, D(ctx)));
  P.ctxText(ctx, slide, s.title, { x: tx, y: H * 0.3, w: tw, h: Math.min(2.6, fit.needIn) + 0.1, fontSize: fit.pt, bold: true, color: ctx.pal.ink, fontFace: ctx.font.display, valign: 'top', align: center ? 'center' : 'left', lineSpacingMultiple: spacingMultiple(1.15, ctx.font.display, true) });
  const subY = H * 0.3 + Math.min(2.6, fit.needIn) + 0.25;
  if (k.subtitle) P.fitBox(ctx, slide, [k.subtitle], { x: tx, y: subY, w: tw, h: 1.0, name: 'cover subtitle' }, { maxPt: ctx.scale.subtitle + 2, minPt: ctx.scale.subtitle - 2, textOptions: { color: ctx.pal.ink_muted, align: center ? 'center' : 'left' } });
  if (lines.length) P.ctxText(ctx, slide, lines.map((t, i) => ({ text: t, options: { breakLine: i < lines.length - 1, bold: i === 0 } })), { x: tx, y: H - M.bottom - 1.0, w: tw, h: 0.9, fontSize: ctx.scale.caption + 1, color: ctx.pal.ink_muted, valign: 'bottom', align: center ? 'center' : 'left', paraSpaceAfter: 2 });
  if (ctx.spec.metadata.sticker || s.sticker) {
    const st = s.sticker || ctx.spec.metadata.sticker;
    P.rect(ctx, slide, { x: W - M.right - 1.3, y: M.top, w: 1.3, h: 0.28 }, { line: ctx.pal.accent, lineWidth: 0.75, radius: 0 });
    P.ctxText(ctx, slide, st, { x: W - M.right - 1.3, y: M.top, w: 1.3, h: 0.28, fontSize: ctx.scale.kicker, bold: true, color: ctx.pal.accent, align: 'center', valign: 'middle', charSpacing: 1 });
  }
}

// ---------------------------------------------------------------- agenda
function agenda(ctx, slide, s, body) {
  const items = c(s).items || [];
  const two = items.length > 5;
  const cols = two ? columns(body, 2, 0.6) : [body];
  const per = Math.ceil(items.length / cols.length);
  const rowH = clamp(body.h / per, 0.55, 1.1);
  items.forEach((it, i) => {
    const col = cols[Math.floor(i / per)];
    const y = col.y + (i % per) * rowH;
    P.numeral(ctx, slide, numeralText(ctx, i + 1), { x: col.x, y, w: 0.8, h: rowH * 0.8 }, { pt: Math.round(ctx.scale.title * 0.95), color: ctx.pal.primary });
    P.ctxText(ctx, slide, it.label, { x: col.x + 0.9, y: y + 0.02, w: col.w - 0.9, h: rowH * 0.5, fontSize: ctx.scale.body + 2, bold: true, color: ctx.pal.ink, fontFace: ctx.font.display });
    if (it.detail) P.ctxText(ctx, slide, it.detail, { x: col.x + 0.9, y: y + rowH * 0.48, w: col.w - 0.9, h: rowH * 0.45, fontSize: ctx.scale.caption + 1, color: ctx.pal.ink_muted });
    if (i % per < per - 1 && i < items.length - 1) P.hline(ctx, slide, col.x, y + rowH - 0.06, col.w, { color: ctx.pal.line_faint });
  });
}

// ---------------------------------------------------------------- executive_summary
function executive_summary(ctx, slide, s, body) {
  const k = c(s);
  const points = k.points || [];
  const leftW = body.w * 0.36;
  const gap = 0.5;
  // 왼쪽: 답(핵심 결론)
  const answerBox = { x: body.x, y: body.y, w: leftW, h: body.h - (k.decision ? 1.0 : 0) };
  P.label(ctx, slide, '핵심 결론', { x: answerBox.x, y: answerBox.y, w: answerBox.w, h: 0.24 }, { color: ctx.pal.primary });
  P.callout(ctx, slide, k.answer || s.takeaway || '', { x: answerBox.x, y: answerBox.y + 0.34, w: answerBox.w, h: answerBox.h - 0.34 }, { maxPt: ctx.scale.body + 5, minPt: ctx.scale.body, bold: true, color: ctx.pal.primary, textColor: ctx.pal.ink });
  // 오른쪽: 근거 포인트 (번호 행)
  const rx = body.x + leftW + gap;
  const rw = body.w - leftW - gap;
  const n = Math.max(1, points.length);
  const rowGap = 0.14;
  const rowH = (body.h - (k.decision ? 1.0 : 0) - rowGap * (n - 1)) / n;
  points.forEach((p, i) => {
    const y = body.y + i * (rowH + rowGap);
    P.numeral(ctx, slide, numeralText(ctx, i + 1, ctx.tok.list.numbering[0] === '01' ? 'pad' : 'plain'), { x: rx, y: y - 0.02, w: 0.62, h: rowH }, { pt: Math.round(ctx.scale.title * 0.9), color: ctx.pal.primary });
    P.headingDetail(ctx, slide, p.heading, p.detail, { x: rx + 0.7, y, w: rw - 0.7, h: rowH, name: `point ${i + 1}` }, { headingPt: ctx.scale.body + 1, detailPt: ctx.scale.body - 1 });
    if (i < n - 1) P.hline(ctx, slide, rx + 0.7, y + rowH + rowGap / 2, rw - 0.7, { color: ctx.pal.line_faint });
  });
  if (k.decision) {
    const dy = body.y + body.h - 0.8;
    P.rect(ctx, slide, { x: body.x, y: dy, w: body.w, h: 0.8 }, { fill: ctx.pal.primary_soft, radius: 0 });
    P.label(ctx, slide, '요청 결정', { x: body.x + 0.2, y: dy + 0.08, w: 1.6, h: 0.24 }, { color: ctx.pal.primary });
    P.fitBox(ctx, slide, [k.decision], { x: body.x + 0.2, y: dy + 0.32, w: body.w - 0.4, h: 0.42, name: 'decision' }, { maxPt: ctx.scale.body, minPt: ctx.scale.body_min, textOptions: { bold: true, color: ctx.pal.ink } });
  }
}

// ---------------------------------------------------------------- section_divider
function section_divider(ctx, slide, s, body) {
  const tok = ctx.tok, W = tok.canvas.width, H = tok.canvas.height, M = tok.canvas.margin;
  const k = c(s);
  if (k.image) P.image(ctx, slide, k.image, { x: W * 0.55, y: 0, w: W * 0.45, h: H }, { scrim: true, scrimTransparency: 60 });
  const n = k.number != null ? k.number : s._sectionIndex;
  const tw = k.image ? W * 0.5 - M.left : W - 2 * M.left;
  if (n != null) P.numeral(ctx, slide, numeralText(ctx, Number(n) || 1), { x: M.left, y: H * 0.22, w: tw, h: 1.4 }, { pt: ctx.scale.hero_number, color: ctx.pal.dark ? ctx.pal.accent : ctx.pal.primary });
  const fit = fitText([s.title], tw, 1.8, ctx.scale.section_title, ctx.scale.section_title - 10, Object.assign({ lineHeight: 1.15 }, D(ctx)));
  P.ctxText(ctx, slide, s.title, { x: M.left, y: H * 0.22 + 1.45, w: tw, h: Math.min(1.8, fit.needIn) + 0.1, fontSize: fit.pt, bold: true, color: ctx.pal.ink, fontFace: ctx.font.display, valign: 'top', lineSpacingMultiple: spacingMultiple(1.15, ctx.font.display, true) });
  if (k.subtitle) P.fitBox(ctx, slide, [k.subtitle], { x: M.left, y: H * 0.22 + 1.45 + Math.min(1.8, fit.needIn) + 0.2, w: tw, h: 1.0, name: 'section subtitle' }, { maxPt: ctx.scale.subtitle + 2, minPt: ctx.scale.subtitle - 2, textOptions: { color: ctx.pal.ink_muted } });
}

// ---------------------------------------------------------------- hero_metric
function hero_metric(ctx, slide, s, body) {
  const k = c(s);
  const metrics = (k.metrics || []).slice(0, 3);
  if (!metrics.length) { ctx.warn('hero_metric: metrics 비어 있음', {}); return; }
  const ctxH = k.context ? 1.1 : 0;
  if (metrics.length === 1) {
    const m = metrics[0];
    const lw = body.w * 0.42;
    P.bigNumber(ctx, slide, m.value, m.unit, { x: body.x, y: body.y, w: lw, h: body.h * 0.55 }, { valign: 'bottom' });
    P.ctxText(ctx, slide, m.label, { x: body.x, y: body.y + body.h * 0.57, w: lw, h: 0.5, fontSize: ctx.scale.body + 1, bold: true, color: ctx.pal.ink });
    if (m.delta) P.ctxText(ctx, slide, m.delta, { x: body.x, y: body.y + body.h * 0.57 + 0.5, w: lw, h: 0.4, fontSize: ctx.scale.body, color: m.trend === 'down' ? ctx.pal.negative : m.trend === 'up' ? ctx.pal.positive : ctx.pal.ink_muted, bold: true });
    const rx = body.x + lw + 0.6;
    const paras = [k.context, k.comparison].filter(Boolean);
    if (paras.length) P.callout(ctx, slide, paras, { x: rx, y: body.y + 0.2, w: body.w - lw - 0.6, h: body.h - 0.4 }, { maxPt: ctx.scale.body + 2, minPt: ctx.scale.body_min, color: ctx.pal.accent });
    return;
  }
  const cols = columns({ x: body.x, y: body.y, w: body.w, h: body.h - ctxH }, metrics.length, 0.5);
  const numPt = Math.round(ctx.scale.hero_number * (metrics.length === 3 ? 0.78 : 0.9));
  const numH = (numPt * 1.15) / 72;
  const blockH = numH + 0.55 + 0.4;
  const top = cols[0].y + Math.max(0.1, (cols[0].h - blockH) * 0.35); // 위쪽으로 당겨 빈 공간이 아래보다 위에 덜 쌓이게
  metrics.forEach((m, i) => {
    const col = cols[i];
    if (i > 0) P.vline(ctx, slide, col.x - 0.25, col.y + 0.1, col.h - 0.2, { color: ctx.pal.line_faint });
    P.bigNumber(ctx, slide, m.value, m.unit, { x: col.x, y: top, w: col.w, h: numH }, { valign: 'bottom', pt: numPt });
    P.ctxText(ctx, slide, m.label, { x: col.x, y: top + numH + 0.08, w: col.w, h: 0.5, fontSize: ctx.scale.body, bold: true, color: ctx.pal.ink });
    if (m.delta) P.ctxText(ctx, slide, m.delta, { x: col.x, y: top + numH + 0.58, w: col.w, h: 0.4, fontSize: ctx.scale.body - 1, color: m.trend === 'down' ? ctx.pal.negative : m.trend === 'up' ? ctx.pal.positive : ctx.pal.ink_muted, bold: true });
  });
  if (k.context) {
    P.hline(ctx, slide, body.x, body.y + body.h - ctxH + 0.1, body.w, { color: ctx.pal.line });
    P.fitBox(ctx, slide, [k.context, k.comparison].filter(Boolean), { x: body.x, y: body.y + body.h - ctxH + 0.25, w: body.w, h: ctxH - 0.3, name: 'context' }, { maxPt: ctx.scale.body, minPt: ctx.scale.body_min, textOptions: { color: ctx.pal.ink } });
  }
}

// ---------------------------------------------------------------- evidence_chart
function evidence_chart(ctx, slide, s, body) {
  const k = c(s);
  const layout = k.layout || (k.insight || (k.callouts || []).length ? 'chart-left' : 'chart-full');
  let chartBox, sideBox;
  if (layout === 'chart-full') { chartBox = { x: body.x, y: body.y, w: body.w, h: body.h }; }
  else {
    const cw = body.w * 0.63;
    const sw = body.w - cw - 0.5;
    chartBox = { x: layout === 'chart-left' ? body.x : body.x + sw + 0.5, y: body.y, w: cw, h: body.h };
    sideBox = { x: layout === 'chart-left' ? body.x + cw + 0.5 : body.x, y: body.y + 0.05, w: sw, h: body.h - 0.1 };
  }
  if (k.chart) buildChart(ctx, slide, k.chart, chartBox);
  else ctx.warn('evidence_chart: chart 없음', {});
  if (sideBox) {
    let y = sideBox.y;
    if (k.insight) {
      const h = Math.min(sideBox.h * 0.5, heightFor([k.insight], sideBox.w - 0.16, ctx.scale.body + 1, { lineHeight: ctx.tok.typography.line_height.body, face: ctx.font.body, bold: true }) + 0.1);
      P.callout(ctx, slide, k.insight, { x: sideBox.x, y, w: sideBox.w, h }, { maxPt: ctx.scale.body + 1, minPt: ctx.scale.body_min, bold: true });
      y += h + 0.3;
    }
    const callouts = (k.callouts || []).slice(0, 3);
    if (callouts.length) P.bulletList(ctx, slide, callouts, { x: sideBox.x, y, w: sideBox.w, h: sideBox.y + sideBox.h - y, name: 'callouts' }, { maxPt: ctx.scale.body, minPt: ctx.scale.body_min, color: ctx.pal.ink_muted });
  }
}

// ---------------------------------------------------------------- comparison
function comparison(ctx, slide, s, body) {
  const k = c(s);
  const cols = ['', ...(k.columns || [])];
  const rows = (k.rows || []).map((r) => [r.criterion, ...(r.cells || [])]);
  const verdictH = k.verdict ? 0.75 : 0;
  const win = k.winner;
  const n = cols.length;
  const firstW = body.w * 0.24;
  const colW = [firstW, ...Array(n - 1).fill((body.w - firstW) / (n - 1))];
  const none = { type: 'none' };
  const B = (pt, color) => ({ type: 'solid', pt, color });
  const header = cols.map((h, ci) => ({ text: String(h), options: { bold: true, color: win != null && ci - 1 === win ? ctx.pal.on_primary : ctx.pal.ink, fill: { color: win != null && ci - 1 === win ? ctx.pal.primary : ctx.pal.surface }, align: ci === 0 ? 'left' : 'center', valign: 'middle', border: [none, none, B(1.25, ctx.pal.ink), none] } }));
  const bodyRows = rows.map((r) => r.map((cell, ci) => ({ text: String(cell == null ? '' : cell), options: { bold: ci === 0, color: ctx.pal.ink, fill: { color: win != null && ci - 1 === win ? ctx.pal.primary_soft : ctx.pal.background }, align: ci === 0 ? 'left' : 'center', valign: 'middle', border: [none, none, B(0.5, ctx.pal.line), none] } })));
  const rowH = clamp((body.h - verdictH - 0.2) / (rows.length + 1), 0.36, 0.8);
  slide.addTable([header, ...bodyRows], { x: body.x, y: body.y, w: body.w, colW, rowH, fontSize: ctx.scale.table, fontFace: ctx.font.body, color: ctx.pal.ink, margin: [0.05, 0.1, 0.05, 0.1], autoPage: false, lang: 'ko-KR' });
  if (k.verdict) P.callout(ctx, slide, k.verdict, { x: body.x, y: body.y + body.h - verdictH + 0.1, w: body.w, h: verdictH - 0.1 }, { maxPt: ctx.scale.body + 1, minPt: ctx.scale.body_min, bold: true });
}

// ---------------------------------------------------------------- process
function process(ctx, slide, s, body) {
  const k = c(s);
  const steps = (k.steps || []).slice(0, 7);
  const style = k.style || 'numbered';
  const n = steps.length || 1;
  const cols = columns(body, n, 0.3);
  if (style === 'chevron') {
    const chH = 0.7;
    steps.forEach((st, i) => {
      const col = cols[i];
      slide.addShape(i === 0 ? ctx.pres.ShapeType.homePlate : ctx.pres.ShapeType.chevron, { x: col.x - (i ? 0.12 : 0), y: body.y, w: col.w + 0.3, h: chH, fill: { color: i === n - 1 ? ctx.pal.accent : ctx.pal.primary }, line: { type: 'none' } });
      P.ctxText(ctx, slide, st.title, { x: col.x + 0.18, y: body.y, w: col.w - 0.35, h: chH, fontSize: ctx.scale.body, bold: true, color: ctx.pal.on_primary, valign: 'middle', align: 'center' });
      P.fitBox(ctx, slide, [st.detail, st.owner ? `담당: ${st.owner}` : null].filter(Boolean), { x: col.x, y: body.y + chH + 0.25, w: col.w - 0.1, h: body.h - chH - 0.3, name: `step ${i + 1}` }, { maxPt: ctx.scale.body - 1, minPt: ctx.scale.body_min, textOptions: { color: ctx.pal.ink_muted } });
    });
    return;
  }
  if (style === 'timeline') {
    const ly = body.y + 0.45;
    P.hline(ctx, slide, body.x, ly, body.w, { color: ctx.pal.line, width: 1.5 });
    steps.forEach((st, i) => {
      const col = cols[i];
      const cx = col.x + 0.16;
      slide.addShape(ctx.pres.ShapeType.ellipse, { x: cx - 0.11, y: ly - 0.11, w: 0.22, h: 0.22, fill: { color: i === n - 1 ? ctx.pal.accent : ctx.pal.primary }, line: { color: ctx.pal.background, width: 2 } });
      P.ctxText(ctx, slide, st.title, { x: col.x, y: body.y, w: col.w, h: 0.3, fontSize: ctx.scale.body, bold: true, color: ctx.pal.ink, fontFace: ctx.font.display });
      P.fitBox(ctx, slide, [st.detail, st.owner ? `담당: ${st.owner}` : null].filter(Boolean), { x: col.x, y: ly + 0.3, w: col.w - 0.15, h: body.h - 0.8, name: `step ${i + 1}` }, { maxPt: ctx.scale.body - 1, minPt: ctx.scale.body_min, textOptions: { color: ctx.pal.ink_muted } });
    });
    return;
  }
  // numbered (기본): 큰 번호 + 제목 + 설명, 번호 사이 가는 연결선
  const numH = 0.9;
  steps.forEach((st, i) => {
    const col = cols[i];
    P.numeral(ctx, slide, numeralText(ctx, i + 1, ctx.tok.list.numbering[0] === '01' ? 'pad' : 'plain'), { x: col.x, y: body.y, w: col.w, h: numH }, { pt: Math.round(ctx.scale.hero_number * 0.55), color: i === n - 1 ? ctx.pal.accent : ctx.pal.primary });
    if (i < n - 1) P.arrow(ctx, slide, col.x + col.w - 0.35, body.y + numH * 0.45, col.x + col.w + 0.22, body.y + numH * 0.45, { color: ctx.pal.line, width: 1 });
    P.headingDetail(ctx, slide, st.title, [st.detail, st.owner ? `담당: ${st.owner}` : null].filter(Boolean), { x: col.x, y: body.y + numH + 0.05, w: col.w - 0.15, h: body.h - numH - 0.05, name: `step ${i + 1}` }, { headingPt: ctx.scale.body + 1, detailPt: ctx.scale.body - 1 });
  });
}

// ---------------------------------------------------------------- roadmap
function roadmap(ctx, slide, s, body) {
  const k = c(s);
  const phases = (k.phases || []).slice(0, 5);
  const n = phases.length || 1;
  const cols = columns(body, n, 0.18);
  const headH = 0.78;
  // 열 간 마일스톤 정렬용: 가장 긴 항목 높이
  roadmap._maxItemsH = Math.max(0, ...phases.map((ph) => Math.min(body.h - headH - 0.25 - (ph.milestone ? 0.62 : 0), (ph.items || []).length ? heightFor(ph.items, cols[0].w - 0.4, ctx.scale.body - 1, Object.assign({ lineHeight: ctx.tok.typography.line_height.body, paraGapEm: 0.35 }, B(ctx))) + 0.1 : 0)));
  phases.forEach((ph, i) => {
    const col = cols[i];
    const first = i === 0;
    P.rect(ctx, slide, { x: col.x, y: col.y, w: col.w, h: headH }, { fill: first ? ctx.pal.primary : ctx.pal.primary_soft, radius: 0 });
    P.ctxText(ctx, slide, ph.name, { x: col.x + 0.15, y: col.y + 0.08, w: col.w - 0.3, h: 0.36, fontSize: ctx.scale.body + 1, bold: true, color: first ? ctx.pal.on_primary : ctx.pal.primary, fontFace: ctx.font.display });
    if (ph.period) P.ctxText(ctx, slide, ph.period, { x: col.x + 0.15, y: col.y + 0.42, w: col.w - 0.3, h: 0.3, fontSize: ctx.scale.caption, color: first ? ctx.pal.on_primary : ctx.pal.ink_muted });
    const msH = ph.milestone ? 0.62 : 0;
    const items = ph.items || [];
    const availH = col.h - headH - 0.25 - msH;
    const itemsH = items.length ? Math.min(availH, heightFor(items, col.w - 0.4, ctx.scale.body - 1, Object.assign({ lineHeight: ctx.tok.typography.line_height.body, paraGapEm: 0.35 }, B(ctx))) + 0.1) : 0;
    if (items.length) P.bulletList(ctx, slide, items, { x: col.x + 0.05, y: col.y + headH + 0.2, w: col.w - 0.1, h: itemsH, name: `phase ${i + 1}` }, { maxPt: ctx.scale.body - 1, minPt: ctx.scale.body_min, paraGapEm: 0.35 });
    if (ph.milestone) {
      // 마일스톤은 항목 바로 아래(내용 기준)에 두되, 열 간 높이를 맞추기 위해 가장 긴 열 기준으로 정렬한다
      const my = col.y + headH + 0.2 + (roadmap._maxItemsH || itemsH) + 0.45;
      P.hline(ctx, slide, col.x, my, col.w, { color: ctx.pal.accent, width: 1.5 });
      slide.addShape(ctx.pres.ShapeType.diamond, { x: col.x, y: my - 0.08, w: 0.16, h: 0.16, fill: { color: ctx.pal.accent }, line: { type: 'none' } });
      P.fitBox(ctx, slide, [ph.milestone], { x: col.x + 0.22, y: my + 0.06, w: col.w - 0.22, h: msH - 0.1, name: 'milestone' }, { maxPt: ctx.scale.caption + 1, minPt: ctx.scale.caption - 1, textOptions: { color: ctx.pal.ink, bold: true } });
    }
  });
  if (k.horizon) P.label(ctx, slide, k.horizon, { x: body.x, y: body.y - 0.26, w: body.w, h: 0.22 }, { align: 'right', bold: false });
}

// ---------------------------------------------------------------- architecture
function architecture(ctx, slide, s, body) {
  const k = c(s);
  const layers = (k.layers || []).slice(0, 6);
  const flows = k.flows || [];
  const flowW = flows.length ? body.w * 0.26 : 0;
  const diag = { x: body.x, y: body.y, w: body.w - (flowW ? flowW + 0.4 : 0), h: body.h - (k.legend ? 0.35 : 0) };
  const n = layers.length || 1;
  const gap = 0.12;
  const rowH = (diag.h - gap * (n - 1)) / n;
  const nameW = Math.min(2.2, diag.w * 0.22);
  layers.forEach((ly, i) => {
    const y = diag.y + i * (rowH + gap);
    const tone = ly.tone || (i === 0 ? 'primary' : 'neutral');
    const fill = tone === 'primary' ? ctx.pal.primary : tone === 'accent' ? ctx.pal.accent : ctx.pal.surface_strong;
    const fg = tone === 'neutral' ? ctx.pal.ink : ctx.pal.on_primary;
    P.rect(ctx, slide, { x: diag.x, y, w: nameW, h: rowH }, { fill, radius: 0 });
    P.ctxText(ctx, slide, ly.name, { x: diag.x + 0.12, y, w: nameW - 0.24, h: rowH, fontSize: ctx.scale.body, bold: true, color: fg, valign: 'middle', fontFace: ctx.font.display });
    const comps = (ly.components || []).slice(0, 6);
    const m = comps.length || 1;
    const cgap = 0.1;
    const cw = (diag.w - nameW - 0.15 - cgap * (m - 1)) / m;
    comps.forEach((co, j) => {
      const cx = diag.x + nameW + 0.15 + j * (cw + cgap);
      P.rect(ctx, slide, { x: cx, y, w: cw, h: rowH }, { fill: ctx.pal.background, line: ctx.pal.line, lineWidth: 0.75, radius: 0 });
      const paras = [co.name, co.note].filter(Boolean);
      P.fitBox(ctx, slide, paras, { x: cx + 0.08, y: y + 0.05, w: cw - 0.16, h: rowH - 0.1, name: `${ly.name}/${co.name}` }, { maxPt: ctx.scale.body - 1, minPt: ctx.scale.body_min - 1, paraGapEm: 0.15, textOptions: { valign: 'middle', align: 'center' }, runOptions: (idx) => ({ bold: idx === 0, color: idx === 0 ? ctx.pal.ink : ctx.pal.ink_muted, fontSize: idx === 0 ? undefined : ctx.scale.caption }) });
    });
  });
  if (flows.length) {
    const fx = body.x + diag.w + 0.4;
    P.label(ctx, slide, '흐름 · 설명', { x: fx, y: body.y, w: flowW, h: 0.24 });
    P.bulletList(ctx, slide, flows, { x: fx, y: body.y + 0.32, w: flowW, h: body.h - 0.35, name: 'flows' }, { maxPt: ctx.scale.body - 1, minPt: ctx.scale.body_min, color: ctx.pal.ink_muted });
  }
  if (k.legend) P.ctxText(ctx, slide, k.legend, { x: body.x, y: body.y + body.h - 0.28, w: diag.w, h: 0.26, fontSize: ctx.scale.caption, color: ctx.pal.ink_faint });
}

// ---------------------------------------------------------------- matrix
function matrix(ctx, slide, s, body) {
  const k = c(s);
  const size = Math.min(body.h - 0.5, body.w * 0.5);
  const plot = { x: body.x + 0.9, y: body.y + 0.1, w: size, h: size - 0.2 };
  const q = k.quadrants || [];
  // 사분면 배경
  const halfW = plot.w / 2, halfH = plot.h / 2;
  [[0, 0], [1, 0], [0, 1], [1, 1]].forEach(([cx, cy], i) => {
    P.rect(ctx, slide, { x: plot.x + cx * halfW, y: plot.y + cy * halfH, w: halfW, h: halfH }, { fill: (cx === 1 && cy === 0) ? ctx.pal.primary_soft : ctx.pal.surface, line: ctx.pal.background, lineWidth: 2, radius: 0 });
    if (q[i]) P.label(ctx, slide, q[i], { x: plot.x + cx * halfW + 0.1, y: plot.y + cy * halfH + 0.06, w: halfW - 0.2, h: 0.22 }, { color: ctx.pal.ink_faint, spacing: 0, bold: true });
  });
  // 축 라벨
  const xa = k.x_axis || {}, ya = k.y_axis || {};
  P.ctxText(ctx, slide, xa.label || '', { x: plot.x, y: plot.y + plot.h + 0.22, w: plot.w, h: 0.26, fontSize: ctx.scale.caption + 1, bold: true, color: ctx.pal.ink, align: 'center' });
  P.ctxText(ctx, slide, xa.low || '', { x: plot.x, y: plot.y + plot.h + 0.02, w: plot.w / 2, h: 0.22, fontSize: ctx.scale.caption, color: ctx.pal.ink_faint, align: 'left' });
  P.ctxText(ctx, slide, xa.high || '', { x: plot.x + plot.w / 2, y: plot.y + plot.h + 0.02, w: plot.w / 2, h: 0.22, fontSize: ctx.scale.caption, color: ctx.pal.ink_faint, align: 'right' });
  // y축 라벨은 270도 회전 (가로 폭 plot.h 를 회전시키므로 상자는 중앙 기준으로 배치)
  const yl = 0.3;
  P.ctxText(ctx, slide, ya.label || '', { x: plot.x - 0.95 - plot.h / 2 + yl / 2, y: plot.y + plot.h / 2 - yl / 2, w: plot.h, h: yl, rotate: 270, fontSize: ctx.scale.caption + 1, bold: true, color: ctx.pal.ink, align: 'center', valign: 'middle' });
  P.ctxText(ctx, slide, ya.high || '', { x: plot.x - 0.62, y: plot.y, w: 0.56, h: 0.24, fontSize: ctx.scale.caption, color: ctx.pal.ink_faint, align: 'right' });
  P.ctxText(ctx, slide, ya.low || '', { x: plot.x - 0.62, y: plot.y + plot.h - 0.24, w: 0.56, h: 0.24, fontSize: ctx.scale.caption, color: ctx.pal.ink_faint, align: 'right', valign: 'bottom' });
  // 항목
  (k.items || []).slice(0, 12).forEach((it) => {
    const x = plot.x + clamp(Number(it.x), 0, 1) * plot.w;
    const y = plot.y + (1 - clamp(Number(it.y), 0, 1)) * plot.h;
    const d = it.emphasis ? 0.26 : 0.18;
    slide.addShape(ctx.pres.ShapeType.ellipse, { x: x - d / 2, y: y - d / 2, w: d, h: d, fill: { color: it.emphasis ? ctx.pal.accent : ctx.pal.primary }, line: { color: ctx.pal.background, width: 1.5 } });
    const lw = 1.6;
    const lx = x + d / 2 + 0.06 + lw > plot.x + plot.w ? x - d / 2 - 0.06 - lw : x + d / 2 + 0.06;
    P.ctxText(ctx, slide, it.label, { x: lx, y: y - 0.15, w: lw, h: 0.3, fontSize: ctx.scale.caption + (it.emphasis ? 1 : 0), bold: !!it.emphasis, color: ctx.pal.ink, valign: 'middle', align: lx < x ? 'right' : 'left' });
  });
  // 시사점
  const rx = plot.x + plot.w + 0.6;
  if (k.implication) P.callout(ctx, slide, k.implication, { x: rx, y: body.y + 0.1, w: body.x + body.w - rx, h: body.h - 0.4 }, { maxPt: ctx.scale.body + 1, minPt: ctx.scale.body_min, bold: true });
}

// ---------------------------------------------------------------- case_study
function case_study(ctx, slide, s, body) {
  const k = c(s);
  const blocks = [['상황', k.context], ['개입', k.intervention], ['결과', k.result]];
  const evH = k.evidence ? 0.7 : 0;
  if (k.image) {
    const iw = body.w * 0.38;
    P.image(ctx, slide, k.image, { x: body.x, y: body.y, w: iw, h: body.h });
    const rx = body.x + iw + 0.45, rw = body.w - iw - 0.45;
    const bh = (body.h - evH - 0.3) / 3;
    blocks.forEach(([h, t], i) => {
      const y = body.y + i * (bh + 0.1);
      P.label(ctx, slide, h, { x: rx, y, w: rw, h: 0.22 }, { color: i === 2 ? ctx.pal.accent : ctx.pal.primary });
      P.fitBox(ctx, slide, [t || ''], { x: rx, y: y + 0.26, w: rw, h: bh - 0.3, name: h }, { maxPt: ctx.scale.body, minPt: ctx.scale.body_min, textOptions: { bold: i === 2 } });
    });
    if (k.evidence) P.callout(ctx, slide, k.evidence, { x: rx, y: body.y + body.h - evH + 0.05, w: rw, h: evH - 0.05 }, { maxPt: ctx.scale.body, minPt: ctx.scale.body_min });
    return;
  }
  const cols = columns({ x: body.x, y: body.y, w: body.w, h: body.h - evH - 0.2 }, 3, 0.4);
  blocks.forEach(([h, t], i) => {
    const col = cols[i];
    if (i === 2) P.rect(ctx, slide, { x: col.x - 0.15, y: col.y - 0.1, w: col.w + 0.3, h: col.h + 0.2 }, { fill: ctx.pal.primary_soft, radius: 0 });
    P.label(ctx, slide, h, { x: col.x, y: col.y, w: col.w, h: 0.24 }, { color: ctx.pal.primary });
    P.hline(ctx, slide, col.x, col.y + 0.3, col.w, { color: i === 2 ? ctx.pal.primary : ctx.pal.line });
    P.fitBox(ctx, slide, [t || ''], { x: col.x, y: col.y + 0.42, w: col.w, h: col.h - 0.45, name: h }, { maxPt: ctx.scale.body, minPt: ctx.scale.body_min, textOptions: { bold: i === 2, color: ctx.pal.ink } });
    if (i < 2) P.arrow(ctx, slide, col.x + col.w + 0.05, col.y + col.h / 2, col.x + col.w + 0.35, col.y + col.h / 2, { color: ctx.pal.line });
  });
  if (k.evidence) P.callout(ctx, slide, k.evidence, { x: body.x, y: body.y + body.h - evH + 0.05, w: body.w, h: evH - 0.05 }, { maxPt: ctx.scale.body, minPt: ctx.scale.body_min });
  if (k.client) P.label(ctx, slide, k.client, { x: body.x, y: body.y - 0.26, w: body.w, h: 0.22 }, { align: 'right', bold: false });
}

// ---------------------------------------------------------------- recommendation
function recommendation(ctx, slide, s, body) {
  const k = c(s);
  const reasons = (k.reasons || []).slice(0, 4);
  const topH = 1.0;
  const nextH = k.next_action ? 0.95 : 0;
  P.callout(ctx, slide, k.recommendation || s.takeaway || '', { x: body.x, y: body.y, w: body.w, h: topH }, { maxPt: ctx.scale.body + 5, minPt: ctx.scale.body, bold: true, color: ctx.pal.primary });
  const midY = body.y + topH + 0.35;
  const midH = body.h - topH - 0.35 - (nextH ? nextH + 0.3 : 0);
  const cols = columns({ x: body.x, y: midY, w: body.w, h: midH }, reasons.length || 1, 0.4);
  reasons.forEach((r, i) => {
    const col = cols[i];
    if (i > 0) P.vline(ctx, slide, col.x - 0.2, col.y, col.h, { color: ctx.pal.line_faint });
    P.numeral(ctx, slide, numeralText(ctx, i + 1, ctx.tok.list.numbering[0] === '01' ? 'pad' : 'plain'), { x: col.x, y: col.y, w: col.w, h: 0.55 }, { pt: Math.round(ctx.scale.title * 0.9) });
    P.headingDetail(ctx, slide, r.heading, r.detail, { x: col.x, y: col.y + 0.62, w: col.w, h: col.h - 0.62, name: `reason ${i + 1}` }, { headingPt: ctx.scale.body + 1, detailPt: ctx.scale.body - 1 });
  });
  if (k.next_action) {
    const ny = body.y + body.h - nextH;
    P.rect(ctx, slide, { x: body.x, y: ny, w: body.w, h: nextH }, { fill: ctx.pal.primary_soft, radius: 0 });
    P.label(ctx, slide, '다음 단계', { x: body.x + 0.2, y: ny + 0.1, w: 1.5, h: 0.24 }, { color: ctx.pal.primary });
    const meta = [k.owner ? `담당 ${k.owner}` : null, k.timing ? `시점 ${k.timing}` : null].filter(Boolean).join('  ·  ');
    if (meta) P.ctxText(ctx, slide, meta, { x: body.x + body.w - 4.2, y: ny + 0.1, w: 4.0, h: 0.24, fontSize: ctx.scale.caption, color: ctx.pal.ink_muted, align: 'right' });
    P.fitBox(ctx, slide, [k.next_action], { x: body.x + 0.2, y: ny + 0.38, w: body.w - 0.4, h: nextH - 0.45, name: 'next action' }, { maxPt: ctx.scale.body + 1, minPt: ctx.scale.body_min, textOptions: { bold: true } });
  }
}

// ---------------------------------------------------------------- points
function points(ctx, slide, s, body) {
  const k = c(s);
  const pts = (k.points || []).slice(0, 4);
  const layout = k.layout || (pts.length >= 3 ? 'columns' : 'rows');
  if (layout === 'columns') {
    const cols = columns(body, pts.length || 1, 0.45);
    pts.forEach((p, i) => {
      const col = cols[i];
      if (i > 0) P.vline(ctx, slide, col.x - 0.22, col.y, col.h, { color: ctx.pal.line_faint });
      let y = col.y;
      if (p.metric) { P.bigNumber(ctx, slide, p.metric, '', { x: col.x, y, w: col.w, h: 0.9 }, { pt: Math.round(ctx.scale.hero_number * 0.5), valign: 'bottom' }); y += 1.0; }
      else { P.numeral(ctx, slide, numeralText(ctx, i + 1, ctx.tok.list.numbering[0] === '01' ? 'pad' : 'plain'), { x: col.x, y, w: col.w, h: 0.6 }, { pt: Math.round(ctx.scale.title * 1.0) }); y += 0.68; }
      P.headingDetail(ctx, slide, p.heading, p.detail, { x: col.x, y, w: col.w, h: col.y + col.h - y, name: `point ${i + 1}` }, { headingPt: ctx.scale.body + 2, detailPt: ctx.scale.body - 1 });
    });
    return;
  }
  const n = pts.length || 1;
  const gap = 0.18;
  const rowH = (body.h - gap * (n - 1)) / n;
  pts.forEach((p, i) => {
    const y = body.y + i * (rowH + gap);
    P.numeral(ctx, slide, numeralText(ctx, i + 1, ctx.tok.list.numbering[0] === '01' ? 'pad' : 'plain'), { x: body.x, y, w: 0.9, h: rowH }, { pt: Math.round(ctx.scale.title * 1.1) });
    const metricW = p.metric ? 2.6 : 0;
    P.headingDetail(ctx, slide, p.heading, p.detail, { x: body.x + 1.0, y: y + 0.02, w: body.w - 1.0 - metricW, h: rowH - 0.04, name: `point ${i + 1}` }, { headingPt: ctx.scale.body + 2, detailPt: ctx.scale.body - 1 });
    if (p.metric) P.bigNumber(ctx, slide, p.metric, '', { x: body.x + body.w - metricW, y, w: metricW, h: rowH }, { pt: Math.round(ctx.scale.hero_number * 0.5), valign: 'middle', align: 'right' });
    if (i < n - 1) P.hline(ctx, slide, body.x + 1.0, y + rowH + gap / 2, body.w - 1.0, { color: ctx.pal.line_faint });
  });
}

// ---------------------------------------------------------------- statement
function statement(ctx, slide, s, body) {
  const tok = ctx.tok, W = tok.canvas.width, H = tok.canvas.height, M = tok.canvas.margin;
  const k = c(s);
  if (k.image) P.image(ctx, slide, k.image, { x: 0, y: 0, w: W, h: H }, { scrim: true });
  const tw = W - 2 * M.left - 0.8;
  const fit = fitText([k.statement || s.title], tw, 3.0, ctx.scale.section_title, ctx.scale.title, Object.assign({ lineHeight: 1.25 }, D(ctx)));
  P.ctxText(ctx, slide, k.statement || s.title, { x: M.left + 0.4, y: (H - Math.min(3.0, fit.needIn)) / 2 - 0.3, w: tw, h: Math.min(3.0, fit.needIn) + 0.2, fontSize: fit.pt, bold: true, color: ctx.pal.ink, fontFace: ctx.font.display, valign: 'middle', lineSpacingMultiple: spacingMultiple(1.25, ctx.font.display, true) });
  if (k.attribution) P.ctxText(ctx, slide, `— ${k.attribution}`, { x: M.left + 0.4, y: (H + Math.min(3.0, fit.needIn)) / 2 + 0.1, w: tw, h: 0.4, fontSize: ctx.scale.body, color: ctx.pal.ink_muted });
}

// ---------------------------------------------------------------- data_table
function data_table(ctx, slide, s, body) {
  const k = c(s);
  if (k.unit) P.label(ctx, slide, `단위: ${k.unit}`, { x: body.x, y: body.y - 0.26, w: body.w, h: 0.22 }, { align: 'right', bold: false });
  P.table(ctx, slide, k.columns || [], k.rows || [], body, { highlightRows: k.highlight_rows || [], align: k.align, boldFirstCol: true });
}

// ---------------------------------------------------------------- image_focus
function image_focus(ctx, slide, s, body) {
  const tok = ctx.tok, W = tok.canvas.width, H = tok.canvas.height;
  const k = c(s);
  const layout = k.layout || 'image-right';
  if (layout === 'full-bleed') {
    P.image(ctx, slide, k.image, { x: 0, y: 0, w: W, h: H }, { scrim: true });
    // 제목은 프레임이 이미 그렸으므로(밝은 글자 필요) 캡션만 하단에
    P.rect(ctx, slide, { x: body.x - 0.2, y: body.y + body.h - 1.1, w: body.w * 0.6, h: 1.0 }, { fill: { color: tok.imagery.scrim, transparency: 20 }, radius: 0 });
    P.fitBox(ctx, slide, [k.caption], { x: body.x, y: body.y + body.h - 1.0, w: body.w * 0.6 - 0.4, h: 0.85, name: 'caption' }, { maxPt: ctx.scale.body + 1, minPt: ctx.scale.body_min, textOptions: { color: 'FFFFFF', bold: true, valign: 'middle' } });
    return;
  }
  const iw = body.w * 0.52;
  const imgBox = { x: layout === 'image-left' ? body.x : body.x + body.w - iw, y: body.y, w: iw, h: body.h };
  const tx = layout === 'image-left' ? body.x + iw + 0.5 : body.x;
  const tw = body.w - iw - 0.5;
  P.image(ctx, slide, k.image, imgBox);
  let y = body.y;
  if (k.caption) {
    const h = Math.min(body.h * 0.45, heightFor([k.caption], tw, ctx.scale.body + 2, Object.assign({ lineHeight: ctx.tok.typography.line_height.body }, B(ctx), { bold: true })) + 0.1);
    P.fitBox(ctx, slide, [k.caption], { x: tx, y, w: tw, h, name: 'caption' }, { maxPt: ctx.scale.body + 2, minPt: ctx.scale.body, textOptions: { bold: true } });
    y += h + 0.25;
  }
  if ((k.points || []).length) P.bulletList(ctx, slide, k.points.slice(0, 3), { x: tx, y, w: tw, h: body.y + body.h - y, name: 'points' }, { color: ctx.pal.ink_muted });
}

// ---------------------------------------------------------------- team
function team(ctx, slide, s, body) {
  const k = c(s);
  const members = (k.members || []).slice(0, 6);
  const cols = members.length > 3 ? columns(body, 2, 0.6) : [body];
  const per = Math.ceil(members.length / cols.length);
  const rowH = (body.h - 0.15 * (per - 1)) / per;
  members.forEach((m, i) => {
    const col = cols[Math.floor(i / per)];
    const y = col.y + (i % per) * (rowH + 0.15);
    P.ctxText(ctx, slide, [{ text: m.name || '', options: { bold: true, fontSize: ctx.scale.body + 1, color: ctx.pal.ink, fontFace: ctx.font.display } }, { text: m.role ? `  ${m.role}` : '', options: { fontSize: ctx.scale.body - 1, color: ctx.pal.primary, bold: true } }], { x: col.x, y, w: col.w, h: 0.36, fontSize: ctx.scale.body });
    P.fitBox(ctx, slide, [m.responsibility, m.proof].filter(Boolean), { x: col.x, y: y + 0.4, w: col.w, h: rowH - 0.45, name: m.name }, { maxPt: ctx.scale.body - 1, minPt: ctx.scale.body_min, paraGapEm: 0.2, runOptions: (idx) => ({ color: idx === 0 ? ctx.pal.ink : ctx.pal.ink_muted }) });
    if (i % per < per - 1) P.hline(ctx, slide, col.x, y + rowH + 0.07, col.w, { color: ctx.pal.line_faint });
  });
}

// ---------------------------------------------------------------- pricing_or_budget
function pricing_or_budget(ctx, slide, s, body) {
  const k = c(s);
  const items = (k.items || []).slice(0, 8);
  const lw = body.w * 0.56;
  const rows = items.map((it) => [it.label, it.amount, it.note || '']);
  if (k.total) rows.push(['합계', k.total, '']);
  const hasNote = items.some((it) => it.note);
  const cols = hasNote ? ['항목', `금액${k.unit ? ` (${k.unit})` : ''}`, '비고'] : ['항목', `금액${k.unit ? ` (${k.unit})` : ''}`];
  P.table(ctx, slide, cols, hasNote ? rows : rows.map((r) => r.slice(0, 2)), { x: body.x, y: body.y, w: lw, h: body.h }, { highlightRows: k.total ? [rows.length - 1] : [], boldFirstCol: false, colW: hasNote ? [lw * 0.42, lw * 0.26, lw * 0.32] : [lw * 0.6, lw * 0.4] });
  const rx = body.x + lw + 0.5, rw = body.w - lw - 0.5;
  let y = body.y;
  if ((k.assumptions || []).length) {
    P.label(ctx, slide, '가정', { x: rx, y, w: rw, h: 0.24 }, { color: ctx.pal.primary });
    const h = Math.min(body.h * 0.6, heightFor(k.assumptions, rw - 0.3, ctx.scale.body - 1, Object.assign({ lineHeight: ctx.tok.typography.line_height.body, paraGapEm: 0.4 }, B(ctx))) + 0.15);
    P.bulletList(ctx, slide, k.assumptions, { x: rx, y: y + 0.3, w: rw, h, name: 'assumptions' }, { maxPt: ctx.scale.body - 1, minPt: ctx.scale.body_min });
    y += h + 0.5;
  }
  if ((k.exclusions || []).length) {
    P.label(ctx, slide, '제외 범위', { x: rx, y, w: rw, h: 0.24 }, { color: ctx.pal.ink_muted });
    P.bulletList(ctx, slide, k.exclusions, { x: rx, y: y + 0.3, w: rw, h: body.y + body.h - y - 0.3, name: 'exclusions' }, { maxPt: ctx.scale.body - 1, minPt: ctx.scale.body_min, color: ctx.pal.ink_muted });
  }
}

// ---------------------------------------------------------------- conclusion
function conclusion(ctx, slide, s, body) {
  const k = c(s);
  const takeaways = (k.takeaways || []).slice(0, 3);
  const steps = (k.next_steps || []).slice(0, 4);
  const topH = 1.0;
  P.callout(ctx, slide, k.statement || s.takeaway || '', { x: body.x, y: body.y, w: body.w, h: topH }, { maxPt: ctx.scale.body + 5, minPt: ctx.scale.body, bold: true, color: ctx.pal.primary });
  let y = body.y + topH + 0.35;
  const stepsH = steps.length ? Math.min(2.2, 0.5 + steps.length * 0.42) : 0;
  const midH = body.h - topH - 0.35 - (stepsH ? stepsH + 0.3 : 0) - (k.contact ? 0.35 : 0);
  if (takeaways.length) {
    const cols = columns({ x: body.x, y, w: body.w, h: midH }, takeaways.length, 0.4);
    takeaways.forEach((t, i) => {
      const col = cols[i];
      if (i > 0) P.vline(ctx, slide, col.x - 0.2, col.y, col.h, { color: ctx.pal.line_faint });
      P.numeral(ctx, slide, numeralText(ctx, i + 1, ctx.tok.list.numbering[0] === '01' ? 'pad' : 'plain'), { x: col.x, y: col.y, w: col.w, h: 0.5 }, { pt: Math.round(ctx.scale.title * 0.85) });
      P.fitBox(ctx, slide, [t], { x: col.x, y: col.y + 0.55, w: col.w, h: col.h - 0.55, name: `takeaway ${i + 1}` }, { maxPt: ctx.scale.body, minPt: ctx.scale.body_min });
    });
    y += midH + 0.3;
  }
  if (steps.length) {
    P.label(ctx, slide, '다음 단계', { x: body.x, y, w: body.w, h: 0.24 }, { color: ctx.pal.primary });
    P.hline(ctx, slide, body.x, y + 0.3, body.w, { color: ctx.pal.ink, width: 1 });
    const rh = (stepsH - 0.4) / steps.length;
    steps.forEach((st, i) => {
      const sy = y + 0.38 + i * rh;
      P.ctxText(ctx, slide, st.label, { x: body.x, y: sy, w: body.w * 0.5, h: rh, fontSize: ctx.scale.body - 1, color: ctx.pal.ink, valign: 'middle' });
      P.ctxText(ctx, slide, st.owner || '', { x: body.x + body.w * 0.52, y: sy, w: body.w * 0.3, h: rh, fontSize: ctx.scale.body - 2, color: ctx.pal.ink_muted, valign: 'middle' });
      P.ctxText(ctx, slide, st.when || '', { x: body.x + body.w * 0.84, y: sy, w: body.w * 0.16, h: rh, fontSize: ctx.scale.body - 1, color: ctx.pal.ink_muted, valign: 'middle', align: 'right' });
      if (i < steps.length - 1) P.hline(ctx, slide, body.x, sy + rh, body.w, { color: ctx.pal.line_faint });
    });
  }
  if (k.contact) P.ctxText(ctx, slide, k.contact, { x: body.x, y: body.y + body.h - 0.3, w: body.w, h: 0.3, fontSize: ctx.scale.caption, color: ctx.pal.ink_muted, align: 'right', valign: 'bottom' });
}

// ---------------------------------------------------------------- appendix
function appendix(ctx, slide, s, body) {
  const k = c(s);
  let y = body.y;
  if ((k.paragraphs || []).length) {
    const h = k.table ? Math.min(body.h * 0.4, heightFor(k.paragraphs, body.w, ctx.scale.body - 1, Object.assign({ lineHeight: ctx.tok.typography.line_height.body }, B(ctx))) + 0.2) : body.h - ((k.items || []).length ? body.h * 0.45 : 0);
    P.fitBox(ctx, slide, k.paragraphs, { x: body.x, y, w: body.w, h, name: 'appendix text' }, { maxPt: ctx.scale.body - 1, minPt: ctx.scale.body_min - 1 });
    y += h + 0.2;
  }
  if (k.table && k.table.columns) {
    const h = body.y + body.h - y - ((k.items || []).length ? 1.2 : 0);
    P.table(ctx, slide, k.table.columns, k.table.rows || [], { x: body.x, y, w: body.w, h }, { boldFirstCol: false });
    y += h + 0.2;
  }
  if ((k.items || []).length) P.bulletList(ctx, slide, k.items, { x: body.x, y, w: body.w, h: body.y + body.h - y, name: 'appendix items' }, { maxPt: ctx.scale.body - 1, minPt: ctx.scale.body_min - 1 });
}

// ---------------------------------------------------------------- small_multiples
// 같은 축을 공유하는 작은 차트 격자 (≤6). 비교의 기준이 같아야 하므로 shared_y 기본 true.
function small_multiples(ctx, slide, s, body) {
  const k = c(s);
  const charts = (k.charts || []).slice(0, 6);
  if (!charts.length) { ctx.warn('small_multiples: charts 비어 있음', {}); return; }
  const n = charts.length;
  const ncol = k.columns || (n <= 2 ? n : n <= 4 ? 2 : 3);
  const nrow = Math.ceil(n / ncol);
  const noteH = k.note ? 0.45 : 0;
  const gapX = 0.4, gapY = 0.35, titleH = 0.3;
  const cw = (body.w - gapX * (ncol - 1)) / ncol;
  const ch = (body.h - noteH - gapY * (nrow - 1)) / nrow;
  let yMax = k.y_max;
  if (k.shared_y !== false && yMax == null) {
    let mx = 0;
    charts.forEach((m) => ((m.chart || {}).series || []).forEach((se) => se.values.forEach((v) => { if (v != null && Number(v) > mx) mx = Number(v); })));
    yMax = mx > 0 ? Math.ceil(mx * 1.15 * 10) / 10 : undefined;
  }
  const unit = (charts.find((m) => (m.chart || {}).unit) || { chart: {} }).chart.unit;
  if (unit) P.label(ctx, slide, `(단위: ${unit})`, { x: body.x, y: body.y - 0.26, w: body.w, h: 0.22 }, { align: 'right', bold: false, pt: Math.max(9, ctx.scale.caption - 1), spacing: 0 });
  charts.forEach((m, i) => {
    const col = i % ncol, row = Math.floor(i / ncol);
    const x = body.x + col * (cw + gapX), y = body.y + row * (ch + gapY);
    P.ctxText(ctx, slide, m.title || '', { x, y, w: cw, h: titleH, fontSize: ctx.scale.body, bold: true, color: ctx.pal.ink, fontFace: ctx.font.display, valign: 'middle' });
    const spec = Object.assign({}, m.chart || {}, { y_max: yMax, hide_value_axis: true, hide_unit: true, label_pt: Math.max(9, ctx.tok.chart.label_pt - 2) });
    buildChart(ctx, slide, spec, { x, y: y + titleH + 0.05, w: cw, h: ch - titleH - 0.05 });
  });
  if (k.note) P.fitBox(ctx, slide, [k.note], { x: body.x, y: body.y + body.h - noteH + 0.1, w: body.w, h: noteH - 0.1, name: 'note' }, { maxPt: ctx.scale.body - 1, minPt: ctx.scale.body_min, textOptions: { color: ctx.pal.ink_muted } });
}

// ---------------------------------------------------------------- big_number_stage
// 숫자 하나가 화면 절반 — 그 숫자가 왜 중요한지 오른쪽 한 문장
function big_number_stage(ctx, slide, s, body) {
  const k = c(s);
  if (k.value == null) { ctx.warn('big_number_stage: value 없음', {}); return; }
  const lw = body.w * 0.5;
  const pt = Math.round(ctx.scale.hero_number * 1.35);
  const numH = (pt * 1.05) / 72;
  const top = body.y + Math.max(0.1, (body.h - numH - 0.9) / 2);
  P.bigNumber(ctx, slide, k.value, k.unit, { x: body.x, y: top, w: lw, h: numH }, { pt, valign: 'bottom', color: k.trend === 'down' ? ctx.pal.negative : ctx.pal.primary });
  P.ctxText(ctx, slide, k.label || '', { x: body.x, y: top + numH + 0.1, w: lw, h: 0.45, fontSize: ctx.scale.body + 2, bold: true, color: ctx.pal.ink, fontFace: ctx.font.display });
  if (k.delta) P.ctxText(ctx, slide, k.delta, { x: body.x, y: top + numH + 0.58, w: lw, h: 0.35, fontSize: ctx.scale.body, color: k.trend === 'down' ? ctx.pal.negative : k.trend === 'up' ? ctx.pal.positive : ctx.pal.ink_muted, bold: true });
  const rx = body.x + lw + 0.6, rw = body.w - lw - 0.6;
  const paras = [k.context, k.comparison].filter(Boolean);
  if (paras.length) P.callout(ctx, slide, paras, { x: rx, y: body.y + body.h * 0.18, w: rw, h: body.h * 0.64 }, { maxPt: ctx.scale.body + 4, minPt: ctx.scale.body, bold: true, color: ctx.pal.accent, textColor: ctx.pal.ink, valign: 'middle' });
}

// ---------------------------------------------------------------- tam_nested
// 중첩 사각형 (TAM ⊃ SAM ⊃ SOM): 바깥에서 안으로 어두워진다. 오른쪽에 값·산출 방법·시사점
function tam_nested(ctx, slide, s, body) {
  const k = c(s);
  const rings = (k.rings || []).slice(0, 4);
  if (!rings.length) { ctx.warn('tam_nested: rings 비어 있음', {}); return; }
  const n = rings.length;
  const size = Math.min(body.h, body.w * 0.46);
  const ox = body.x, oy = body.y + (body.h - size) / 2;
  const fills = [ctx.pal.surface, ctx.pal.primary_soft, ctx.pal.primary, ctx.pal.accent];
  rings.forEach((r, i) => {
    const f = 1 - i * (0.72 / Math.max(1, n - 1)) * 0.95; // 1 → ~0.3
    const w = size * f, h = size * f;
    const x = ox, y = oy + size - h; // 왼쪽 아래 정렬
    const fill = fills[Math.min(i, fills.length - 1)];
    const dark = i >= 2;
    P.rect(ctx, slide, { x, y, w, h }, { fill, line: ctx.pal.background, lineWidth: 1.5, radius: 0 });
    const labelY = y + 0.08;
    // 안쪽 사각형은 좁다: 라벨+값 → 라벨만 → 생략 (값은 오른쪽 목록에 항상 있다)
    const full = `${r.label || ''}  ${r.value || ''}`;
    const wFull = textWidthIn(full, ctx.scale.body, ctx.font.numeral, true) + 0.1;
    const wLabel = textWidthIn(r.label || '', ctx.scale.body - 1, ctx.font.body, true) + 0.1;
    if (wFull <= w - 0.2) P.ctxText(ctx, slide, [{ text: r.label || '', options: { bold: true, fontSize: ctx.scale.body - 1, color: dark ? ctx.pal.on_primary : ctx.pal.ink } }, { text: r.value ? `  ${r.value}` : '', options: { bold: true, fontSize: ctx.scale.body + 1, color: dark ? ctx.pal.on_primary : ctx.pal.primary, fontFace: ctx.font.numeral } }], { x: x + 0.12, y: labelY, w: w - 0.2, h: 0.32, fontSize: ctx.scale.body, singleLine: true });
    else if (wLabel <= w - 0.2) P.ctxText(ctx, slide, r.label || '', { x: x + 0.12, y: labelY, w: w - 0.2, h: 0.32, fontSize: ctx.scale.body - 1, bold: true, color: dark ? ctx.pal.on_primary : ctx.pal.ink, singleLine: true });
  });
  const rx = body.x + size + 0.6, rw = body.w - size - 0.6;
  let y = body.y;
  rings.forEach((r, i) => {
    const rowH = 0.62;
    P.ctxText(ctx, slide, [{ text: r.label || '', options: { bold: true, color: ctx.pal.ink, fontSize: ctx.scale.body } }, { text: r.value ? `   ${r.value}` : '', options: { bold: true, color: ctx.pal.primary, fontSize: ctx.scale.body + 2, fontFace: ctx.font.numeral } }], { x: rx, y, w: rw, h: 0.32, fontSize: ctx.scale.body });
    if (r.note) P.ctxText(ctx, slide, r.note, { x: rx, y: y + 0.3, w: rw, h: 0.3, fontSize: Math.max(ctx.scale.body_min, ctx.scale.caption + 1), color: ctx.pal.ink_muted, singleLine: true });
    P.hline(ctx, slide, rx, y + rowH - 0.04, rw, { color: ctx.pal.line_faint });
    y += rowH;
  });
  if (k.method) {
    P.label(ctx, slide, '산출 방법', { x: rx, y: y + 0.1, w: rw, h: 0.22 });
    const avail = Math.max(0.4, body.y + body.h - (y + 0.36) - (k.implication ? 1.1 : 0.1));
    const mh = Math.min(avail, heightFor([k.method], rw, ctx.scale.body - 1, Object.assign({ lineHeight: ctx.tok.typography.line_height.body }, B(ctx))) + 0.1);
    P.fitBox(ctx, slide, [k.method], { x: rx, y: y + 0.36, w: rw, h: mh, name: 'method' }, { maxPt: ctx.scale.body - 1, minPt: ctx.scale.body_min, textOptions: { color: ctx.pal.ink_muted } });
  }
  if (k.implication) P.callout(ctx, slide, k.implication, { x: rx, y: body.y + body.h - 0.9, w: rw, h: 0.9 }, { maxPt: ctx.scale.body, minPt: ctx.scale.body_min, bold: true });
}

// ---------------------------------------------------------------- logo_wall
// 로고·레퍼런스 격자 (≤12). 셀 크기 동일, contain 배치, 테두리 없음. 로고는 승인 자산만.
function logo_wall(ctx, slide, s, body) {
  const k = c(s);
  const logos = (k.logos || []).slice(0, 12);
  if (!logos.length) { ctx.warn('logo_wall: logos 비어 있음', {}); return; }
  const n = logos.length;
  const ncol = k.columns || (n <= 4 ? n : n <= 8 ? 4 : 6);
  const nrow = Math.ceil(n / ncol);
  const capH = k.caption ? 0.5 : 0;
  const gap = 0.3;
  const cw = (body.w - gap * (ncol - 1)) / ncol;
  const ch = Math.min(1.6, (body.h - capH - gap * (nrow - 1)) / nrow);
  const top = body.y + Math.max(0, (body.h - capH - (ch * nrow + gap * (nrow - 1))) / 2);
  logos.forEach((id, i) => {
    const col = i % ncol, row = Math.floor(i / ncol);
    const box = { x: body.x + col * (cw + gap) + 0.15, y: top + row * (ch + gap) + 0.15, w: cw - 0.3, h: ch - 0.3 };
    const name = typeof id === 'string' ? id : id.image;
    const p = ctx.asset(name);
    if (p) slide.addImage({ path: p, x: box.x, y: box.y, w: box.w, h: box.h, sizing: { type: 'contain', w: box.w, h: box.h }, objectName: name });
    else { P.rect(ctx, slide, box, { fill: ctx.pal.surface, radius: 0 }); P.ctxText(ctx, slide, typeof id === 'string' ? id : (id.label || id.image), { x: box.x, y: box.y, w: box.w, h: box.h, fontSize: ctx.scale.caption, color: ctx.pal.ink_faint, align: 'center', valign: 'middle' }); ctx.warn(`로고 자산 '${name}' 없음 — 회색 자리표시`, {}); }
    if (typeof id === 'object' && id.label && p) P.ctxText(ctx, slide, id.label, { x: box.x, y: box.y + box.h - 0.02, w: box.w, h: 0.24, fontSize: ctx.scale.caption - 1, color: ctx.pal.ink_faint, align: 'center', singleLine: true });
  });
  if (k.caption) P.fitBox(ctx, slide, [k.caption], { x: body.x, y: body.y + body.h - capH + 0.1, w: body.w, h: capH - 0.1, name: 'caption' }, { maxPt: ctx.scale.body, minPt: ctx.scale.body_min, textOptions: { color: ctx.pal.ink_muted, align: 'center' } });
}

// ---------------------------------------------------------------- before_after
// 현재 → 이후. 왼쪽은 흐리게, 오른쪽은 주조 면. 숫자가 있으면 큰 숫자로 대비
function before_after(ctx, slide, s, body) {
  const k = c(s);
  const b = k.before || {}, a = k.after || {};
  const arrowW = 0.7;
  const cw = (body.w - arrowW) / 2;
  const L = { x: body.x, y: body.y, w: cw, h: body.h }, R = { x: body.x + cw + arrowW, y: body.y, w: cw, h: body.h };
  P.rect(ctx, slide, L, { fill: ctx.pal.surface, radius: 0 });
  P.rect(ctx, slide, R, { fill: ctx.pal.primary_soft, radius: 0 });
  const mid = body.y + body.h / 2;
  P.arrow(ctx, slide, body.x + cw + 0.12, mid, body.x + cw + arrowW - 0.12, mid, { color: ctx.pal.accent, width: 2 });
  if (k.arrow_label) P.ctxText(ctx, slide, k.arrow_label, { x: body.x + cw - 0.3, y: mid - 0.5, w: arrowW + 0.6, h: 0.3, fontSize: ctx.scale.caption, bold: true, color: ctx.pal.accent, align: 'center', singleLine: true });
  [[L, b, false], [R, a, true]].forEach(([box, side, after]) => {
    const pad = 0.3;
    let y = box.y + pad;
    P.label(ctx, slide, side.label || (after ? '이후' : '현재'), { x: box.x + pad, y, w: box.w - 2 * pad, h: 0.24 }, { color: after ? ctx.pal.primary : ctx.pal.ink_muted });
    y += 0.34;
    if (side.metric) {
      P.bigNumber(ctx, slide, side.metric, side.metric_unit || '', { x: box.x + pad, y, w: box.w - 2 * pad, h: 1.0 }, { pt: Math.round(ctx.scale.hero_number * 0.6), valign: 'bottom', color: after ? ctx.pal.primary : ctx.pal.ink_muted });
      y += 1.05;
      if (side.metric_label) { P.ctxText(ctx, slide, side.metric_label, { x: box.x + pad, y, w: box.w - 2 * pad, h: 0.3, fontSize: ctx.scale.caption + 1, color: ctx.pal.ink_muted }); y += 0.4; }
    }
    const pts = (side.points || []).slice(0, 4);
    if (pts.length) P.bulletList(ctx, slide, pts, { x: box.x + pad, y, w: box.w - 2 * pad, h: box.y + box.h - y - pad, name: after ? 'after' : 'before' }, { maxPt: ctx.scale.body, minPt: ctx.scale.body_min, color: after ? ctx.pal.ink : ctx.pal.ink_muted });
  });
}

// ---------------------------------------------------------------- kpi_bento
// 불균등 격자: 큰 숫자 하나(왼쪽 전체 높이) + 작은 셀 2~5개. 카드 테두리 없이 헤어라인으로만 나눈다
function kpi_bento(ctx, slide, s, body) {
  const k = c(s);
  const hero = k.hero;
  const cells = (k.cells || []).slice(0, 5);
  if (!hero && !cells.length) { ctx.warn('kpi_bento: hero/cells 없음', {}); return; }
  const noteH = k.note ? 0.5 : 0;
  const H = body.h - noteH;
  const heroW = hero ? body.w * 0.42 : 0;
  if (hero) {
    const pt = Math.round(ctx.scale.hero_number * 1.0);
    const numH = (pt * 1.05) / 72;
    const top = body.y + Math.max(0.2, (H - numH - 1.0) / 2);
    P.bigNumber(ctx, slide, hero.value, hero.unit, { x: body.x, y: top, w: heroW - 0.3, h: numH }, { pt, valign: 'bottom' });
    P.ctxText(ctx, slide, hero.label || '', { x: body.x, y: top + numH + 0.08, w: heroW - 0.3, h: 0.45, fontSize: ctx.scale.body + 1, bold: true, color: ctx.pal.ink });
    if (hero.delta) P.ctxText(ctx, slide, hero.delta, { x: body.x, y: top + numH + 0.55, w: heroW - 0.3, h: 0.35, fontSize: ctx.scale.body, color: hero.trend === 'down' ? ctx.pal.negative : hero.trend === 'up' ? ctx.pal.positive : ctx.pal.ink_muted, bold: true });
    P.vline(ctx, slide, body.x + heroW - 0.15, body.y + 0.1, H - 0.2, { color: ctx.pal.line });
  }
  const gx = body.x + heroW + (hero ? 0.3 : 0);
  const gw = body.w - heroW - (hero ? 0.3 : 0);
  const n = cells.length;
  const ncol = n <= 1 ? 1 : n <= 4 ? 2 : 3;
  const nrow = Math.ceil(n / ncol);
  const cw = gw / ncol, ch = H / Math.max(1, nrow);
  cells.forEach((m, i) => {
    const col = i % ncol, row = Math.floor(i / ncol);
    const x = gx + col * cw, y = body.y + row * ch;
    const pt = Math.round(ctx.scale.hero_number * (nrow >= 3 ? 0.42 : 0.55));
    const numH = (pt * 1.05) / 72;
    P.bigNumber(ctx, slide, m.value, m.unit, { x: x + 0.2, y: y + 0.15, w: cw - 0.4, h: numH }, { pt, valign: 'bottom', color: ctx.pal.ink });
    P.ctxText(ctx, slide, m.label || '', { x: x + 0.2, y: y + 0.2 + numH, w: cw - 0.4, h: 0.3, fontSize: ctx.scale.body - 1, bold: true, color: ctx.pal.ink });
    if (m.delta) P.ctxText(ctx, slide, m.delta, { x: x + 0.2, y: y + 0.5 + numH, w: cw - 0.4, h: 0.3, fontSize: ctx.scale.caption + 1, color: m.trend === 'down' ? ctx.pal.negative : m.trend === 'up' ? ctx.pal.positive : ctx.pal.ink_muted, bold: true });
    if (row < nrow - 1) P.hline(ctx, slide, x + 0.2, y + ch - 0.02, cw - 0.4, { color: ctx.pal.line_faint });
    if (col > 0) P.vline(ctx, slide, x, y + 0.15, ch - 0.3, { color: ctx.pal.line_faint });
  });
  if (k.note) P.fitBox(ctx, slide, [k.note], { x: body.x, y: body.y + body.h - noteH + 0.12, w: body.w, h: noteH - 0.12, name: 'note' }, { maxPt: ctx.scale.body - 1, minPt: ctx.scale.body_min, textOptions: { color: ctx.pal.ink_muted } });
}

function custom(ctx, slide, s, body) {
  const fn = ctx.hooks && (ctx.hooks[s.number] || ctx.hooks[String(s.number)]);
  if (!fn) { ctx.warn(`custom 슬라이드 ${s.number}: hooks 파일에 핸들러가 없음 — 빈 본문`, {}); return; }
}

module.exports = { cover, agenda, executive_summary, section_divider, hero_metric, evidence_chart, comparison, process, roadmap, architecture, matrix, case_study, recommendation, points, statement, data_table, image_focus, team, pricing_or_budget, conclusion, appendix, small_multiples, big_number_stage, tam_nested, logo_wall, before_after, kpi_bento, custom, columns };
