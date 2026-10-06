"""Original synthetic fixtures. Never present these as published research claims."""
import json
from pathlib import Path

rows = [
 ('atlas','Atlas-R · 双编码器检索增强生成',2020,'双编码器检索', ['method.retrieval.dense','method.fusion.context'], 'A dual encoder retrieves passages and concatenates them with the question before generation.', 'The system is evaluated on a single-domain collection; cross-domain transfer remains untested.', 'Compare the retrieved passages with a manually annotated evidence set.', '基于双编码器召回段落，将证据与问题拼接后生成答案。','仅在单一领域语料上评估，跨域迁移尚未验证。'),
 ('fusion','Fusion-R · 多文档解码融合',2021,'多文档融合', ['method.fusion.decoder','method.retrieval.dense'], 'We extend Atlas-R by encoding each passage independently and fusing representations in the decoder.', 'Memory use grows with the number of retrieved passages. We leave adaptive passage selection to future work.', 'At a fixed retrieval budget, independent passage encoding improves evidence coverage in our synthetic benchmark.', '独立编码各个检索段落，在解码阶段融合多文档信息。','检索段落数量增加时，内存开销随之增长。'),
 ('loop','Loop-R · 迭代证据检索',2022,'迭代检索', ['method.retrieval.iterative','method.retrieval.rewrite'], 'Loop-R retrieves again using an intermediate answer as a reformulated query.', 'An incorrect intermediate answer may redirect retrieval to irrelevant passages.', 'Additional retrieval rounds increase evidence coverage on two-hop questions in this controlled setting.', '根据中间答案重写查询，通过多轮检索补充证据。','错误的中间答案可能导致检索转向无关段落。'),
 ('reflect','Reflect-R · 反思驱动的生成',2023,'自反思生成', ['method.control.reflect','method.control.adaptive'], 'Building on Loop-R, we add a reflection decision before each additional retrieval step.', 'The reflection classifier requires labeled examples and can fail under domain shift.', 'Skipping unnecessary retrieval reduces the number of retrieval calls in this evaluation.', '在每轮检索前引入反思判断，决定是否继续检索。','反思分类器需要标注样本，在领域偏移下可能失效。'),
 ('verify','Verify-R · 引用支持核验',2024,'证据支持核验', ['method.control.verify','method.control.citation'], 'Each generated statement is paired with a passage and checked for textual support.', 'Textual support does not establish that the source passage itself is factually correct.', 'Unsupported statements are flagged for manual review rather than silently accepted.', '将生成结论与段落配对，核验文本是否支持该结论。','文本支持关系不能证明来源段落本身的事实正确性。')
]
papers=[]
for slug,title,year,method,tags,method_quote,limit_quote,adv_quote,method_cn,limit_cn in rows:
    pid='demo-'+slug
    ev=[{'id':pid+'-e'+str(i),'paper_id':pid,'text':text,'page':i,'section':section} for i,text,section in [(1,title+'\nSynthetic Research Team · '+str(year)+'\nThis is an invented demonstration document, not a published paper.','示例元信息'),(2,method_quote,'3 Method'),(3,limit_quote,'6 Limitations'),(4,adv_quote,'4 Evaluation')]]
    def claim(suffix,text,e,kind='author_statement',status='supported'):
        return {'id':pid+'-'+suffix,'text':text,'evidence_ids':[pid+'-e'+str(e)],'kind':kind,'status':status,'reason':'示例核验状态，仅用于演示交互。'}
    papers.append({'id':pid,'filename':slug+'-example.pdf','metadata':{'title':title,'authors':['Synthetic Research Team'],'year':year,'venue':'原创教学样例 · 非真实论文','task':'知识密集型问答','evidence_ids':[pid+'-e1']},'extraction':{'method_name':method,'methods':[claim('method',method_cn,2)],'advantages':[claim('adv',{'atlas':'对检索段落进行人工证据集对照评估。','fusion':'在固定检索预算下提高证据覆盖。','loop':'在限定的双跳问题场景增加证据覆盖。','reflect':'跳过不必要的检索，减少检索调用。','verify':'将不受支持的陈述标记给人工审核。'}[slug],4)],'limitations':[claim('limit',limit_cn,3)],'future_work':[claim('future','探索自适应段落选择。',3)] if slug=='fusion' else [],'evaluations':[]},'classification':{'task_ids':['task.qa.open'],'method_ids':tags,'rationale':'教学用预置分类，非模型分析。','evidence_ids':[pid+'-e2']},'evidence':ev,'revision':1,'warnings':[]})
result={'mode':'demo','papers':papers,'failures':[],'synthesis':{'summary':[{'id':'summary-1','text':'这组教学样例依次展示了稠密检索、多文档融合、迭代检索、反思控制和引用核验。时间顺序不自动构成继承关系。','evidence_ids':[p['id']+'-e2' for p in papers],'kind':'inference','status':'supported','reason':'教学示例。'}],'relations':[{'source':'demo-atlas','target':'demo-fusion','type':'improves','scope':'独立编码段落并在解码阶段融合','evidence_ids':['demo-fusion-e2'],'status':'supported'},{'source':'demo-loop','target':'demo-reflect','type':'improves','scope':'在迭代检索前增加反思决策','evidence_ids':['demo-reflect-e2'],'status':'supported'}],'directions':[{'id':'direction-1','title':'让检索预算随证据需求变化','problem':'多文档融合的内存开销与额外检索调用需要控制。','hypothesis':'依据证据覆盖动态选择段落和检索轮数，可能在相近回答质量下减少开销。','reasoning':'Fusion-R 指出段落数量带来的内存问题；Reflect-R 展示检索调用可以按需跳过。这只构成实验动机。','experiment':'固定生成模型与数据划分，对比固定段落数和自适应策略；记录答案质量、证据覆盖、内存和检索调用次数。','failure_condition':'若覆盖率显著下降或控制器自身成本抵消节省，则假设不成立。','evidence_ids':['demo-fusion-e3','demo-reflect-e4'],'status':'supported','reason':'示例中前提有依据；假设尚未验证。'},{'id':'direction-2','title':'检索链错误的早期识别','problem':'中间答案错误可能污染后续检索，反思判断也可能受领域变化影响。','hypothesis':'在新一轮检索前增加原文支持检查，可能降低错误传播。','reasoning':'将 Loop-R 的错误传播风险与 Verify-R 的支持核验思路组合，尚需验证域外表现。','experiment':'构造正确与错误中间答案两组，测量错误检索率、最终正确率与额外时延，并加入域外测试。','failure_condition':'检查器无法识别错误，或引入过多误拒绝。','evidence_ids':['demo-loop-e3','demo-verify-e2','demo-reflect-e3'],'status':'partial','reason':'组合策略的可行性仍需实验。'}],'common_gaps':[{'method':'双编码器检索 / 反思控制','limitation':'域外适用性仍需验证','idea':'设置领域迁移测试，并单独评价检索器与控制器。','evidence_ids':['demo-atlas-e3','demo-reflect-e3']}]}}
# Original mathematical teaching example, explicitly separate from real papers.
paper=papers[0]
pid=paper['id']
theory_texts=[
    ('definition','Definition 1 · 证据召回率','设相关证据集合 R 非空，检索集合为 S，定义召回率为 |R ∩ S| / |R|。',[], 'Definition 1. For a nonempty set R of relevant evidence and a retrieved set S, recall is |R intersection S| / |R|.'),
    ('lemma','Lemma 1 · 交集单调性','若 S ⊆ T，则 R ∩ S ⊆ R ∩ T。',['S ⊆ T'],'Lemma 1. If S is a subset of T, then R intersection S is a subset of R intersection T. Proof: any element in R intersection S belongs to R and S, hence to R and T.'),
    ('theorem','Theorem 1 · 召回率单调性','在相关证据集合固定且非空、S ⊆ T 时，扩大检索集合不会降低该定义下的召回率。',['R 固定且非空','S ⊆ T'],'Theorem 1. For fixed nonempty R and S subset T, recall(S) <= recall(T). Proof: Lemma 1 gives |R intersection S| <= |R intersection T|. Divide by the positive |R| and apply Definition 1. This says nothing about precision or answer accuracy.'),
]
nodes=[]
for i,(kind,label,statement,conditions,text) in enumerate(theory_texts):
    ref=pid+'-theory-e'+str(i)
    paper['evidence'].append({'id':ref,'paper_id':pid,'text':text,'page':5,'section':'原创数学教学样例 · 非真实论文'})
    nodes.append({'id':pid+'-theory-'+str(i),'kind':kind,'label':label,'statement':statement,'conditions':conditions,'evidence_ids':[ref]})
paper['theory']={'status':'ready','nodes':nodes,'edges':[
    {'source':nodes[i]['id'],'target':nodes[2]['id'],'explanation':'原创教学证明显式使用'+nodes[i]['label'],'evidence_ids':nodes[2]['evidence_ids']} for i in [0,1]
], 'learning_paths':{nodes[0]['id']:[nodes[0]['id']],nodes[1]['id']:[nodes[1]['id']],nodes[2]['id']:[n['id'] for n in nodes]},'warnings':[]}
for paper in papers[1:]:
    paper['theory']={'status':'ready','nodes':[],'edges':[],'learning_paths':{},'warnings':[]}
Path('public').mkdir(exist_ok=True)
Path('public/demo.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
