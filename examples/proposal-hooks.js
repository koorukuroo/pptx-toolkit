'use strict';
// custom 아키타입 예시: 슬라이드 11에 간트 막대를 pptxgenjs API로 직접 그린다.
// 시그니처: (slide, ctx, slideSpec, body). ctx.pal(팔레트)·ctx.scale(글자 크기)·ctx.font 만 쓰고 색·폰트를 새로 만들지 않는다.
const P = require('../scripts/lib/primitives');

const TASKS = [
  { name: '데이터 연결', start: 0, len: 4 },
  { name: '예측 모델 학습', start: 3, len: 6 },
  { name: '관제 화면 개발', start: 5, len: 6 },
  { name: '현장 적용·측정', start: 10, len: 6 },
  { name: '결과 보고', start: 15, len: 1, accent: true },
];

module.exports = {
  11: (slide, ctx, s, body) => {
    const weeks = 16;
    const labelW = 2.2;
    const gx = body.x + labelW, gw = body.w - labelW;
    const rowH = Math.min(0.6, (body.h - 0.5) / TASKS.length);
    // 주차 눈금
    for (let w = 0; w <= weeks; w += 4) {
      const x = gx + (gw * w) / weeks;
      P.vline(ctx, slide, x, body.y + 0.3, rowH * TASKS.length + 0.1, { color: ctx.pal.line_faint });
      const lx = Math.min(x - 0.3, body.x + body.w - 0.6); // 마지막 눈금 라벨이 여백 밖으로 나가지 않게
      P.ctxText(ctx, slide, `${w}주`, { x: lx, y: body.y, w: 0.6, h: 0.25, fontSize: ctx.scale.caption, color: ctx.pal.ink_faint, align: w === weeks ? 'right' : 'center' });
    }
    TASKS.forEach((t, i) => {
      const y = body.y + 0.4 + i * rowH;
      P.ctxText(ctx, slide, t.name, { x: body.x, y, w: labelW - 0.2, h: rowH - 0.1, fontSize: ctx.scale.body - 1, color: ctx.pal.ink, valign: 'middle' });
      P.rect(ctx, slide, { x: gx + (gw * t.start) / weeks, y: y + 0.08, w: (gw * t.len) / weeks, h: rowH - 0.26 }, { fill: t.accent ? ctx.pal.accent : ctx.pal.primary, radius: 0 });
    });
    P.ctxText(ctx, slide, '※ 주차는 착수일 기준. 고객 데이터 접근 승인 지연 시 전체 일정이 같은 기간만큼 이동', { x: body.x, y: body.y + body.h - 0.3, w: body.w, h: 0.3, fontSize: ctx.scale.caption, color: ctx.pal.ink_faint });
  },
};
