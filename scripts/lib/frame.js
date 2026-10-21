'use strict';
// 슬라이드 프레임: 마스터(배경·푸터·쪽번호), 킥커/트래커/빵부스러기, 액션 타이틀, 스티커, 본문 영역 계산,
// 제안서형 블록(요구·대응 / 검증·산출물 / 요구 ID 태그 / 요약 줄), 출처·노트.
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
  const base = Object.assign({ ink_strong: c.ink_strong || c.ink }, c);
  if (!c.ink_strong) base.ink_strong = c.ink;
  if (bg === 'dark') {
    return Object.assign({}, base, {
      background: c.dark_background, ink: c.on_dark, ink_strong: c.on_dark, ink_muted: 'C7D0D8', ink_faint: '94A3B3', line: '3A4A5A', line_faint: '2A3845',
      surface: shade(c.dark_background, 12), surface_strong: shade(c.dark_background, 22), primary: c.light_background ? c.primary : 'FFFFFF',
      primary_soft: shade(c.dark_background, 18), on_primary: c.dark_background, accent: c.accent, accent_soft: shade(c.dark_background, 18), dark: true,
    });
  }
  if (bg === 'surface') return Object.assign({}, base, { background: c.surface, surface: c.surface_strong, primary_soft: c.primary_soft });
  if (c.light_background && c.light_ink && bg === 'light' && c.background === c.dark_background) {
    // 키노트 프로파일은 기본이 어두움. 'light' 요청 시 밝은 팔레트
    return Object.assign({}, base, { background: c.light_background, ink: c.light_ink, ink_strong: c.light_ink, ink_muted: '5B6977', ink_faint: '8A97A4', line: 'D5DBE1', line_faint: 'E9EDF1', surface: 'F3F5F7', surface_strong: 'E6EAEE', primary: '0F4C81', primary_soft: 'DCE8F3', on_primary: 'FFFFFF' });
  }
  return base;
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

// 색 이름(토큰 키) 또는 hex → hex
function colorOf(pal, v, fallback) {
  if (!v) return fallback;
  if (/^[0-9A-Fa-f]{6}$/.test(v)) return v.toUpperCase();
  return pal[v] || fallback;
}

// 마스터 정의 — 배경별 1개. 푸터·쪽번호는 마스터에, 제목은 placeholder.
function defineMasters(ctx) {
  const tok = ctx.tok;
  const W = tok.canvas.width, H = tok.canvas.height;
  const M = tok.canvas.margin;
  const F = tok.footer;
  const FR = tok.frame || {};
  const meta = ctx.spec.metadata;
  const chipShift = tok.title.style === 'chip' ? 0.68 : 0;
  const footY = H - (F.bottom_inset || 0.42), footH = 0.28;
  for (const bg of ['light', 'dark', 'surface', 'cover_light', 'cover_dark']) {
    // cover_*: 표지 전용 — 푸터·쪽번호 없음
    const isCover = bg.startsWith('cover_');
    const pal = palette(tok, isCover ? bg.slice(6) : bg);
    const objects = [];
    if (isCover) {
      const def0 = { title: `TK_${bg.toUpperCase()}`, background: { color: pal.background }, objects: [] };
      ctx.pres.defineSlideMaster(def0);
      ctx.masters[bg] = { name: def0.title, titleY: M.top, titleH: 1, chipShift: 0, footY, footH, leftText: '' };
      continue;
    }
    const leftText = F.left === 'organization' ? (meta.organization || '') : F.left === 'document_title' ? (meta.title || '') : '';
    const footOpts = { fontSize: Math.max(8, ctx.scale.source - 1), color: colorOf(pal, F.color, pal.ink_faint), fontFace: ctx.font.body, margin: 0, valign: 'middle', lang: 'ko-KR' };
    // 태그 줄(요구 ID)을 쓰는 프레임은 왼쪽 푸터 글자를 슬라이드마다 그린다(태그와 겹치지 않게)
    if (leftText && !FR.tags) objects.push({ text: { text: leftText, options: Object.assign({ x: M.left, y: footY, w: W * 0.45, h: footH, align: 'left' }, footOpts) } });
    if (F.confidentiality && meta.confidentiality) objects.push({ text: { text: meta.confidentiality, options: Object.assign({ x: W * 0.35, y: footY, w: W * 0.3, h: footH, align: 'center' }, footOpts) } });
    const titleY = M.top + (tok.title.kicker !== 'none' ? 0.3 : 0);
    const maxLines = tok.title.max_lines || 2;
    const titleH = (maxLines * ctx.scale.title * tok.typography.line_height.title) / 72 + 0.08;
    objects.push({ placeholder: { options: { name: 'title', type: 'title', x: M.left + chipShift, y: titleY, w: W - M.left - M.right - chipShift - (meta.sticker ? 1.4 : 0), h: titleH, bold: tok.fonts.titleBold, color: pal.ink_strong, fontFace: ctx.font.display, margin: 0, valign: 'top', align: tok.title.align || 'left', lang: 'ko-KR' }, text: '' } });
    const def = { title: `TK_${bg.toUpperCase()}`, background: { color: pal.background }, objects };
    if (F.right === 'page_number') {
      const big = F.page_number_style === 'display';
      const pnPt = big ? Math.round(ctx.scale.title * 0.6) : Math.max(8, ctx.scale.source - 1);
      def.slideNumber = { x: W - M.right - 0.8, y: footY, w: 0.8, h: footH, fontSize: pnPt, bold: big, color: big ? pal.primary : colorOf(pal, F.color, pal.ink_faint), fontFace: big ? ctx.font.numeral : ctx.font.body, align: 'right', margin: 0, valign: 'middle' };
    }
    ctx.pres.defineSlideMaster(def);
    ctx.masters[bg] = { name: def.title, titleY, titleH, chipShift, footY, footH, leftText };
  }
}

// brief / verification 입력 정규화: {requirement, response} | {criteria, deliverables} | [{label, text, emphasis?}]
function briefRows(ctx, v) {
  if (!v) return [];
  const L = Object.assign({ requirement: '요구사항', response: '대응방안', criteria: '검증 기준', deliverables: '산출물' }, (ctx.tok.frame || {}).labels || {});
  if (Array.isArray(v)) return v.filter((r) => r && r.text).map((r) => ({ label: r.label || '', text: r.text, emphasis: !!r.emphasis, muted: !!r.muted }));
  const rows = [];
  if (v.requirement) rows.push({ label: L.requirement, text: v.requirement });
  if (v.response) rows.push({ label: L.response, text: v.response, emphasis: true });
  if (v.criteria) rows.push({ label: L.criteria, text: v.criteria });
  if (v.deliverables) rows.push({ label: L.deliverables, text: v.deliverables, muted: true });
  return rows;
}

// 슬라이드 시작: 배경·킥커·제목·스티커(·요구/대응 블록)를 그리고 본문 영역을 돌려준다
function begin(ctx, slideSpec, opts = {}) {
  const tok = ctx.tok;
  const FR = tok.frame || {};
  const W = tok.canvas.width, H = tok.canvas.height, M = tok.canvas.margin;
  const bg = defaultBackground(ctx, slideSpec);
  ctx.pal = palette(tok, bg);
  const master = slideSpec.archetype === 'cover' ? (ctx.masters[`cover_${bg === 'dark' ? 'dark' : 'light'}`] || ctx.masters[bg]) : ctx.masters[bg];
  const slide = ctx.pres.addSlide({ masterName: master.name, sectionTitle: ctx.currentSection || undefined });
  const isChrome = !['cover', 'section_divider', 'statement'].includes(slideSpec.archetype) && !opts.noChrome;
  const hasSource = !!(slideSpec.source_note && slideSpec.source_note.trim());
  const sourceH = 0.3;
  const footerY = master.footY;
  const frame = { left: M.left, right: W - M.right, width: W - M.left - M.right, top: M.top, H, W, sourceH, footerY, bottom: footerY - 0.04 };
  ctx.frame = frame;
  ctx.slide = slide;
  ctx.slideSpec = slideSpec;
  const body = { x: M.left, y: M.top, w: frame.width, h: 0 };
  if (!isChrome) {
    frame.sourceY = footerY - sourceH - 0.02;
    body.h = (hasSource ? frame.sourceY - 0.12 : footerY - 0.2) - M.top;
    return { slide, body, bg };
  }

  // 상단 괘선 (제안서형): 가는 선 + 왼쪽 짧은 주조색 구간
  if (FR.top_rule) {
    P.rect(ctx, slide, { x: M.left, y: 0.15, w: frame.width, h: 0.03 }, { fill: ctx.pal.line, radius: 0 });
    P.rect(ctx, slide, { x: M.left, y: 0.15, w: FR.top_rule_accent_w || 1.35, h: 0.03 }, { fill: ctx.pal.primary, radius: 0 });
  }
  // 킥커 / 트래커 / 빵부스러기 / exhibit
  const kickerY = M.top - 0.02;
  const kickerParts = [];
  if ((tok.title.kicker === 'section' || tok.title.kicker === 'tracker' || tok.title.kicker === 'breadcrumb') && slideSpec.section) kickerParts.push(slideSpec.section);
  if (slideSpec.kicker) kickerParts.push(slideSpec.kicker);
  if (tok.footer.exhibit_numbers && slideSpec.exhibit != null) kickerParts.unshift(typeof slideSpec.exhibit === 'number' ? `Exhibit ${slideSpec.exhibit}` : String(slideSpec.exhibit));
  if (tok.title.kicker !== 'none' && kickerParts.length) {
    if (tok.title.kicker === 'breadcrumb') P.label(ctx, slide, kickerParts.join('   /   '), { x: M.left, y: kickerY, w: frame.width - 1.6, h: 0.24 }, { color: ctx.pal.primary, spacing: 0 });
    else P.label(ctx, slide, kickerParts.join('  ·  '), { x: M.left, y: kickerY, w: frame.width - 1.6, h: 0.24 }, { color: ctx.pal.ink_muted });
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
  // 제목 (액션 타이틀) — max_lines 줄 안에 들어가도록 title pt에서 최대 6pt까지 축소
  const title = (slideSpec.title || '').trim();
  const titleW = W - M.left - M.right - master.chipShift - (sticker ? 1.5 : 0);
  const tlh = tok.typography.line_height.title;
  const maxLines = tok.title.max_lines || 2;
  const fit = fitText([title], titleW, master.titleH, ctx.scale.title, ctx.scale.title - 6, { lineHeight: tlh, paraGapEm: 0, face: ctx.font.display, bold: tok.fonts.titleBold });
  if (!fit.fits || fit.lines > maxLines) ctx.warn(`제목이 ${maxLines}줄을 넘음(추정 ${fit.lines}줄, ${fit.pt}pt): "${title.slice(0, 40)}…" — ${maxLines === 1 ? '28' : '45'}자 이내로 줄인다`, {});
  if (fit.pt < ctx.scale.title) ctx.info(`제목 ${ctx.scale.title}→${fit.pt}pt 축소 (${maxLines}줄 맞춤): "${title.slice(0, 30)}…"`);
  const trk = Math.round(fit.pt * (tok.typography.tracking_em.display || 0) * 10) / 10;
  slide.addText(title, Object.assign({ placeholder: 'title', fontSize: fit.pt, lineSpacingMultiple: spacingMultiple(tlh, ctx.font.display, tok.fonts.titleBold), lang: 'ko-KR' }, trk ? { charSpacing: trk } : {}));
  let bodyTop = master.titleY + master.titleH + (opts.bodyGap != null ? opts.bodyGap : 0.22);
  if (FR.title_rule) { P.hline(ctx, slide, M.left, master.titleY + master.titleH + 0.02, frame.width, { color: ctx.pal.line, width: 0.5 }); bodyTop = master.titleY + master.titleH + 0.1; }

  // 요구사항 / 대응방안 블록 (제안서형) — 본문 위
  const brief = briefRows(ctx, slideSpec.brief);
  if (brief.length) {
    const rowH = 0.34;
    const bh = brief.length * rowH + 0.08;
    const labelW = FR.label_w || 1.1;
    P.rect(ctx, slide, { x: M.left, y: bodyTop, w: frame.width, h: bh }, { fill: ctx.pal.surface, radius: 0 });
    P.rect(ctx, slide, { x: M.left, y: bodyTop, w: 0.03, h: bh }, { fill: ctx.pal.accent, radius: 0 });
    brief.forEach((r, i) => {
      const y = bodyTop + 0.04 + i * rowH;
      P.ctxText(ctx, slide, r.label, { x: M.left + 0.16, y, w: labelW - 0.16, h: rowH, fontSize: ctx.scale.kicker + 1, bold: true, color: ctx.pal.primary, valign: 'middle', singleLine: true });
      P.fitBox(ctx, slide, [r.text], { x: M.left + labelW + 0.1, y, w: frame.width - labelW - 0.3, h: rowH, name: `brief ${r.label}` }, { maxPt: r.emphasis ? ctx.scale.body : ctx.scale.body - 1, minPt: ctx.scale.body_min, lineHeight: 1.2, textOptions: { bold: r.emphasis, color: r.emphasis ? ctx.pal.ink_strong : ctx.pal.ink, valign: 'middle' } });
    });
    bodyTop += bh + 0.22;
  }

  // 아래쪽 한계: 검증·산출물 블록 → 출처 → 본문
  let bottom = footerY - 0.06;
  const ver = briefRows(ctx, slideSpec.verification);
  if (ver.length) {
    const rowH = 0.27;
    const vh = ver.length * rowH + 0.08;
    const vy = bottom - vh;
    frame.verification = { y: vy, h: vh, rows: ver };
    bottom = vy - 0.06;
  }
  // 검증 블록이 없으면 본문(>12pt)은 바닥 안전구역(0.5in) 밖에 둔다
  if (!ver.length) bottom = Math.min(bottom, H - 0.52);
  frame.sourceY = bottom - sourceH;
  if (hasSource) bottom = frame.sourceY - 0.08;
  // 요약 줄 (본문 아래, 검증 블록 위)
  if (slideSpec.summary && (slideSpec.summary.text || typeof slideSpec.summary === 'string')) {
    const sm = typeof slideSpec.summary === 'string' ? { text: slideSpec.summary } : slideSpec.summary;
    const sh = sm.style === 'band' ? 0.5 : 0.4;
    frame.summary = { y: bottom - sh, h: sh, spec: sm };
    bottom = bottom - sh - 0.14;
  }
  body.y = bodyTop;
  body.h = bottom - bodyTop;
  frame.bottom = bottom;
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

// 태그 입력 정규화: ["SFR-003", …] | {label:"RFP", ids:[…]} | "SFR-003 · SFR-004"
function tagParts(v) {
  if (!v) return null;
  if (typeof v === 'string') return { label: '', ids: [v] };
  if (Array.isArray(v)) return { label: '', ids: v.map(String) };
  return { label: v.label || '', ids: (v.ids || []).map(String) };
}

// 슬라이드 끝: 요약 줄·검증 블록·태그 줄·푸터 글자·출처·노트
function end(ctx, slideSpec) {
  const slide = ctx.slide;
  const tok = ctx.tok, FR = tok.frame || {}, M = tok.canvas.margin;
  const f = ctx.frame;
  const isChrome = !['cover', 'section_divider', 'statement'].includes(slideSpec.archetype);
  const master = ctx.masters[defaultBackground(ctx, slideSpec)] || {};
  if (isChrome && f.summary) {
    const sm = f.summary.spec;
    const labelW = sm.label ? Math.min(2.4, Math.max(1.2, sm.label.length * 0.2 + 0.4)) : 0;
    if (sm.style === 'band') {
      P.rect(ctx, slide, { x: f.left, y: f.summary.y, w: f.width, h: f.summary.h }, { fill: ctx.pal.surface, radius: 0 });
      if (sm.label) P.ctxText(ctx, slide, sm.label, { x: f.left + 0.25, y: f.summary.y, w: labelW, h: f.summary.h, fontSize: ctx.scale.body + 1, bold: true, color: ctx.pal.accent, valign: 'middle', fontFace: ctx.font.display, singleLine: true });
      P.fitBox(ctx, slide, [sm.text], { x: f.left + 0.25 + labelW + 0.2, y: f.summary.y, w: f.width - labelW - 0.7, h: f.summary.h, name: 'summary' }, { maxPt: ctx.scale.body + 1, minPt: ctx.scale.body_min, lineHeight: 1.2, textOptions: { bold: !sm.label, color: ctx.pal.ink_strong, valign: 'middle' } });
    } else {
      if (sm.label) P.ctxText(ctx, slide, sm.label, { x: f.left, y: f.summary.y, w: labelW, h: f.summary.h, fontSize: ctx.scale.body + 1, bold: true, color: ctx.pal.primary, valign: 'middle', fontFace: ctx.font.display, singleLine: true });
      P.fitBox(ctx, slide, [sm.text], { x: f.left + labelW + (labelW ? 0.2 : 0), y: f.summary.y, w: f.width - labelW - (labelW ? 0.2 : 0), h: f.summary.h, name: 'summary' }, { maxPt: ctx.scale.body + 1, minPt: ctx.scale.body_min, lineHeight: 1.2, textOptions: { bold: true, color: ctx.pal.ink_strong, valign: 'middle' } });
    }
  }
  if (isChrome && f.verification) {
    const v = f.verification;
    const labelW = FR.label_w || 1.1;
    P.hline(ctx, slide, f.left, v.y - 0.03, f.width, { color: ctx.pal.primary, width: 0.6 });
    P.rect(ctx, slide, { x: f.left, y: v.y, w: f.width, h: v.h }, { fill: ctx.pal.surface, radius: 0 });
    v.rows.forEach((r, i) => {
      const y = v.y + 0.04 + i * 0.27;
      P.ctxText(ctx, slide, r.label, { x: f.left + 0.16, y, w: labelW - 0.16, h: 0.27, fontSize: r.muted ? ctx.scale.kicker - 1 : ctx.scale.kicker, bold: true, color: r.muted ? ctx.pal.ink_muted : ctx.pal.primary, valign: 'middle', singleLine: true });
      P.fitBox(ctx, slide, [r.text], { x: f.left + labelW + 0.1, y, w: f.width - labelW - 0.3, h: 0.27, name: `verification ${r.label}` }, { maxPt: r.muted ? ctx.scale.caption : ctx.scale.caption + 1, minPt: Math.max(8, ctx.scale.source), lineHeight: 1.15, textOptions: { color: r.muted ? ctx.pal.ink_muted : ctx.pal.ink, valign: 'middle' } });
    });
  }
  // 푸터 줄: 태그(요구 ID) 띠 + 조견표 참조, 없으면 왼쪽 문서명 (마스터가 그리지 않은 경우)
  if (isChrome && FR.tags) {
    const tags = tagParts(slideSpec.tags);
    const footY = f.footerY, footH = master.footH || 0.28;
    const pnW = tok.footer.right === 'page_number' ? 0.9 : 0;
    if (tags && tags.ids.length) {
      const bandW = f.width * 0.74;
      P.rect(ctx, slide, { x: f.left, y: footY + 0.02, w: bandW, h: footH - 0.02 }, { fill: ctx.pal.surface_strong, radius: 0 });
      const runs = [];
      if (tags.label) runs.push({ text: `${tags.label}  `, options: { bold: true, color: ctx.pal.primary } });
      tags.ids.forEach((id, i) => {
        runs.push({ text: id, options: { bold: true, color: ctx.pal.primary, underline: { style: 'sng', color: ctx.pal.line } } });
        if (i < tags.ids.length - 1) runs.push({ text: '   ·   ', options: { color: ctx.pal.ink_faint } });
      });
      P.ctxText(ctx, slide, runs, { x: f.left + 0.12, y: footY + 0.02, w: bandW - 0.2, h: footH - 0.02, fontSize: ctx.scale.source, valign: 'middle', wrap: false });
      if (slideSpec.xref) P.ctxText(ctx, slide, slideSpec.xref, { x: f.left + bandW + 0.2, y: footY, w: f.width - bandW - 0.2 - pnW, h: footH, fontSize: ctx.scale.source, bold: true, color: ctx.pal.primary, align: 'right', valign: 'middle', singleLine: true });
    } else {
      P.hline(ctx, slide, f.left, footY - 0.08, f.width, { color: ctx.pal.line, width: 0.5 });
      const left = slideSpec.footer_left || master.leftText || '';
      if (left) P.ctxText(ctx, slide, left, { x: f.left, y: footY, w: f.width * 0.5, h: footH, fontSize: Math.max(8, ctx.scale.source - 1), color: colorOf(ctx.pal, tok.footer.color, ctx.pal.ink_faint), valign: 'middle', singleLine: true });
      if (slideSpec.xref) P.ctxText(ctx, slide, slideSpec.xref, { x: f.left + f.width * 0.5, y: footY, w: f.width * 0.5 - pnW, h: footH, fontSize: ctx.scale.source, bold: true, color: ctx.pal.primary, align: 'right', valign: 'middle', singleLine: true });
    }
  } else if (isChrome && FR.footer_rule) P.hline(ctx, slide, f.left, f.footerY - 0.08, f.width, { color: ctx.pal.line, width: 0.5 });
  if (slideSpec.source_note) P.sourceNote(ctx, slide, slideSpec.source_note);
  const notes = [];
  if (slideSpec.speaker_notes) notes.push(slideSpec.speaker_notes);
  else if (slideSpec.takeaway) notes.push(`요지: ${slideSpec.takeaway}`);
  if (notes.length) slide.addNotes(notes.join('\n'));
}

module.exports = { defineMasters, begin, end, palette, numeralText, ROMAN, colorOf, briefRows };
