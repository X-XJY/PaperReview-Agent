import test from 'node:test';
import assert from 'node:assert/strict';
import {matchingItems} from '../src/pdfMatch.ts';
test('evidence matches across lines and normalized ligatures',()=>{
 assert.deepEqual(matchingItems(['A sufficiently long evidence ', 'fragment with efﬁcient methods.'], 'A sufficiently long evidence fragment with efficient methods.'),[0,1]);
});
test('short and ambiguous text never produces fabricated highlights',()=>{
 assert.deepEqual(matchingItems(['short phrase'],'short phrase'),[]);
 const text='This is a sufficiently long repeated evidence passage.';
 assert.deepEqual(matchingItems([text,text],text),[]);
 assert.deepEqual(matchingItems(['Unrelated content and unrelated statements.'],text),[]);
});
