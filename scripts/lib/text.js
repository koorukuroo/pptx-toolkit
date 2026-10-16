'use strict';
// 글자 폭 추정과 상자 맞춤 — core/inspect.py 의 estimate_lines 와 같은 계수를 쓴다.
// 한글 1.0em, 대문자 0.68, 숫자 0.58, 소문자 0.55, 공백 0.3, 좁은 문장부호 0.3. 줄높이 1.2em(기본).

function charEm(ch) {
  const o = ch.codePointAt(0);
  if (ch === ' ') return 0.3;
  if ((o >= 0xac00 && o <= 0xd7a3) || (o >= 0x3130 && o <= 0x318f) || (o >= 0x4e00 && o <= 0x9fff) || (o >= 0x3000 && o <= 0x303f) || (o >= 0xff00 && o <= 0xffef)) return 1.0;
  if (/\d/.test(ch)) return 0.58;
  if (/[A-Z]/.test(ch)) return 0.68;
  if ('.,:;\'|!il'.includes(ch)) return 0.3;
  return 0.55;
}

function textWidthIn(text, pt) {
  let em = 0;
  for (const ch of text) em += charEm(ch);
  return (em * pt) / 72;
}

// 단락 하나를 폭 widthIn 에 흘렸을 때 줄 수 (영숫자 단어 단위, 한글 글자 단위 줄바꿈)
function linesFor(text, pt, widthIn) {
  if (!text) return 1;
  const emIn = pt / 72;
  const tokens = text.match(/\s+|[A-Za-z0-9.,%()'\-/:+]+|./gu) || [];
  let lines = 1;
  let w = 0;
  for (const tok of tokens) {
    let tw = 0;
    for (const ch of tok) tw += charEm(ch) * emIn;
    if (/^\s+$/.test(tok)) { w += tw; continue; }
    if (tw > widthIn) {
      for (const ch of tok) {
        const cw = charEm(ch) * emIn;
        if (w + cw > widthIn && w > 0) { lines += 1; w = 0; }
        w += cw;
      }
      continue;
    }
    if (w + tw > widthIn && w > 0) { lines += 1; w = 0; }
    w += tw;
  }
  return lines;
}

// paragraphs: string[] — 상자(w,h)에 들어가는 최대 글자 크기 (maxPt 에서 minPt 까지 0.5pt 씩)
function fitText(paragraphs, wIn, hIn, maxPt, minPt, opts = {}) {
  const lh = opts.lineHeight || 1.2;
  const paraGapEm = opts.paraGapEm || 0.35; // 문단 사이 간격 (em)
  const paras = Array.isArray(paragraphs) ? paragraphs : [String(paragraphs || '')];
  for (let pt = maxPt; pt >= minPt - 1e-6; pt -= 0.5) {
    let lines = 0;
    for (const p of paras) lines += linesFor(p, pt, wIn);
    const need = (lines * pt * lh + Math.max(0, paras.length - 1) * pt * paraGapEm) / 72;
    if (need <= hIn) return { pt, lines, needIn: need, fits: true };
  }
  let lines = 0;
  for (const p of paras) lines += linesFor(p, minPt, wIn);
  const need = (lines * minPt * lh + Math.max(0, paras.length - 1) * minPt * paraGapEm) / 72;
  return { pt: minPt, lines, needIn: need, fits: false };
}

function heightFor(paragraphs, wIn, pt, opts = {}) {
  const lh = opts.lineHeight || 1.2;
  const paraGapEm = opts.paraGapEm || 0.35;
  const paras = Array.isArray(paragraphs) ? paragraphs : [String(paragraphs || '')];
  let lines = 0;
  for (const p of paras) lines += linesFor(p, pt, wIn);
  return (lines * pt * lh + Math.max(0, paras.length - 1) * pt * paraGapEm) / 72;
}

module.exports = { charEm, textWidthIn, linesFor, fitText, heightFor };
