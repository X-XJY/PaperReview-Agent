import json
from pathlib import Path
from . import db
from .llm import call
from .mineru import parse
from .schemas import Metadata, Extraction, Classification, Paper, Synthesis, Verification

ONTOLOGY = json.loads(Path(__file__).with_name('ontology.json').read_text(encoding='utf-8'))

def label_ids(nodes):
    return {node['id'] for node in nodes} | {key for node in nodes for key in label_ids(node.get('children',[]))}

def chunks(evidence, limit=24000):
    group, size = [], 0
    for block in evidence:
        if group and size + len(block.text) > limit:
            yield group
            group, size = [], 0
        group.append(block)
        size += len(block.text)
    if group:
        yield group

def refs_valid(refs, available):
    return bool(refs) and all(ref in available for ref in refs)

def all_claims(paper):
    return [c for field in ('methods','advantages','limitations','future_work') for c in getattr(paper.extraction,field)]

def verify_items(items, evidence, job_id):
    available = {e.id:e for e in evidence}
    results = {}
    # Bounded groups keep the verifier from losing individual claims in a long context.
    for start in range(0,len(items),8):
        group = items[start:start+8]
        valid = []
        for item in group:
            if not refs_valid(item['evidence_ids'],available):
                results[item['id']] = ('unsupported','缺少有效原文证据。')
            else:
                valid.append(item)
        if valid:
            wanted = set(ref for item in valid for ref in item['evidence_ids'])
            # Include neighboring blocks so a quote is checked in context.
            for index, block in enumerate(evidence):
                if block.id in set(ref for item in valid for ref in item['evidence_ids']):
                    wanted.update(e.id for e in evidence[max(0,index-1):index+2] if e.paper_id == block.paper_id)
            verification = call('verify', {'items':valid,'evidence':[available[k].model_dump() for k in sorted(wanted)]}, Verification, job_id)
            ids = [check.id for check in verification.checks]
            for item in valid:
                matches = [check for check in verification.checks if check.id == item['id']]
                if len(matches) == 1:
                    results[item['id']] = (matches[0].status,matches[0].reason)
                else:
                    results[item['id']] = ('unverified','校验结果缺失或重复，需人工确认。')
    return results

def verify_paper(paper, job_id):
    claims = all_claims(paper)
    items = [{'id':c.id,'text':c.text,'kind':c.kind,'evidence_ids':c.evidence_ids} for c in claims if c.kind != 'human_note']
    items.append({'id':'metadata','text':paper.metadata.model_dump(),'evidence_ids':paper.metadata.evidence_ids})
    items.append({'id':'classification','text':{'classification':paper.classification.model_dump(),'ontology':ONTOLOGY},'evidence_ids':paper.classification.evidence_ids})
    for index, evaluation in enumerate(paper.extraction.evaluations):
        items.append({'id':f'eval-{index}','text':evaluation.model_dump(),'evidence_ids':evaluation.evidence_ids})
    result = verify_items(items,paper.evidence,job_id)
    paper.warnings = [w for w in paper.warnings if w.startswith('标签') or w.startswith('页码')]
    for claim in claims:
        if claim.kind == 'human_note':
            claim.status,claim.reason = 'unverified','人工备注，不作为已核验论文事实。'
        else:
            claim.status,claim.reason = result[claim.id]
    for key in ['metadata','classification']+[f'eval-{i}' for i in range(len(paper.extraction.evaluations))]:
        status,reason = result[key]
        if status != 'supported':
            paper.warnings.append(f'{key} 待确认：{reason}')
    return paper

def extract_paper(file, job_id):
    paper_id = file['hash']
    evidence = parse(Path(file['path']), paper_id, job_id)
    db.update(job_id,stage=f'元信息 · {file["name"]}')
    front = evidence[:18]
    metadata = call('metadata', {'evidence':[e.model_dump() for e in front]}, Metadata, job_id)
    combined = Extraction(method_name='',methods=[],advantages=[],limitations=[],future_work=[],evaluations=[])
    # Every block participates. No silent loss of introduction/appendix/limitations.
    for index, group in enumerate(chunks(evidence)):
        db.update(job_id,stage=f'方法拆解 {index+1} · {file["name"]}')
        part = call('extract', {'metadata':metadata.model_dump(),'evidence':[e.model_dump() for e in group]}, Extraction, job_id)
        if part.methods and not combined.method_name:
            combined.method_name = part.method_name
        for field in ('methods','advantages','limitations','future_work','evaluations'):
            existing = getattr(combined,field)
            for item in getattr(part,field):
                marker = item.text if hasattr(item,'text') else json.dumps(item.model_dump(),sort_keys=True)
                if not any((x.text if hasattr(x,'text') else json.dumps(x.model_dump(),sort_keys=True)) == marker for x in existing):
                    existing.append(item)
    combined.method_name = combined.method_name or metadata.title
    for field in ('methods','advantages','limitations','future_work'):
        for index,claim in enumerate(getattr(combined,field)):
            claim.id = f'{paper_id[:12]}-{field}-{index}'
            claim.kind = 'author_statement'
            claim.status = 'unverified'
    db.update(job_id,stage=f'分类与核验 · {file["name"]}')
    wanted = {ref for claim in combined.methods for ref in claim.evidence_ids}
    classification = call('classify', {'extraction':combined.model_dump(),'ontology':ONTOLOGY,'evidence':[e.model_dump() for e in evidence if e.id in wanted]}, Classification,job_id)
    warnings = []
    for field,branch in [('task_ids','tasks'),('method_ids','methods')]:
        ids = getattr(classification,field)
        allowed = label_ids(ONTOLOGY[branch])
        if any(key not in allowed for key in ids):
            warnings.append('标签校验：已移除本体外标签。')
        setattr(classification,field,sorted(set(key for key in ids if key in allowed)))
    if any(e.page is None for e in evidence):
        warnings.append('页码映射不完整，部分证据只能定位到正文块。')
    paper = Paper(id=paper_id,filename=file['name'],metadata=metadata,extraction=combined,classification=classification,evidence=evidence,warnings=warnings)
    return verify_paper(paper,job_id)

def synthesize(papers, job_id):
    evidence = [e for p in papers for e in p.evidence]
    available = {e.id:e for e in evidence}
    cards = []
    wanted = set()
    for paper in papers:
        card = paper.model_dump(exclude={'evidence'})
        for field in ('methods','advantages','limitations','future_work'):
            card['extraction'][field] = [c.model_dump() for c in getattr(paper.extraction,field) if c.status == 'supported' and c.kind != 'human_note']
            wanted.update(ref for c in card['extraction'][field] for ref in c['evidence_ids'])
        # Unverified evaluation and metadata fields remain labeled via warnings.
        wanted.update(paper.metadata.evidence_ids)
        cards.append(card)
    result = call('synthesize', {'papers':cards,'evidence':[available[k].model_dump() for k in sorted(wanted) if k in available]}, Synthesis, job_id)
    paper_ids = {p.id for p in papers}
    result.relations = [r for r in result.relations if r.source in paper_ids and r.target in paper_ids and r.source != r.target and refs_valid(r.evidence_ids,available)]
    result.common_gaps = [g for g in result.common_gaps if refs_valid(g.evidence_ids,available) and len({available[r].paper_id for r in g.evidence_ids}) >= 2]
    items = []
    for index,c in enumerate(result.summary):
        c.id = f'summary-{index}'
        c.kind = 'inference'
        items.append({'id':c.id,'text':c.text,'evidence_ids':c.evidence_ids})
    for index,d in enumerate(result.directions):
        d.id = f'direction-{index}'
        items.append({'id':d.id,'text':d.model_dump(),'evidence_ids':d.evidence_ids})
    for index,r in enumerate(result.relations):
        items.append({'id':f'relation-{index}','text':r.model_dump(),'evidence_ids':r.evidence_ids})
    for index,g in enumerate(result.common_gaps):
        items.append({'id':f'gap-{index}','text':g.model_dump(),'evidence_ids':g.evidence_ids})
    verified = verify_items(items,evidence,job_id)
    for c in result.summary:
        c.status,c.reason = verified[c.id]
    for d in result.directions:
        d.status,d.reason = verified[d.id]
    for index,r in enumerate(result.relations):
        r.status = verified[f'relation-{index}'][0]
    result.relations = [r for r in result.relations if r.status == 'supported']
    result.common_gaps = [g for index,g in enumerate(result.common_gaps) if verified[f'gap-{index}'][0] == 'supported']
    return result

def run(job):
    output = job['result'] or {'papers':[],'synthesis':None,'failures':[],'mode':'live'}
    papers = [Paper.model_validate(p) for p in output['papers']]
    output['failures'] = []
    done = {p.id for p in papers}
    for file in job['payload']['files']:
        if file['hash'] in done:
            continue
        try:
            paper = extract_paper(file,job['id'])
            papers.append(paper)
            done.add(paper.id)
        except Exception as error:
            output['failures'].append({'filename':file['name'],'message':str(error) if isinstance(error,RuntimeError) else '处理失败，请检查文件或服务配置。'})
        output['papers'] = [p.model_dump() for p in papers]
        db.update(job['id'],result=json.dumps(output,ensure_ascii=False))
    if not papers:
        db.update(job['id'],status='failed',stage='处理失败',error='没有成功处理的论文。可查看单篇错误后重试。')
        return
    dirty = set(job['payload'].get('dirty_papers',[]))
    for index,paper in enumerate(papers):
        if paper.id in dirty:
            db.update(job['id'],stage='重新核验人工修正')
            wanted = {ref for c in paper.extraction.methods for ref in c.evidence_ids}
            classification = call('classify',{'extraction':paper.extraction.model_dump(),'ontology':ONTOLOGY,'evidence':[e.model_dump() for e in paper.evidence if e.id in wanted]},Classification,job['id'])
            classification.task_ids = [v for v in classification.task_ids if v in label_ids(ONTOLOGY['tasks'])]
            classification.method_ids = [v for v in classification.method_ids if v in label_ids(ONTOLOGY['methods'])]
            paper.classification = classification
            papers[index] = verify_paper(paper,job['id'])
    output['papers'] = [p.model_dump() for p in papers]
    db.update(job['id'],stage='演进推导与聚合核验',result=json.dumps(output,ensure_ascii=False))
    output['synthesis'] = synthesize(papers,job['id']).model_dump()
    payload = {**job['payload'],'dirty_papers':[]}
    db.update(job['id'],status='partial' if output['failures'] else 'completed',stage='分析完成',stale=0,error=None,payload=json.dumps(payload),result=json.dumps(output,ensure_ascii=False))
