'use strict';
// 네이티브 차트 — 팔레트·직접 라벨·하이라이트·조용한 프레임을 토큰에서 가져온다.
// highlight: 카테고리 index(숫자) → 단일 시리즈를 '기타(muted)' + '강조' 두 시리즈로 나눠 barOverlapPct 100 으로 겹친다.
//            시리즈 이름(문자열) → 그 시리즈만 primary, 나머지 muted.

function buildChart(ctx, slide, spec, box) {
  const pres = ctx.pres;
  const C = ctx.tok.chart;
  const type = (spec.type || 'column').toLowerCase();
  const cats = spec.categories || [];
  let series = (spec.series || []).map((s) => ({ name: s.name || '', labels: cats, values: s.values.map((v) => (v == null ? null : Number(v))) }));
  if (!series.length) { ctx.warn('차트 series 없음', {}); return; }
  const fmt = spec.value_format || (series.some((s) => s.values.some((v) => v != null && !Number.isInteger(v))) ? '#,##0.0' : '#,##0');
  const showValues = spec.show_values !== false;
  const labelPt = spec.label_pt || C.label_pt;
  const common = {
    x: box.x, y: box.y, w: box.w, h: box.h,
    showLegend: false,
    dataLabelFontFace: '+mn-lt', catAxisLabelFontFace: '+mn-lt', valAxisLabelFontFace: '+mn-lt', legendFontFace: '+mn-lt',
    dataLabelFontSize: labelPt, catAxisLabelFontSize: labelPt, valAxisLabelFontSize: labelPt - 1, legendFontSize: labelPt,
    dataLabelColor: ctx.pal.ink, catAxisLabelColor: ctx.pal.ink_muted, valAxisLabelColor: ctx.pal.ink_faint, legendColor: ctx.pal.ink_muted,
    valGridLine: { color: C.gridline, size: 0.5 }, catGridLine: { style: 'none' },
    catAxisLineShow: true, valAxisLineShow: false,
    dataLabelFormatCode: fmt, valAxisLabelFormatCode: fmt,
    showTitle: false,
    lang: 'ko-KR',
  };
  if (spec.y_max != null) common.valAxisMaxVal = spec.y_max;
  if (spec.y_min != null) common.valAxisMinVal = spec.y_min;
  let colors = C.palette.slice(0, Math.max(1, series.length));
  const hl = spec.highlight;
  let chartType = pres.ChartType.bar;
  const opts = {};

  const isBar = ['column', 'bar', 'stacked_column', 'stacked_bar'].includes(type);
  if (isBar) {
    opts.barDir = type.includes('bar') && !type.includes('column') ? 'bar' : 'col';
    opts.barGapWidthPct = series.length > 1 && !type.startsWith('stacked') ? 80 : 60;
    if (type.startsWith('stacked')) { opts.barGrouping = 'stacked'; opts.dataLabelPosition = 'ctr'; opts.dataLabelColor = ctx.pal.on_primary; }
    else opts.dataLabelPosition = 'outEnd';
    if (typeof hl === 'number' && series.length === 1 && !type.startsWith('stacked')) {
      const base = series[0];
      series = [
        { name: base.name || '기타', labels: cats, values: base.values.map((v, i) => (i === hl ? null : v)) },
        { name: '강조', labels: cats, values: base.values.map((v, i) => (i === hl ? v : null)) },
      ];
      colors = [C.muted, C.highlight];
      opts.barOverlapPct = 100;
      opts.barGapWidthPct = 60;
    } else if (typeof hl === 'string' && series.length > 1) {
      colors = series.map((s) => (s.name === hl ? C.highlight : C.muted));
    } else if (series.length === 1) {
      colors = [C.palette[0]];
    }
    opts.valAxisHidden = !!spec.hide_value_axis || (showValues && series.length <= 2 && !type.startsWith('stacked'));
    if (opts.valAxisHidden) opts.valGridLine = { style: 'none' };
  } else if (type === 'line' || type === 'area') {
    chartType = type === 'line' ? pres.ChartType.line : pres.ChartType.area;
    opts.lineSize = 2.25;
    opts.lineDataSymbol = 'circle';
    opts.lineDataSymbolSize = 6;
    opts.lineSmooth = false;
    opts.dataLabelPosition = 't';
    if (typeof hl === 'string' && series.length > 1) colors = series.map((s) => (s.name === hl ? C.highlight : C.muted));
    if (series.length > 1) { common.showLegend = true; common.legendPos = 'b'; }
    if (series.length > 1 && showValues) opts.showValue = false; // 선 2개 이상이면 라벨은 어지러움
  } else if (type === 'pie' || type === 'doughnut') {
    chartType = type === 'pie' ? pres.ChartType.pie : pres.ChartType.doughnut;
    const vals = series[0].values;
    colors = vals.map((_, i) => (typeof hl === 'number' ? (i === hl ? C.highlight : C.palette[Math.min(i, C.palette.length - 1)]) : C.palette[Math.min(i, C.palette.length - 1)]));
    opts.showPercent = spec.show_percent !== false;
    opts.showValue = false;
    common.dataLabelFormatCode = '0%';
    opts.dataLabelPosition = 'bestFit';
    opts.showLeaderLines = true;
    opts.dataLabelColor = ctx.pal.ink;
    opts.showLabel = true;
    if (type === 'doughnut') opts.holeSize = 60;
    common.showLegend = false;
    if (vals.length > 6) ctx.warn(`원형 차트 조각 ${vals.length}개 > 6 — 막대로 바꾸거나 기타로 합친다`, {});
  } else if (type === 'scatter') {
    chartType = pres.ChartType.scatter;
    // series[0] = X, 나머지 = Y
    opts.lineSize = 0;
    opts.lineDataSymbol = 'circle';
    opts.lineDataSymbolSize = 8;
    opts.showValue = false;
    common.showLegend = series.length > 2;
  } else if (type === 'combo') {
    // series[i].kind: 'bar' | 'line'; secondary: true → 보조축
    const bars = (spec.series || []).filter((s) => (s.kind || 'bar') === 'bar');
    const lines = (spec.series || []).filter((s) => s.kind === 'line');
    const useSecondary = lines.some((s) => s.secondary);
    const data = [];
    if (bars.length) data.push({ type: pres.ChartType.bar, data: bars.map((s) => ({ name: s.name, labels: cats, values: s.values })), options: { barDir: 'col', barGapWidthPct: 80, chartColors: bars.map((_, i) => C.palette[i]), showValue: showValues, dataLabelPosition: 'outEnd' } });
    if (lines.length) data.push({ type: pres.ChartType.line, data: lines.map((s) => ({ name: s.name, labels: cats, values: s.values })), options: Object.assign({ chartColors: lines.map(() => C.highlight), lineSize: 2.25, lineDataSymbol: 'circle', lineDataSymbolSize: 6, showValue: false }, useSecondary ? { secondaryValAxis: true, secondaryCatAxis: true } : {}) });
    const comboOpts = Object.assign({}, common, { showLegend: true, legendPos: 'b' });
    if (useSecondary) {
      comboOpts.valAxes = [{ showValAxisTitle: false, valAxisLabelFormatCode: fmt }, { showValAxisTitle: false, valGridLine: { style: 'none' }, valAxisLabelFormatCode: lines[0].value_format || '0' }];
      comboOpts.catAxes = [{ catAxisTitle: '' }, { catAxisHidden: true }];
    }
    slide.addChart(data, comboOpts);
    return;
  }
  const finalOpts = Object.assign({}, common, opts, { chartColors: colors, showValue: opts.showValue != null ? opts.showValue : showValues });
  if (spec.unit && !spec.hide_unit) {
    // 단위는 축 제목(세로 회전) 대신 차트 상단 우측에 작은 라벨로 — 한글 세로 회전은 읽기 어렵다
    slide.addText(`(단위: ${spec.unit})`, { x: box.x, y: box.y - 0.26, w: box.w, h: 0.22, fontSize: Math.max(8, labelPt - 2), color: ctx.pal.ink_faint, align: 'right', valign: 'bottom', isTextBox: true, margin: 0, fontFace: ctx.font.body, lang: 'ko-KR' });
  }
  slide.addChart(chartType, series, finalOpts);
}

module.exports = { buildChart };
