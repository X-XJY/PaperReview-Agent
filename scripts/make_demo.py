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
# Each fictional document includes its own explicitly authored teaching proof.
# These simplified models do not assert properties of real neural architectures.
additional_theory = {
    'demo-fusion': [
        ('definition', 'Definition 1 · 加权表示融合', '在同一赋范向量空间中，定义融合表示 h = Σ wᵢhᵢ，其中 wᵢ ≥ 0 且 Σ wᵢ = 1。', ['有限个表示向量', '非负归一化权重'], 'Definition 1. In one normed vector space, a teaching fusion model is h = sum_i w_i h_i, for finitely many nonnegative weights with sum_i w_i = 1. This simplified model is not a description of a real decoder.'),
        ('lemma', 'Lemma 1 · 加权误差上界', '对非负权重，有 ‖Σ wᵢ(hᵢ − h*)‖ ≤ Σ wᵢ‖hᵢ − h*‖。', ['所有向量属于同一赋范向量空间', 'wᵢ ≥ 0'], 'Lemma 1. For nonnegative weights and vectors in the same normed vector space, norm(sum_i w_i(h_i-h*)) <= sum_i w_i norm(h_i-h*). Proof: apply the triangle inequality and positive homogeneity of the norm.'),
        ('theorem', 'Theorem 1 · 融合表示误差界', '若每个表示与目标 h* 的距离至多为 ε，则该加权融合表示与 h* 的距离也至多为 ε。', ['采用 Definition 1 的融合模型', '每个 ‖hᵢ − h*‖ ≤ ε，且 ε ≥ 0'], 'Theorem 1. Under Definition 1, if every norm(h_i-h*) <= epsilon with epsilon >= 0, then norm(h-h*) <= epsilon. Proof: Definition 1 gives h-h* = sum_i w_i(h_i-h*). Lemma 1 bounds its norm by sum_i w_i epsilon = epsilon. This does not guarantee factual accuracy or apply to arbitrary nonlinear decoders.'),
    ],
    'demo-loop': [
        ('definition', 'Definition 1 · 累积证据集合', '定义第 t 轮累积证据 Sₜ，更新规则为 Sₜ₊₁ = Sₜ ∪ Rₜ，其中 Rₜ 为本轮检索结果。', ['证据来自固定有限集合 U', '不删除已经收集的证据'], 'Definition 1. Let U be a fixed finite evidence universe. Starting with S_0 subset U, the teaching retrieval loop updates S_(t+1) = S_t union R_t, where R_t subset U. Previously collected evidence is never removed.'),
        ('lemma', 'Lemma 1 · 新增证据计数', '若 S ⊂ T ⊆ U，则 |T| ≥ |S| + 1。', ['U 有限', 'S 为 T 的真子集'], 'Lemma 1. If S is a strict subset of T and T subset U for finite U, then |T| >= |S| + 1. Proof: T contains all elements of S and at least one element outside S.'),
        ('theorem', 'Theorem 1 · 有限证据扩展上界', '若每个继续执行的更新都至少增加一条新证据，则成功扩展次数最多为 |U| − |S₀|。', ['采用 Definition 1 的累积更新规则', '每次继续更新均满足 Sₜ ⊂ Sₜ₊₁'], 'Theorem 1. Under Definition 1, if every continuing update strictly enlarges S_t, there are at most |U|-|S_0| such updates. Proof: Definition 1 keeps all S_t inside U; Lemma 1 increases cardinality by at least one per update. Thus |S_0|+k <= |U|. No claim is made about answer correctness or loops that keep repeating the same evidence.'),
    ],
    'demo-reflect': [
        ('definition', 'Definition 1 · 检索开销模型', '设候选检索步骤开销 cᵢ ≥ 0，固定策略执行所有步骤；反思策略仅执行集合 A 中的步骤，另支付控制器开销 H ≥ 0。', ['候选步骤有限', '两种策略使用相同的单步检索开销'], 'Definition 1. For finitely many candidate steps with fixed costs c_i >= 0, the baseline cost is B = sum_i c_i. A teaching reflection policy executes subset A and incurs controller overhead H >= 0, so C = H + sum_(i in A) c_i.'),
        ('lemma', 'Lemma 1 · 省略步骤开销分解', '总检索开销等于已选步骤开销与省略步骤开销之和。', ['A 是候选步骤集合的子集'], 'Lemma 1. For a finite index set I and A subset I, sum_(i in I) c_i = sum_(i in A) c_i + sum_(i in I minus A) c_i. Proof: A and its complement partition I into disjoint sets.'),
        ('theorem', 'Theorem 1 · 反思策略节省条件', '当且仅当省略步骤的检索开销之和不小于 H 时，反思策略的总开销不超过固定策略。', ['采用 Definition 1 的成本模型', '计入控制器开销 H'], 'Theorem 1. Under Definition 1, C <= B if and only if sum_(i not in A) c_i >= H. Proof: substituting Definition 1 and the decomposition in Lemma 1 yields B-C = sum_(i not in A) c_i-H. Its nonnegativity is exactly the stated condition. Cost savings alone do not imply preserved answer quality.'),
    ],
    'demo-verify': [
        ('definition', 'Definition 1 · 支持分数阈值集', '对固定的有限陈述集合 Q，给定固定文本支持分数 s(q) ∈ [0,1]，定义通过集合 Aτ = {q ∈ Q : s(q) ≥ τ}。', ['Q 和各陈述分数固定', 'τ ∈ [0,1]'], 'Definition 1. For a fixed finite set Q of statements and fixed textual-support scores s(q) in [0,1], define A_tau = {q in Q: s(q) >= tau}, with tau in [0,1]. Scores measure the teaching checker output, not factual truth.'),
        ('lemma', 'Lemma 1 · 阈值集合包含关系', '若 τ₁ ≤ τ₂，则通过较高阈值的陈述也通过较低阈值。', ['两次筛选使用相同分数'], 'Lemma 1. If tau_1 <= tau_2, every score at least tau_2 is also at least tau_1. Proof: s >= tau_2 >= tau_1 by transitivity of the order on real numbers.'),
        ('theorem', 'Theorem 1 · 通过数量单调性', '在陈述和分数固定时，提高阈值不会增加通过的陈述数量，即 |Aτ₂| ≤ |Aτ₁|。', ['采用 Definition 1 的固定集合与分数', 'τ₁ ≤ τ₂'], 'Theorem 1. Under Definition 1 and tau_1 <= tau_2, |A_(tau_2)| <= |A_(tau_1)|. Proof: Lemma 1 and Definition 1 give A_(tau_2) subset A_(tau_1); finite set cardinality preserves inclusion. This proves only count monotonicity, not better factual correctness or score calibration.'),
    ],
}
for paper in papers[1:]:
    pid = paper['id']
    nodes = []
    for i, (kind, label, statement, conditions, text) in enumerate(additional_theory[pid]):
        ref = f'{pid}-theory-e{i}'
        paper['evidence'].append({'id': ref, 'paper_id': pid, 'text': text, 'page': 5, 'section': '原创数学教学样例 · 非真实论文'})
        nodes.append({'id': f'{pid}-theory-{i}', 'kind': kind, 'label': label, 'statement': statement, 'conditions': conditions, 'evidence_ids': [ref]})
    paper['theory'] = {'status': 'ready', 'nodes': nodes, 'edges': [
        {'source': nodes[i]['id'], 'target': nodes[2]['id'], 'explanation': '原创教学证明显式使用' + nodes[i]['label'], 'evidence_ids': nodes[2]['evidence_ids']} for i in [0, 1]
    ], 'learning_paths': {nodes[0]['id']: [nodes[0]['id']], nodes[1]['id']: [nodes[1]['id']], nodes[2]['id']: [n['id'] for n in nodes]}, 'warnings': []}
# Different proof topologies are authored from the teaching arguments, rather
# than adding decorative edges to make identical diagrams look different.
def add_node(paper, kind, label, statement, conditions, proof):
    index = len(paper['theory']['nodes'])
    ref = f"{paper['id']}-theory-e{index}"
    paper['evidence'].append({'id': ref, 'paper_id': paper['id'], 'text': proof,
                             'page': 5, 'section': '原创数学教学样例 · 非真实论文'})
    paper['theory']['nodes'].append({'id': f"{paper['id']}-theory-{index}",
        'kind': kind, 'label': label, 'statement': statement,
        'conditions': conditions, 'evidence_ids': [ref]})

fusion, loop, reflect, verify = papers[1:]
add_node(fusion, 'assumption', 'Assumption 1 · 单表示误差约束',
         '所有输入表示满足 ‖hᵢ − h*‖ ≤ ε，其中 ε ≥ 0。', ['同一目标表示 h*'],
         'Assumption 1. Every input representation satisfies norm(h_i-h*) <= epsilon, with epsilon >= 0. This is an assumption, not a measured empirical guarantee.')
fusion['evidence'][6]['text'] = fusion['evidence'][6]['text'].replace('if every norm(h_i-h*) <= epsilon with epsilon >= 0', 'if Assumption 1 holds').replace('sum_i w_i epsilon = epsilon', 'sum_i w_i epsilon = epsilon, using Assumption 1')
add_node(fusion, 'corollary', 'Corollary 1 · 精确输入的融合',
         '若所有输入表示都等于 h*，则融合表示也等于 h*。', ['Definition 1 的非负归一化权重'],
         'Corollary 1. If all h_i equal h*, the fused representation equals h*. Proof: apply Theorem 1 with epsilon = 0. A vector at norm distance zero equals h*. This concerns the teaching vector model only.')

# Loop-R demonstrates a chain: model -> per-step growth -> finite bound -> stop.
loop['theory']['nodes'][1].update(statement='在 Definition 1 的累积模型下，每次严格扩展都使 |Sₜ| 至少增加 1。', conditions=['U 有限', '每次继续更新满足 Sₜ ⊂ Sₜ₊₁'])
loop['evidence'][5]['text'] = 'Lemma 1. Under Definition 1, every strict update increases |S_t| by at least one and keeps S_t inside the fixed finite U. Proof: Definition 1 uses union with R_t subset U; a strict update adds at least one previously absent element.'
loop['evidence'][6]['text'] = 'Theorem 1. In the finite cumulative model of Lemma 1, at most |U|-|S_0| strict updates can occur. Proof: Lemma 1 gives |S_k| >= |S_0|+k and S_k subset U, so k <= |U|-|S_0|. Repeated non-expanding retrieval is outside this bound.'
add_node(loop, 'corollary', 'Corollary 1 · 停止规则的轮数界',
         '若首次无新增证据时停止，最多执行 |U| − |S₀| + 1 次检索。', ['每次检索均终止', '首次无新增证据立即停止'],
         'Corollary 1. If each retrieval terminates and the loop stops on its first non-expanding retrieval, at most |U|-|S_0|+1 retrievals execute. Proof: Theorem 1 bounds strict updates by |U|-|S_0|; the stopping rule permits at most one final non-expanding retrieval.')

# Reflect-R forks into two conclusions with different prerequisites.
reflect['theory']['nodes'][1].update(label='Lemma 1 · 总成本差额', statement='在 Definition 1 的模型下，B − C = Σᵢ∉A cᵢ − H。', conditions=['采用 Definition 1 的固定成本模型'])
reflect['evidence'][5]['text'] = 'Lemma 1. Under Definition 1, B-C = sum_(i not in A) c_i-H. Proof: Definition 1 specifies B and C; partition the finite candidate set into A and its complement and subtract.'
reflect['evidence'][6]['text'] = 'Theorem 1. C <= B if and only if sum_(i not in A) c_i >= H. Proof: Lemma 1 gives B-C = sum_(i not in A) c_i-H; C <= B is equivalent to its nonnegativity. No answer-quality guarantee follows.'
add_node(reflect, 'proposition', 'Proposition 1 · 零省略时的额外成本',
         '若不省略任何检索步骤，则反思策略总开销为 B + H。', ['A 等于完整候选步骤集合'],
         'Proposition 1. If A is the entire candidate set, C = B+H. Proof: in Lemma 1 the complement is empty, so B-C = -H. This branch does not require Theorem 1.')
add_node(reflect, 'corollary', 'Corollary 1 · 等成本步骤的节省门槛',
         '若每步检索成本均为 c > 0，省略 k 步即可节省总开销，当且仅当 kc ≥ H。', ['所有步骤成本等于 c > 0', 'k 为省略步骤数量'],
         'Corollary 1. With uniform step cost c > 0 and k omitted steps, C <= B if and only if kc >= H. Proof: substitute sum_(i not in A) c_i = kc into Theorem 1.')

# Verify-R demonstrates split/merge reasoning followed by a corollary.
verify['theory']['nodes'][1].update(statement='采用 Definition 1 的筛选集合时，τ₁ ≤ τ₂ 蕴含 Aτ₂ ⊆ Aτ₁。')
verify['evidence'][5]['text'] = 'Lemma 1. Under Definition 1, if tau_1 <= tau_2 then A_(tau_2) subset A_(tau_1). Proof: Definition 1 admits q exactly when s(q) reaches the threshold; s(q) >= tau_2 implies s(q) >= tau_1.'
add_node(verify, 'lemma', 'Lemma 2 · 阈值区间中的陈述',
         'Aτ₁ 中未通过 τ₂ 的陈述，恰为分数处于 [τ₁, τ₂) 的陈述。', ['Definition 1 的固定分数', 'τ₁ ≤ τ₂'],
         'Lemma 2. Under Definition 1 and tau_1 <= tau_2, A_(tau_1) minus A_(tau_2) = {q in Q: tau_1 <= s(q) < tau_2}. Proof: Definition 1 translates membership and nonmembership into the two score inequalities.')
add_node(verify, 'corollary', 'Corollary 1 · 通过数量的精确变化',
         '提高阈值后减少的通过数量，等于分数位于 [τ₁, τ₂) 的陈述数量。', ['Q 有限', 'τ₁ ≤ τ₂'],
         'Corollary 1. |A_(tau_1)|-|A_(tau_2)| equals the number of q with tau_1 <= s(q) < tau_2. Proof: Lemma 1 gives nested finite sets, so their cardinality difference equals the set-difference cardinality. Lemma 2 identifies that difference with the score interval.')
add_node(verify, 'corollary', 'Corollary 2 · 无区间分数时数量不变',
         '若没有陈述分数位于 [τ₁, τ₂)，提高阈值不会改变通过数量。', ['τ₁ ≤ τ₂', '区间 [τ₁, τ₂) 内无陈述分数'],
         'Corollary 2. If no statement score lies in [tau_1,tau_2), the two thresholds accept the same number of statements. Proof: Corollary 1 gives a cardinality difference of zero. No factual-truth claim is implied.')

connections = {
    'demo-atlas': [(0, 2), (1, 2)],
    'demo-fusion': [(0, 2), (1, 2), (3, 2), (2, 4)],
    'demo-loop': [(0, 1), (1, 2), (2, 3)],
    'demo-reflect': [(0, 1), (1, 2), (1, 3), (2, 4)],
    'demo-verify': [(0, 1), (0, 3), (0, 2), (1, 2), (1, 4), (3, 4), (4, 5)],
}
import sys
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.theory import learning_paths
from backend.schemas import TheoryNode, TheoryEdge
for paper in papers:
    nodes = paper['theory']['nodes']
    edges = [{'source': nodes[a]['id'], 'target': nodes[b]['id'],
              'explanation': nodes[b]['label'] + ' 的原创教学证明使用 ' + nodes[a]['label'],
              'evidence_ids': nodes[b]['evidence_ids']} for a, b in connections[paper['id']]]
    paper['theory']['edges'] = edges
    paper['theory']['learning_paths'] = learning_paths(
        [TheoryNode.model_validate(n) for n in nodes], [TheoryEdge.model_validate(e) for e in edges])
# A rendered teaching PDF places each evidence block on its own numbered page.
for paper in papers:
    for number, evidence in enumerate(paper['evidence'], 1):
        evidence['page'] = number
Path('public').mkdir(exist_ok=True)
Path('public/demo.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
