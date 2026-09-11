import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';
import { readFileSync, writeFileSync, mkdirSync, unlinkSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const dir=resolve('node_modules/.cache');mkdirSync(dir,{recursive:true});
const file=resolve(dir,`evidence-test-${process.pid}.mjs`);
const source=readFileSync('src/EvidenceText.tsx','utf8').replace(/^import ['"].*\.css['"];?\r?\n/gm,'');
writeFileSync(file,ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,jsx:ts.JsxEmit.ReactJSX}}).outputText);
let EvidenceText;
try { EvidenceText=(await import(pathToFileURL(file).href)).default; } finally { unlinkSync(file); }
const render=text=>renderToStaticMarkup(createElement(EvidenceText,{text}));

test('MinerU HTML tables render as cells, including incomplete retrieved fragments',()=>{
 const html=render('<table><tr><th>Method</th><th>Score</th></tr><tr><td>BERT</td><td>80.5</td></tr></table>');
 assert.match(html,/<table>/);assert.match(html,/<td>BERT<\/td>/);assert.doesNotMatch(html,/&lt;table/);
 assert.match(render('<table><tr><td>Visible text'),/Visible text<\/td>/);
});
test('untrusted evidence cannot execute HTML or load remote images',()=>{
 const html=render('<script>alert(1)</script><table onclick="alert(2)"><tr><td>Safe</td></tr></table><img src="https://evil.example/x" onerror="alert(3)"><a href="javascript:alert(4)">Link</a>');
 assert.match(html,/Safe/);assert.doesNotMatch(html,/<script|onclick|onerror|<img|javascript:|evil\.example/);
});
test('ordinary evidence text and formulas remain readable',()=>{
 const html=render('Attention uses $d_k$ dimensions.');
 assert.match(html,/Attention uses/);assert.match(html,/katex/);
});
