def escape(text):
    return str(text or '').replace('|','\\|').replace('\n',' ')

def report(job):
    result = job['result'] or {}
    evidence = {e['id']:e for p in result.get('papers',[]) for e in p['evidence']}
    def cites(ids):
        return ' '.join(f'[{i}]' for i in ids if i in evidence)
    lines = ['# 论文方法梳理报告','',f"模式：{'演示样例（非真实论文事实）' if result.get('mode') == 'demo' else '真实 API 分析'}",f"状态：{'人工修正后待重新推导' if job['stale'] else job['status']}",'','> 研究方向为待验证假设；证据支持状态不代表假设已被实验证明。','', '## 多论文对比','', '| 论文 | 方法 | 优势 | 作者局限 | 数据集 |','|---|---|---|---|---|']
    for p in result.get('papers',[]):
        ex = p['extraction']
        def values(field):
            return '; '.join(c['text']+f"（{c['status']}）"+cites(c['evidence_ids']) for c in ex[field]) or '未找到明确陈述'
        lines.append('| '+' | '.join(escape(x) for x in [p['metadata']['title'],values('methods'),values('advantages'),values('limitations'),'; '.join(e['dataset'] for e in ex['evaluations'])])+' |')
        lines.extend([])
    for p in result.get('papers',[]):
        lines += ['', '## '+p['metadata']['title'],f"版本：{p['revision']} · 年份：{p['metadata']['year'] or '未知'}",'']
        for field,label in [('methods','方法'),('advantages','优势'),('limitations','作者局限'),('future_work','作者未来工作')]:
            lines.append('### '+label)
            lines += ['- '+c['text']+f" [{c['status']}] "+cites(c['evidence_ids']) for c in p['extraction'][field]] or ['未找到明确陈述。']
        lines += ['', '### 数据集与评价指标']
        lines += ['- '+escape(e['dataset'])+' / '+escape(e['metric'])+' / '+escape(e['value'])+'；条件：'+escape(e['setting'])+' '+cites(e['evidence_ids']) for e in p['extraction']['evaluations']]
        lines += ['- 告警：'+w for w in p['warnings']]
    synthesis = result.get('synthesis')
    if synthesis:
        lines += ['', '## 技术演进总结']
        lines += ['- '+c['text']+f" [{c['status']}] "+cites(c['evidence_ids']) for c in synthesis['summary']]
        lines += ['', '## 方法关系']
        lines += [f"- {r['source']} → {r['target']}：{r['type']}；{r['scope']} "+cites(r['evidence_ids']) for r in synthesis['relations']]
        lines += ['', '## 方法—共性缺陷—改进思路','', '| 方法 | 共性缺陷 | 改进思路 |','|---|---|---|']
        lines += ['| '+' | '.join(escape(g[k]) for k in ['method','limitation','idea'])+cites(g['evidence_ids'])+' |' for g in synthesis['common_gaps']]
        lines += ['', '## 待验证研究方向']
        for d in synthesis['directions']:
            lines += ['', '### '+d['title'],f"依据状态：{d['status']}；{d['reason']}"]
            lines += [f"- {label}：{d[field]}" for field,label in [('problem','问题'),('hypothesis','假设'),('reasoning','推导依据'),('experiment','验证实验'),('failure_condition','失败条件')]]
            lines.append(cites(d['evidence_ids']))
    if result.get('failures'):
        lines += ['', '## 未完成论文']+[f"- {f['filename']}：{f['message']}" for f in result['failures']]
    lines += ['', '## 原文证据']
    for e in evidence.values():
        lines += ['',f"### [{e['id']}] · PDF 第 {e['page'] or '未知'} 页 · {e['section']}",'> '+e['text'].replace('\n','\n> ')]
    return '\n'.join(lines)
