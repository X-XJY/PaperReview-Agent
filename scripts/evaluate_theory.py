"""Opt-in live evaluation; PDFs, parser output and credentials stay local.

Run from repository root: python -m scripts.evaluate_theory 1406.2661
This uses the configured MinerU and language-model APIs and their credits.
"""
import argparse
import hashlib
import json
import time
import sys
from pathlib import Path
import httpx
from backend import db
from backend.mineru import parse
from backend.pipeline import chunks, verify_items
from backend.theory import extract_theory


def reference_checks(result, reference):
    labels={n.id:n.label for n in result.nodes}
    actual=set(labels.values())
    expected=set(reference['labels'])
    edges={(labels[e.source],labels[e.target]) for e in result.edges}
    conditions={n.label:' '.join(n.conditions) for n in result.nodes}
    return {'expected_nodes_found':len(actual&expected),'expected_nodes':len(expected),
            'unexpected_labels':sorted(actual-expected),'missing_labels':sorted(expected-actual),
            'expected_edges_found':len(edges&{tuple(e) for e in reference['edges']}),
            'expected_edges':len(reference['edges']),
            'unexpected_edges':sorted(edges-{tuple(e) for e in reference['edges']}),
            'condition_keyword_checks':{label:{term:term in conditions.get(label,'') for term in terms}
                                        for label,terms in reference['condition_checks'].items()}}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser()
    parser.add_argument('arxiv_id',choices=['1406.2661','1706.03762'])
    args=parser.parse_args()
    folder=db.DATA/'finals-evaluation'/args.arxiv_id
    folder.mkdir(parents=True,exist_ok=True)
    pdf=folder/'paper.pdf'
    if not pdf.exists():
        response=httpx.get('https://arxiv.org/pdf/'+args.arxiv_id,follow_redirects=True,timeout=90)
        response.raise_for_status()
        if not response.content.startswith(b'%PDF'):
            raise RuntimeError('下载结果不是 PDF。')
        pdf.write_bytes(response.content)
    digest=hashlib.sha256(pdf.read_bytes()).hexdigest()
    db.init()
    job='theory-eval-'+args.arxiv_id
    with db.connection() as conn:
        conn.execute("INSERT OR IGNORE INTO jobs(id,session,status,stage,payload,created,updated) VALUES(?,?,'running','理论评测',?, ?,?)",(job,'local-evaluation',json.dumps({'files':[]}),time.time(),time.time()))
        conn.execute('UPDATE jobs SET payload=? WHERE id=?',(json.dumps({'files':[]}),job))
    evidence=parse(pdf,digest,job)
    print(json.dumps({'paper':args.arxiv_id,'blocks':len(evidence),'phase':'parsed'}),flush=True)
    result=extract_theory(evidence,job,chunks,verify_items)
    (folder/'theory.json').write_text(result.model_dump_json(indent=2),encoding='utf-8')
    (folder/'evidence.json').write_text(json.dumps([e.model_dump() for e in evidence],ensure_ascii=False),encoding='utf-8')
    labels={n.id:n.label for n in result.nodes}
    summary={'paper':args.arxiv_id,'nodes':[{ 'label':n.label,'kind':n.kind,'conditions':n.conditions} for n in result.nodes],
             'edges':[{ 'source':labels[e.source],'target':labels[e.target],'explanation':e.explanation} for e in result.edges],
             'warnings':result.warnings}
    reference=json.loads(Path('tests/theory_reference_cases.json').read_text(encoding='utf-8'))['cases'][args.arxiv_id]
    summary['reference_checks']=reference_checks(result,reference)
    (folder/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    db.update(job,status='completed',stage='理论评测完成')


if __name__=='__main__':
    main()
