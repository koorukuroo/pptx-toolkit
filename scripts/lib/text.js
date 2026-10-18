'use strict';
// 글자 폭 추정과 상자 맞춤 — core/inspect.py 의 estimate_lines 와 같은 알고리즘.
// 폭: 설치 폰트의 hmtx(fontmetrics.js). 폰트가 없으면 평균 계수(한글 1.0, 대문자 0.68, 숫자 0.58, 소문자 0.55, 공백 0.3).
// 줄바꿈: PowerPoint·LibreOffice 처럼 어절(공백) 단위. 한 어절이 상자보다 길면 글자 단위. 폭에 2% 안전 여유.
// 행간: lineHeight 는 '절대 em'(글자 크기 대비). PowerPoint의 spcPct 는 폰트 고유 행간(hhea/OS2)에 곱해지므로
//       spacingMultiple(lineHeight, face) = lineHeight / fontLineHeightEm 으로 환산해 쓴다.
const FM = require('./fontmetrics');

const SAFETY = 0.98;

function charEm(ch, face, bold) {
  return FM.widthEm(ch, face, !!bold);
}

function textWidthIn(text, pt, face, bold) {
  let em = 0;
  for (const ch of text) em += charEm(ch, face, bold);
  return (em * pt) / 72;
}

function baseLineHeight(face, bold) {
  return FM.lineHeightEm(face, !!bold);
}

// 원하는 절대 행간(em) → pptxgenjs lineSpacingMultiple
function spacingMultiple(lineHeightEm, face, bold) {
  return Math.round((lineHeightEm / baseLineHeight(face, bold)) * 1000) / 1000;
}

// 단락 하나를 폭 widthIn 에 흘렸을 때 줄 수 (어절 단위 줄바꿈)
function linesFor(text, pt, widthIn, opts = {}) {
  if (!text) return 1;
  const face = opts.face, bold = !!opts.bold;
  const emIn = pt / 72;
  const W = widthIn * SAFETY;
  if (W <= 0) return 1;
  const tokens = String(text).match(/\s+|\S+/gu) || [];
  let lines = 1;
  let w = 0;
  for (const tok of tokens) {
    let tw = 0;
    for (const ch of tok) tw += charEm(ch, face, bold) * emIn;
    if (/^\s+$/.test(tok)) { if (w > 0) w += tw; continue; }
    if (w + tw > W && w > 0) { lines += 1; w = 0; }
    if (tw > W) {
      for (const ch of tok) {
        const cw = charEm(ch, face, bold) * emIn;
        if (w + cw > W && w > 0) { lines += 1; w = 0; }
        w += cw;
      }
      continue;
    }
    w += tw;
  }
  return lines;
}

function _need(paras, pt, wIn, lh, paraGapEm, opts) {
  let lines = 0;
  for (const p of paras) lines += linesFor(p, pt, wIn, opts);
  return { lines, need: (lines * pt * lh + Math.max(0, paras.length - 1) * pt * paraGapEm) / 72 };
}

// paragraphs: string[] — 상자(w,h)에 들어가는 최대 글자 크기 (maxPt 에서 minPt 까지 0.5pt 씩)
// opts: { lineHeight(em, 기본 1.2), paraGapEm(0.35), face, bold }
function fitText(paragraphs, wIn, hIn, maxPt, minPt, opts = {}) {
  const lh = opts.lineHeight || 1.2;
  const paraGapEm = opts.paraGapEm == null ? 0.35 : opts.paraGapEm;
  const paras = Array.isArray(paragraphs) ? paragraphs : [String(paragraphs || '')];
  for (let pt = maxPt; pt >= minPt - 1e-6; pt -= 0.5) {
    const r = _need(paras, pt, wIn, lh, paraGapEm, opts);
    if (r.need <= hIn) return { pt, lines: r.lines, needIn: r.need, fits: true };
  }
  const r = _need(paras, minPt, wIn, lh, paraGapEm, opts);
  return { pt: minPt, lines: r.lines, needIn: r.need, fits: false };
}

function heightFor(paragraphs, wIn, pt, opts = {}) {
  const lh = opts.lineHeight || 1.2;
  const paraGapEm = opts.paraGapEm == null ? 0.35 : opts.paraGapEm;
  const paras = Array.isArray(paragraphs) ? paragraphs : [String(paragraphs || '')];
  return _need(paras, pt, wIn, lh, paraGapEm, opts).need;
}

module.exports = { charEm, textWidthIn, linesFor, fitText, heightFor, baseLineHeight, spacingMultiple, SAFETY };
