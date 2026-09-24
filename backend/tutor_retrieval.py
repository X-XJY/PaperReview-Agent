"""Bounded per-request sparse retrieval; raw evidence remains authoritative."""
import re
from rank_bm25 import BM25Okapi

TERMS = {'注意力':'attention', '多头':'multi head', '掩码':'masked mask', '编码器':'encoder',
         '解码器':'decoder', '预训练':'pre training', '训练':'training', '位置':'position positional',
         '局限':'limitation limitations', '复杂度':'complexity', '双向':'bidirectional',
         '缩放':'scaled scaling', '数据集':'dataset', '消融':'ablation', '指标':'evaluation metric',
         '检索':'retrieval', '损失':'loss', '公式':'equation', '实验':'experiment'}

def tokens(text):
    text = text.lower()
    result = re.findall(r'[a-z0-9_]+',text)
    for run in re.findall(r'[\u4e00-\u9fff]+',text):
        result.extend(run[i:i+2] for i in range(max(1,len(run)-1)))
    return result or ['__empty__']

def retrieve(papers, question, keywords=(), pinned=()):
    expanded = question + ' ' + ' '.join(keywords)
    for source,target in TERMS.items():
        if source in question:
            expanded += ' ' + target
    query = tokens(expanded)
    chosen = []
    # Each selected paper gets its own quota; never let one paper dominate comparison.
    quota = max(2, min(8, 16 // len(papers)))
    for paper in papers:
        rows = []
        cards = {}
        for field in ('methods','advantages','limitations','future_work'):
            for claim in paper.extraction.__getattribute__(field):
                if claim.kind == 'human_note':
                    continue
                for ref in claim.evidence_ids:
                    cards[ref] = cards.get(ref,'') + ' ' + claim.text
        for e in paper.evidence:
            for start in range(0,len(e.text),1100):
                excerpt=e.text[start:start+1400]
                rows.append({'evidence_id':e.id,'paper_id':paper.id,'page':e.page,
                             'section':e.section,'text':excerpt,'offset':start})
        if not rows:
            continue
        corpus=[tokens(r['text']+' '+r['section']+' '+cards.get(r['evidence_id'],'')) for r in rows]
        index=BM25Okapi(corpus)
        scores=index.get_scores(query)
        # Explicit overlap keeps tiny corpora usable when BM25's IDF is zero/negative.
        ranked=sorted(range(len(rows)),key=lambda i:(rows[i]['evidence_id'] in pinned,
                      sum(t in set(corpus[i]) for t in set(query)),float(scores[i])),reverse=True)
        seen=set()
        for i in ranked:
            row=rows[i]
            if row['evidence_id'] in seen:
                continue
            if row['evidence_id'] not in pinned and not set(query).intersection(corpus[i]):
                continue
            seen.add(row['evidence_id'])
            chosen.append(row)
            if len(seen)>=quota:
                break
    return chosen
