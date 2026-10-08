import test from 'node:test';
import assert from 'node:assert/strict';
import {relatedNodes} from '../src/graphReading.ts';
test('target dependency subgraph includes transitive prerequisites but excludes siblings and descendants',()=>{
 const e=[{source:'a',target:'b'},{source:'b',target:'c'},{source:'a',target:'sibling'},{source:'c',target:'d'}];
 assert.deepEqual([...relatedNodes('c',e,true)].sort(),['a','b']);
 assert.deepEqual([...relatedNodes('b',e,false)].sort(),['c','d']);
 assert.deepEqual([...relatedNodes('',e,true)],[]);
});
test('cycles and duplicate edges terminate without including the focused node',()=>{
 const e=[{source:'a',target:'b'},{source:'b',target:'a'},{source:'a',target:'b'}];
 assert.deepEqual([...relatedNodes('a',e,true)],['b']);
});
