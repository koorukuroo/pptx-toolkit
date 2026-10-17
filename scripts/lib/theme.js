'use strict';
// pptxgenjs가 쓰지 못하는 테마 값(한글 ea 글꼴, 색 스킴)을 작성 후 theme1.xml에 주입한다.
const fs = require('fs');
const path = require('path');

// jszip은 pptxgenjs의 의존성이다. 이 저장소에서 `npm install`을 했으면 바로 풀리지만, pptxgenjs만 전역(`npm i -g`)으로
// 설치된 환경(코드 샌드박스 등)에서는 jszip이 pptxgenjs/node_modules/ 안에 중첩돼 있어 직접 require가 실패한다 —
// 그때는 pptxgenjs가 설치된 위치를 기준으로 다시 찾는다.
function loadJSZip() {
  try {
    return require('jszip');
  } catch (e) {
    const from = path.dirname(require.resolve('pptxgenjs'));
    return require(require.resolve('jszip', { paths: [from] }));
  }
}
const JSZip = loadJSZip();

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

async function applyTheme(file, { headFont, bodyFont, colors, name }) {
  const buf = fs.readFileSync(file);
  const zip = await JSZip.loadAsync(buf);
  const entries = Object.keys(zip.files).filter((n) => /^ppt\/theme\/theme\d+\.xml$/.test(n));
  for (const n of entries) {
    let xml = await zip.file(n).async('string');
    // 글꼴: majorFont / minorFont 의 latin·ea·cs
    xml = xml.replace(/<a:majorFont>[\s\S]*?<\/a:majorFont>/, `<a:majorFont><a:latin typeface="${esc(headFont)}"/><a:ea typeface="${esc(headFont)}"/><a:cs typeface="${esc(headFont)}"/></a:majorFont>`);
    xml = xml.replace(/<a:minorFont>[\s\S]*?<\/a:minorFont>/, `<a:minorFont><a:latin typeface="${esc(bodyFont)}"/><a:ea typeface="${esc(bodyFont)}"/><a:cs typeface="${esc(bodyFont)}"/></a:minorFont>`);
    if (colors) {
      const c = colors;
      const scheme = `<a:clrScheme name="${esc(name || 'pptx-toolkit')}">` +
        `<a:dk1><a:srgbClr val="${c.dk1}"/></a:dk1><a:lt1><a:srgbClr val="${c.lt1}"/></a:lt1>` +
        `<a:dk2><a:srgbClr val="${c.dk2}"/></a:dk2><a:lt2><a:srgbClr val="${c.lt2}"/></a:lt2>` +
        `<a:accent1><a:srgbClr val="${c.accent1}"/></a:accent1><a:accent2><a:srgbClr val="${c.accent2}"/></a:accent2>` +
        `<a:accent3><a:srgbClr val="${c.accent3}"/></a:accent3><a:accent4><a:srgbClr val="${c.accent4}"/></a:accent4>` +
        `<a:accent5><a:srgbClr val="${c.accent5}"/></a:accent5><a:accent6><a:srgbClr val="${c.accent6}"/></a:accent6>` +
        `<a:hlink><a:srgbClr val="${c.hlink}"/></a:hlink><a:folHlink><a:srgbClr val="${c.folHlink}"/></a:folHlink></a:clrScheme>`;
      xml = xml.replace(/<a:clrScheme[\s\S]*?<\/a:clrScheme>/, scheme);
    }
    zip.file(n, xml);
  }
  // 슬라이드·레이아웃의 lang="en-US" 는 그대로 두되, 한글 run 에 altLang 이 없으면 추가하지 않는다(pptxgenjs가 lang 옵션으로 처리).
  const out = await zip.generateAsync({ type: 'nodebuffer', compression: 'DEFLATE' });
  fs.writeFileSync(file, out);
}

module.exports = { applyTheme };
