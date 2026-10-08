import test from 'node:test';
import assert from 'node:assert/strict';
import {methodStudyNodes} from '../src/studyNodes.ts';
test('method reading steps require supported author claims and owned evidence; duplicates are removed',()=>{
 const claim={id:'a',text:'Supported architecture statement',kind:'author_statement',status:'supported',evidence_ids:['e']};
 const paper={id:'p',evidence:[{id:'e',paper_id:'p'},{id:'foreign',paper_id:'other'}],extraction:{methods:[claim,{...claim,id:'duplicate'},{...claim,id:'inference',kind:'inference'},{...claim,id:'unverified',status:'unverified'},{...claim,id:'foreign',evidence_ids:['foreign']}],advantages:[],limitations:[]}};
 const nodes=methodStudyNodes(paper);
 assert.equal(nodes.length,1);
 assert.equal(nodes[0].id,'method-study:methods:a');
 assert.equal(nodes[0].kind,'methods');
 assert.equal(nodes[0].statement,claim.text);
});
