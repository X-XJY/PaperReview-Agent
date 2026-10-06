import test from 'node:test';
import assert from 'node:assert/strict';
import {dependencyPositions} from '../src/graphLayout.ts';

test('proof layers follow prerequisites including diamonds; isolated nodes stay independent',()=>{
  const positions=dependencyPositions(['a','b','c','d','e'],[{source:'a',target:'b'},{source:'a',target:'c'},{source:'b',target:'d'},{source:'c',target:'d'}]);
  assert.equal(positions.a.y,0);
  assert.equal(positions.b.y,160);
  assert.equal(positions.c.y,160);
  assert.equal(positions.d.y,320);
  assert.equal(positions.e.y,0);
  assert.notEqual(positions.b.x,positions.c.x);
});
test('cycles never receive invented prerequisite layers; duplicate or foreign edges are harmless',()=>{
  assert.equal(dependencyPositions(['a','b'],[{source:'a',target:'b'},{source:'b',target:'a'}]),null);
  const positions=dependencyPositions(['a','b'],[{source:'a',target:'b'},{source:'a',target:'b'},{source:'missing',target:'b'}]);
  assert.equal(positions.b.y,160);
});
