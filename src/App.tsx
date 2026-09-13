import EvidenceText from './LazyEvidenceText';
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  lazy,
  Suspense,
} from "react";
import {
  BookOpen,
  Network,
  Table2,
  Clock3,
  Lightbulb,
  Upload,
  Download,
  Plus,
  Search,
  ArrowUpRight,
  ChevronRight,
  Check,
  AlertTriangle,
  Trash2,
  PanelLeftClose,
  PanelLeftOpen,
  X,
  Pencil,
  RotateCcw,
  FileText,
  Layers,
  ShieldCheck,
  Loader2,
  ExternalLink,
  History,
  FolderOpen,
} from "lucide-react";
import { api, localDemo, download, matrixMarkdown, localReport } from "./api";
import ontologyData from "../backend/ontology.json";
import { useResearchTools } from "./webmcp";
import type { TutorSeed } from './Tutor';
import type {
  Claim,
  Config,
  Evidence,
  Field,
  Job,
  Paper,
  Status,
  Tag,
} from "./types";
const Graph = lazy(() => import("./Graph"));
const Tutor = lazy(() => import('./Tutor'));
const statuses: Record<Status, string> = {
  supported: "有据支持",
  partial: "部分支持",
  unsupported: "缺少支持",
  unverified: "待核验",
};
const fields: Record<Field, string> = {
  methods: "核心方法",
  advantages: "方法优势",
  limitations: "作者局限",
  future_work: "作者未来工作",
};
const tabs = [
  { id: "matrix", label: "对比矩阵", icon: Table2 },
  { id: "papers", label: "论文详情", icon: BookOpen },
  { id: "timeline", label: "技术时间轴", icon: Clock3 },
  { id: "graph", label: "方法图谱", icon: Network },
  { id: "directions", label: "研究方向", icon: Lightbulb },
];
function Badge({ status }: { status: Status }) {
  return (
    <span className={"badge " + status}>
      {status === "supported" ? (
        <Check size={12} />
      ) : (
        <AlertTriangle size={12} />
      )}{" "}
      {statuses[status]}
    </span>
  );
}
function flatten(nodes: Tag[]): Tag[] {
  return nodes.flatMap((n) => [n, ...flatten(n.children || [])]);
}
export default function App() {
  const [sidebarHidden,setSidebarHidden]=useState(false);
  const [tutorOpen,setTutorOpen]=useState(false);
  const [tutorSeed,setTutorSeed]=useState<TutorSeed>();
  const [tutorKey,setTutorKey]=useState(0);
  function askTutor(seed?:TutorSeed){setTutorSeed(seed);setTutorKey(k=>k+1);setTutorOpen(true);}
  const [config, setConfig] = useState<Config | null>(null),
    [connected, setConnected] = useState(false),
    [job, setJob] = useState<Job | null>(null);
  const [tab, setTab] = useState("matrix"),
    [query, setQuery] = useState(""),
    [filter, setFilter] = useState("all"),
    [tags, setTags] = useState<Tag[]>(
      flatten([...ontologyData.tasks, ...ontologyData.methods]),
    );
  const [evidenceIds, setEvidenceIds] = useState<string[] | null>(null),
    [uploadOpen, setUploadOpen] = useState(false),
    [files, setFiles] = useState<File[]>([]),
    [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [historyOpen, setHistoryOpen] = useState(false),
    [history, setHistory] = useState<
      { id: string; stage: string; status: string; created: number }[]
    >([]);
  const [editing, setEditing] = useState<{
      paper: Paper;
      field: Field;
      claim: Claim;
    } | null>(null),
    [editText, setEditText] = useState(""),
    [editRefs, setEditRefs] = useState<string[]>([]),
    [editKind, setEditKind] = useState<"author_statement" | "human_note">(
      "author_statement",
    );
  const [revisionLog, setRevisionLog] = useState<
    { paper: string; created: number; before: Paper; after: Paper }[] | null
  >(null);
  const input = useRef<HTMLInputElement>(null),
    started = useRef(false);
  const showEvidence = useCallback((ids: string[]) => setEvidenceIds(ids), []);
  useResearchTools(job, tab, setTab);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    (async () => {
      try {
        const c = await api<Config>("/session");
        setConfig(c);
        setConnected(true);
        const ontology = await api<{ methods: Tag[]; tasks: Tag[] }>(
          "/ontology",
        );
        setTags(flatten([...ontology.tasks, ...ontology.methods]));
        const jobs = await api<{ id: string }[]>("/jobs");
        if (jobs.length) {
          setJob(await api<Job>("/jobs/" + jobs[0].id));
          return;
        }
        const demo = await api<{ id: string }>("/jobs/demo", {
          method: "POST",
        });
        setJob(await api<Job>("/jobs/" + demo.id));
      } catch {
        setConnected(false);
        try {
          setJob(await localDemo());
        } catch (e) {
          setError(String(e));
        }
      }
    })();
  }, []);
  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status)) return;
    const timer = setInterval(
      () =>
        api<Job>("/jobs/" + job.id)
          .then(setJob)
          .catch((e) => setError(e.message)),
      2000,
    );
    return () => clearInterval(timer);
  }, [job?.id, job?.status]);
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 5000);
    return () => clearTimeout(timer);
  }, [notice]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setEvidenceIds(null);
        setUploadOpen(false);
        setEditing(null);
        setHistoryOpen(false);
        setRevisionLog(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  const result = job?.result,
    papers = result?.papers || [],
    synthesis = result?.synthesis;
  const filtered = papers.filter(
    (p) =>
      (
        p.metadata.title +
        " " +
        p.extraction.method_name +
        " " +
        p.classification.method_ids.join(" ")
      )
        .toLowerCase()
        .includes(query.toLowerCase()) &&
      (filter === "all" || p.classification.method_ids.includes(filter)),
  );
  const evidence: Evidence[] = papers.flatMap((p) => p.evidence);
  const selectedEvidence =
    evidenceIds === null
      ? []
      : evidence.filter((e) => evidenceIds.includes(e.id));
  const active = !!job && ["queued", "running"].includes(job.status);
  const tagLabel = (id: string) =>
    tags.find((t) => t.id === id)?.label || id.split(".").at(-1);
  const doAction = async (action: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  const loadDemo = () =>
    doAction(async () => {
      if (connected) {
        const data = await api<{ id: string }>("/jobs/demo", {
          method: "POST",
        });
        setJob(await api<Job>("/jobs/" + data.id));
      } else setJob(await localDemo());
      setQuery("");
      setFilter("all");
      setTab("matrix");
      setNotice("已打开原创教学样例，非真实论文分析。");
    });
  const upload = () =>
    doAction(async () => {
      if (!files.length || !consent) return;
      const form = new FormData();
      files.forEach((f) => form.append("files", f));
      const data = await api<{ id: string; reused: boolean }>("/jobs", {
        method: "POST",
        body: form,
      });
      setJob(await api<Job>("/jobs/" + data.id));
      setUploadOpen(false);
      setFiles([]);
      setConsent(false);
      setQuery("");
      setFilter("all");
      setNotice(
        data.reused ? "已复用相同文件的现有任务。" : "论文已加入处理队列。",
      );
    });
  const addFiles = (selected: FileList | null) => {
    if (!selected) return;
    const next = [...files];
    for (const file of Array.from(selected)) {
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        setError("请只上传 PDF 文件。");
        continue;
      }
      if (file.size > (config?.max_file_mb || 30) * 1024 * 1024) {
        setError("文件超过单篇大小限制。");
        continue;
      }
      if (!next.some((f) => f.name === file.name && f.size === file.size))
        next.push(file);
    }
    if (next.length > (config?.max_files || 8)) {
      setError("每次最多上传 8 篇论文。");
      return;
    }
    setFiles(next);
  };
  const edit = (paper: Paper, field: Field, claim: Claim) => {
    setEditing({ paper, field, claim });
    setEditText(claim.text);
    setEditRefs([...claim.evidence_ids]);
    setEditKind(
      claim.kind === "human_note" ? "human_note" : "author_statement",
    );
  };
  const saveEdit = () =>
    doAction(async () => {
      if (!editing || !job) return;
      if (!editText.trim()) throw new Error("内容不能为空。");
      if (editKind === "author_statement" && !editRefs.length)
        throw new Error("作者陈述至少需要一条原文证据。");
      if (job.id === "local-demo") {
        const next = structuredClone(job);
        const p = next.result!.papers.find((p) => p.id === editing.paper.id)!;
        let c = p.extraction[editing.field].find(
          (c) => c.id === editing.claim.id,
        );
        if (!c && editing.claim.id === "new") {
          c = { ...editing.claim, id: "local-" + crypto.randomUUID() };
          p.extraction[editing.field].push(c);
        }
        if (!c) throw new Error("未找到字段，请刷新页面。");
        Object.assign(c, {
          text: editText,
          evidence_ids: editRefs,
          kind: editKind,
          status: "unverified",
          reason: "本地示例修改，未经模型核验。",
        });
        p.revision++;
        next.stale = 1;
        setJob(next);
        setNotice("修改仅保留在当前页面；示例不模拟模型重算。");
      } else {
        setJob(
          await api<Job>(`/jobs/${job.id}/papers/${editing.paper.id}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              revision: editing.paper.revision,
              field: editing.field,
              claim_id: editing.claim.id,
              text: editText,
              evidence_ids: editRefs,
              kind: editKind,
            }),
          }),
        );
        setNotice("已保存新版本，聚合结果待重新推导。");
      }
      setEditing(null);
    });
  const regenerate = () =>
    doAction(async () => {
      if (!job) return;
      await api("/jobs/" + job.id + "/regenerate", { method: "POST" });
      setJob(await api<Job>("/jobs/" + job.id));
    });
  const exportAll = () =>
    doAction(async () => {
      if (!job?.result) return;
      if (job.id === "local-demo")
        download("论文方法梳理报告.md", localReport(job));
      else {
        const response = await fetch("/api/jobs/" + job.id + "/report");
        if (!response.ok) throw new Error("报告导出失败。");
        download("论文方法梳理报告.md", await response.text());
      }
      setNotice("已导出含原文证据的 Markdown 报告。");
    });
  const openHistory = () =>
    doAction(async () => {
      if (!connected) {
        setNotice("在线静态示例不保存任务历史。");
        return;
      }
      setHistory(await api("/jobs"));
      setHistoryOpen(true);
    });
  function ClaimView({
    claim,
    paper,
    field,
  }: {
    claim: Claim;
    paper: Paper;
    field: Field;
  }) {
    return (
      <div
        className={"claim " + (claim.status !== "supported" ? "flagged" : "")}
      >
        <p>{claim.text}</p>
        <div className="claim-meta">
          <Badge status={claim.status} />
          <button
            className="evidence-link"
            onClick={() => showEvidence(claim.evidence_ids)}
          >
            <BookOpen size={13} /> {claim.evidence_ids.length} 条证据
          </button>
          <button
            className="icon-button edit-button"
            title="编辑并保留版本"
            aria-label="编辑结论"
            disabled={active}
            onClick={() => edit(paper, field, claim)}
          >
            <Pencil size={13} />
          </button>
          <button className="evidence-link" onClick={()=>askTutor({paperIds:[paper.id],evidenceIds:claim.evidence_ids.slice(0,8),question:'请解释这段结论：'+claim.text})}>问助教</button>
        </div>
        {claim.kind === "human_note" && <small>人工备注</small>}
      </div>
    );
  }
  const modal = uploadOpen || editing || historyOpen || revisionLog;
  useEffect(() => {
    if (!modal && evidenceIds === null) return;
    const previous = document.activeElement as HTMLElement | null;
    const root = document.querySelector<HTMLElement>(
      modal ? ".modal" : ".evidence-drawer",
    );
    const selector =
      "button:not(:disabled),a[href],input:not(:disabled),textarea,select";
    root?.querySelector<HTMLElement>(selector)?.focus();
    const trap = (event: KeyboardEvent) => {
      if (event.key !== "Tab" || !root) return;
      const nodes = [...root.querySelectorAll<HTMLElement>(selector)].filter(
        (n) => n.offsetParent !== null,
      );
      const first = nodes[0],
        last = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", trap);
    return () => {
      document.removeEventListener("keydown", trap);
      previous?.focus();
    };
  }, [!!modal, evidenceIds !== null]);
  return (
    <div className={'app-shell'+(tutorOpen?' tutor-active':'')+(sidebarHidden?' sidebar-hidden':'')}>
      {sidebarHidden && <button className="sidebar-restore icon-button" aria-label="展开侧边栏" title="展开侧边栏" onClick={()=>setSidebarHidden(false)}><PanelLeftOpen size={20}/></button>}
      <aside className="sidebar">
        <button className="sidebar-collapse icon-button" aria-label="隐藏侧边栏" title="隐藏侧边栏" onClick={()=>setSidebarHidden(true)}><PanelLeftClose size={20}/></button>
        <a className="brand" href="#" onClick={(e) => e.preventDefault()}>
          <div className="brand-mark">
            <Layers size={25} />
          </div>
          <div>
            <strong>研脉</strong>
            <small>PAPER METHOD AGENT</small>
          </div>
        </a>
        <div className="workspace-label">研究工作空间</div>
        <button className="nav-item selected" onClick={() => setTab("matrix")}>
          <FolderOpen size={18} /> 论文方法梳理 <ChevronRight size={14} />
        </button>
        <button className="nav-item" onClick={openHistory}>
          <History size={18} /> 分析历史
        </button>
        <div className="sidebar-divider" />
        <div className="workspace-label">当前研究领域</div>
        <div className="domain-card">
          <span className="domain-icon">
            <Network size={19} />
          </span>
          <div>
            <strong>检索增强生成</strong>
            <small>RAG · 本体 v1.0</small>
          </div>
        </div>
        <p className="side-copy">
          限定分类，保留原文依据。
          <br />
          每一次推导，都有迹可循。
        </p>
        <div className="sidebar-bottom">
          <div className="agent-stack">
            <ShieldCheck size={19} />
            <div>
              <strong>4 + 1 分层流水线</strong>
              <small>抽取 · 分类 · 推导 · 核验</small>
            </div>
          </div>
          <span>MIT 开源 · MinerU 文档解析</span>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            研究工作空间 <ChevronRight size={14} />
            <strong>方法分析</strong>
          </div>
          <button className="button secondary tutor-open-button" disabled={!job?.result?.papers.length} onClick={()=>tutorOpen?setTutorOpen(false):askTutor()}><BookOpen size={16}/>论文助教</button>
          <button className="text-button" onClick={loadDemo}>
            <BookOpen size={15} /> 打开教学示例
          </button>
        </header>
        <main>
          <div className="page-heading">
            <div>
              <div className="eyebrow">EVIDENCE-BASED RESEARCH</div>
              <h1>
                从论文中，读懂方法的脉络<span>。</span>
              </h1>
              <p>对比研究方法，追溯原文依据，探索可验证的下一步。</p>
            </div>
            <div className="heading-actions">
              <button
                className="button secondary"
                disabled={!result || busy}
                onClick={exportAll}
              >
                <Download size={16} />
                导出报告
              </button>
              <button
                className="button primary"
                onClick={() => {
                  setError("");
                  setUploadOpen(true);
                }}
              >
                <Plus size={17} />
                新建分析
              </button>
            </div>
          </div>
          {error && (
            <div className="alert error" role="alert">
              <AlertTriangle size={17} />
              <span>{error}</span>
              <button
                className="icon-button"
                onClick={() => setError("")}
                aria-label="关闭错误"
              >
                <X size={16} />
              </button>
            </div>
          )}
          {notice && (
            <div className="toast" role="status">
              <Check size={16} />
              {notice}
            </div>
          )}
          {result?.mode === "demo" && (
            <div className="demo-banner">
              <span className="demo-label">教学示例</span>
              <span>
                5
                篇原创虚构文档，用于体验分析流程；所有方法和证据均为样例，不可作为科研引用。
              </span>
              <button onClick={() => setUploadOpen(true)}>
                分析我的论文 <ArrowUpRight size={14} />
              </button>
            </div>
          )}
          {active && (
            <div className="alert processing" role="status">
              <Loader2 className="spin" size={17} />
              <span>
                {job?.stage} · 已完成 {papers.length} 篇，可离开页面后回来查看。
              </span>
            </div>
          )}
          {job?.error && (
            <div className="alert error">
              <AlertTriangle size={17} />
              <span>{job.error}</span>
              <button
                className="text-button"
                onClick={regenerate}
                disabled={busy}
              >
                重试
              </button>
            </div>
          )}
          {!!job?.stale && (
            <div className="alert warning">
              <AlertTriangle size={17} />
              <span>论文已修正，当前演进与研究方向基于旧版本。</span>
              <button
                className="text-button"
                onClick={regenerate}
                disabled={busy || active || result?.mode === "demo"}
              >
                <RotateCcw size={14} />
                重新推导
              </button>
              {result?.mode === "demo" && <small>示例模式不执行模型重算</small>}
            </div>
          )}
          {result?.failures.map((f) => (
            <div className="alert error" key={f.filename}>
              <FileText size={16} />
              <span>
                {f.filename}：{f.message}
              </span>
            </div>
          ))}
          <div className="stats">
            <div className="stat">
              <span>
                <FileText size={17} /> 已分析论文
              </span>
              <div>
                <strong>{papers.length.toString().padStart(2, "0")}</strong>
                <small>/ 08 篇上限</small>
              </div>
            </div>
            <div className="stat">
              <span>
                <Network size={17} /> 核心研究方法
              </span>
              <div>
                <strong>{papers.length.toString().padStart(2, "0")}</strong>
                <small>方法实例</small>
              </div>
            </div>
            <div className="stat">
              <span>
                <BookOpen size={17} /> 原文证据块
              </span>
              <div>
                <strong>{evidence.length.toString().padStart(2, "0")}</strong>
                <small>可追溯来源</small>
              </div>
            </div>

          </div>
          <section className="analysis-panel">
            <div className="tabs" role="tablist" aria-label="分析视图">
              {tabs.map((t) => (
                <button
                  key={t.id}
                  role="tab"
                  aria-selected={tab === t.id}
                  className={tab === t.id ? "active" : ""}
                  onClick={() => setTab(t.id)}
                >
                  <t.icon size={17} />
                  {t.label}
                  {t.id === "directions" && (
                    <span className="count">
                      {synthesis?.directions.length || 0}
                    </span>
                  )}
                </button>
              ))}
            </div>
            <div className="toolbar">
              <div className="search-box">
                <Search size={16} />
                <input
                  aria-label="搜索论文或方法"
                  placeholder="搜索论文、方法关键词…"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
                {query && (
                  <button
                    className="icon-button"
                    onClick={() => setQuery("")}
                    aria-label="清除搜索"
                  >
                    <X size={14} />
                  </button>
                )}
              </div>
              <select
                aria-label="筛选方法类别"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              >
                <option value="all">全部方法类别</option>
                {Array.from(
                  new Set(papers.flatMap((p) => p.classification.method_ids)),
                ).map((id) => (
                  <option key={id} value={id}>
                    {tagLabel(id)}
                  </option>
                ))}
              </select>
              <span className="toolbar-count">{filtered.length} 篇论文</span>
              {tab === "matrix" && (
                <button
                  className="text-button"
                  onClick={() =>
                    result &&
                    download(
                      "论文对比矩阵.md",
                      matrixMarkdown({ ...result, papers: filtered }),
                    )
                  }
                  disabled={!result}
                >
                  <Download size={15} />
                  导出矩阵
                </button>
              )}
            </div>
            {!job ? (
              <div className="empty">
                <Loader2 size={28} className="spin" />
                <h3>正在准备研究工作空间</h3>
              </div>
            ) : papers.length === 0 ? (
              <div className="empty">
                <FileText size={38} />
                <h3>{active ? "论文正在处理中" : "还没有分析结果"}</h3>
                <p>
                  {active
                    ? "单篇处理完成后将逐步显示，失败不会清空其他结果。"
                    : "上传 PDF 或打开教学示例，开始梳理研究方法。"}
                </p>
              </div>
            ) : filtered.length === 0 ? (
              <div className="empty">
                <Search size={32} />
                <h3>没有匹配的论文</h3>
                <button
                  className="text-button"
                  onClick={() => {
                    setQuery("");
                    setFilter("all");
                  }}
                >
                  清除筛选条件
                </button>
              </div>
            ) : (
              <>
                {tab === "matrix" && (
                  <div className="table-scroll">
                    <table className="comparison">
                      <thead>
                        <tr>
                          <th className="paper-column">论文 / 方法</th>
                          <th>核心方法</th>
                          <th>方法优势</th>
                          <th className="limit-heading">
                            作者原文局限 <ShieldCheck size={13} />
                          </th>
                          <th>数据集 / 指标</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filtered.map((p, i) => (
                          <tr key={p.id}>
                            <td>
                              <div className="paper-number">
                                {String(i + 1).padStart(2, "0")}
                                <span>{p.metadata.year || "未知年份"}</span>
                              </div>
                              <button
                                className="paper-title"
                                onClick={() => {
                                  setQuery(p.metadata.title);
                                  setTab("papers");
                                }}
                              >
                                {p.metadata.title}
                                <ArrowUpRight size={14} />
                              </button>
                              <div className="tag-list">
                                {p.classification.method_ids.map((id) => (
                                  <span key={id}>{tagLabel(id)}</span>
                                ))}
                              </div>
                              <small className="version">
                                {result?.mode === "demo"
                                  ? "原创教学样例"
                                  : "原文抽取"}{" "}
                                · v{p.revision}
                              </small>
                            </td>
                            {(
                              [
                                "methods",
                                "advantages",
                                "limitations",
                              ] as Field[]
                            ).map((field) => (
                              <td key={field}>
                                {p.extraction[field].length ? (
                                  p.extraction[field].map((c) => (
                                    <ClaimView
                                      key={c.id}
                                      claim={c}
                                      paper={p}
                                      field={field}
                                    />
                                  ))
                                ) : (
                                  <span className="missing">
                                    未找到明确陈述
                                  </span>
                                )}
                              </td>
                            ))}
                            <td>
                              {p.extraction.evaluations.length ? (
                                p.extraction.evaluations.map((e, i) => (
                                  <div className="evaluation" key={i}>
                                    <strong>{e.dataset}</strong>
                                    <span>
                                      {e.metric}
                                      {e.value && " · " + e.value}
                                    </span>
                                    <small>{e.setting}</small>
                                    <button
                                      className="evidence-link"
                                      onClick={() =>
                                        showEvidence(e.evidence_ids)
                                      }
                                    >
                                      查看依据
                                    </button>
                                  </div>
                                ))
                              ) : (
                                <span className="missing">
                                  未抽取到明确数据
                                  <br />
                                  <small>保留空值，不推测补全</small>
                                </span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                {tab === "papers" && (
                  <div className="paper-grid">
                    {filtered.map((p) => (
                      <article className="paper-card" key={p.id}>
                        <div className="paper-card-top">
                          <span className="year-pill">
                            {p.metadata.year || "年份未知"}
                          </span>
                          <span className="version">修订 v{p.revision}</span>
                        </div>
                        <h2>{p.metadata.title}</h2>
                        <button className="evidence-link" onClick={()=>askTutor({paperIds:[p.id]})}>向助教提问 <ChevronRight size={14}/></button>
                        <p className="paper-authors">
                          {p.metadata.authors.join(" · ")}
                        </p>
                        <p className="paper-venue">
                          {p.metadata.venue || "未找到会议 / 期刊"}
                        </p>
                        <button
                          className="evidence-link"
                          onClick={() => showEvidence(p.metadata.evidence_ids)}
                        >
                          元信息依据 <ArrowUpRight size={13} />
                        </button>
                        <div className="tag-list">
                          {p.classification.method_ids.map((id) => (
                            <span key={id}>{tagLabel(id)}</span>
                          ))}
                        </div>
                        {p.warnings.filter(w => !/^(eval-\d+|metadata|classification) 待确认[：:]/.test(w)).map((w, i) => (
                          <p className="inline-warning" key={i}>
                            {w}
                          </p>
                        ))}
                        {(Object.keys(fields) as Field[]).map((f) => (
                          <section className="detail-section" key={f}>
                            <h3>{fields[f]}</h3>
                            {p.extraction[f].length ? (
                              p.extraction[f].map((c) => (
                                <ClaimView
                                  key={c.id}
                                  claim={c}
                                  paper={p}
                                  field={f}
                                />
                              ))
                            ) : (
                              <div>
                                <p className="missing">未找到作者明确陈述</p>
                                <button
                                  className="evidence-link"
                                  disabled={active}
                                  onClick={() =>
                                    edit(p, f, {
                                      id: "new",
                                      text: "",
                                      evidence_ids: [],
                                      kind: "author_statement",
                                      status: "unverified",
                                      reason: "",
                                    })
                                  }
                                >
                                  <Plus size={13} />
                                  手动补充并关联证据
                                </button>
                              </div>
                            )}
                          </section>
                        ))}
                        <section className="detail-section">
                          <h3>数据集与指标</h3>
                          {p.extraction.evaluations.length ? (
                            p.extraction.evaluations.map((e, i) => (
                              <p key={i}>
                                {e.dataset} · {e.metric} ·{" "}
                                {e.value || "数值未知"}
                                <br />
                                {e.setting}
                                <button
                                  className="evidence-link"
                                  onClick={() => showEvidence(e.evidence_ids)}
                                >
                                  原文依据
                                </button>
                              </p>
                            ))
                          ) : (
                            <p className="missing">未抽取到明确数据</p>
                          )}
                        </section>
                      </article>
                    ))}
                  </div>
                )}
                {tab === "timeline" && (
                  <div className="timeline-view">
                    <div className="view-note">
                      <Clock3 size={16} />
                      按论文发表年份排列；先后顺序不代表继承关系。
                    </div>
                    <div className="timeline">
                      {[...filtered]
                        .sort(
                          (a, b) =>
                            (a.metadata.year ?? 9999) -
                            (b.metadata.year ?? 9999),
                        )
                        .map((p) => (
                          <article className="timeline-item" key={p.id}>
                            <div className="timeline-year">
                              {p.metadata.year || "未知"}
                            </div>
                            <div className="timeline-dot" />
                            <div className="timeline-card">
                              <span className="eyebrow">
                                {p.extraction.method_name}
                              </span>
                              <h2>{p.metadata.title}</h2>
                              {p.extraction.methods.map((c) => (
                                <p key={c.id}>{c.text}</p>
                              ))}
                              <div className="tag-list">
                                {p.classification.method_ids.map((id) => (
                                  <span key={id}>{tagLabel(id)}</span>
                                ))}
                              </div>
                              <button
                                className="evidence-link"
                                onClick={() =>
                                  showEvidence(
                                    p.extraction.methods.flatMap(
                                      (c) => c.evidence_ids,
                                    ),
                                  )
                                }
                              >
                                查看原文证据 <ArrowUpRight size={14} />
                              </button>
                            </div>
                          </article>
                        ))}
                    </div>
                  </div>
                )}
                {tab === "graph" && (
                  <div className="graph-view">
                    <div className="view-note">
                      <Network size={16} />
                      仅展示有据支持的方法关系。点击节点或连线查看证据；孤立节点表示尚无明确关系。
                    </div>
                    <Suspense
                      fallback={<div className="empty">正在加载图谱…</div>}
                    >
                      <Graph
                        papers={filtered}
                        synthesis={synthesis || null}
                        onEvidence={showEvidence}
                      />
                    </Suspense>
                    <div className="relation-list">
                      {synthesis?.relations
                        .filter(
                          (r) =>
                            filtered.some((p) => p.id === r.source) &&
                            filtered.some((p) => p.id === r.target),
                        )
                        .map((r, i) => (
                          <button
                            key={i}
                            onClick={() => showEvidence(r.evidence_ids)}
                          >
                            <Network size={16} />
                            <span>
                              {
                                papers.find((p) => p.id === r.source)
                                  ?.extraction.method_name
                              }{" "}
                              →{" "}
                              {
                                papers.find((p) => p.id === r.target)
                                  ?.extraction.method_name
                              }
                              <small>{r.scope}</small>
                            </span>
                            <ArrowUpRight size={15} />
                          </button>
                        ))}
                    </div>
                  </div>
                )}
                {tab === "directions" && (
                  <div className="directions-view">
                    <div className="view-note">
                      <Lightbulb size={17} />
                      本视图聚合本批次全部 {papers.length}{" "}
                      篇论文。研究方向是待验证假设；不代表创新性或实验有效性已被确认。
                    </div>
                    {!synthesis ? (
                      <div className="empty">聚合推导尚未完成。</div>
                    ) : (
                      <>
                        <div className="synthesis-summary">
                          <span className="eyebrow">方法演进观察</span>
                          {synthesis.summary.map((c) => (
                            <div key={c.id}>
                              <p>{c.text}</p>
                              <Badge status={c.status} />
                              <button
                                className="evidence-link"
                                onClick={() => showEvidence(c.evidence_ids)}
                              >
                                查看依据
                              </button>
                            </div>
                          ))}
                        </div>
                        <div className="direction-grid">
                          {synthesis.directions.map((d, i) => (
                            <article className="direction-card" key={d.id}>
                              <div className="direction-top">
                                <span>
                                  研究假设 {String(i + 1).padStart(2, "0")}
                                </span>
                                <Badge status={d.status} />
                              </div>
                              <h2>{d.title}</h2>
                              <p>{d.problem}</p>
                              <div className="hypothesis">{d.hypothesis}</div>
                              <dl>
                                <dt>推导依据</dt>
                                <dd>{d.reasoning}</dd>
                                <dt>最小验证实验</dt>
                                <dd>{d.experiment}</dd>
                                <dt>可能失败条件</dt>
                                <dd>{d.failure_condition}</dd>
                              </dl>
                              <p className="muted">{d.reason}</p>
                              <button
                                className="evidence-link"
                                onClick={() => showEvidence(d.evidence_ids)}
                              >
                                <BookOpen size={14} />
                                {d.evidence_ids.length} 条原文依据{" "}
                                <ArrowUpRight size={14} />
                              </button>
                            </article>
                          ))}
                        </div>
                        <h2 className="section-heading">
                          方法—共性缺陷—改进思路
                        </h2>
                        <div className="table-scroll">
                          <table className="gap-table">
                            <thead>
                              <tr>
                                <th>研究方法</th>
                                <th>共性问题</th>
                                <th>改进思路</th>
                                <th>依据</th>
                              </tr>
                            </thead>
                            <tbody>
                              {synthesis.common_gaps.map((g, i) => (
                                <tr key={i}>
                                  <td>{g.method}</td>
                                  <td>{g.limitation}</td>
                                  <td>{g.idea}</td>
                                  <td>
                                    <button
                                      className="evidence-link"
                                      onClick={() =>
                                        showEvidence(g.evidence_ids)
                                      }
                                    >
                                      查看证据
                                    </button>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          {!synthesis.common_gaps.length && (
                            <p className="missing">
                              本批次尚无足够证据支持共性缺陷。
                            </p>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                )}
              </>
            )}
            <div className="panel-footer">
              <span>
                <ShieldCheck size={14} />
                作者局限保留原意 · 空缺不补编
              </span>
              <span>
                {result?.mode === "demo"
                  ? "示例数据 · 外部调用 0 次"
                  : `模型调用 ${job?.calls || 0} 次 · 缓存命中 ${job?.cache_hits || 0} 次 · Token ${(job?.input_tokens || 0) + (job?.output_tokens || 0)}`}
              </span>
            </div>
          </section>
          <footer className="page-footer">
            <span>研脉 · 论文方法梳理智能体</span>
            <div>
              <button
                onClick={() =>
                  doAction(async () => {
                    if (!job || job.id === "local-demo") {
                      setNotice("本地示例不持久保存修改历史。");
                      return;
                    }
                    setRevisionLog(await api("/jobs/" + job.id + "/revisions"));
                  })
                }
              >
                修订记录
              </button>
              <span>·</span>
              <span>
                {connected
                  ? config?.configured
                    ? "真实分析已配置"
                    : "真实分析待配置"
                  : "独立示例预览"}
              </span>
            </div>
          </footer>
        </main>
      </div>
      {tutorOpen&&job?.result&&<Suspense fallback={<div className="notice">正在打开论文助教…</div>}><Tutor key={job.id+':'+tutorKey} job={job} connected={connected} seed={tutorSeed} onClose={()=>setTutorOpen(false)} onEvidence={showEvidence}/></Suspense>}
      {evidenceIds !== null && (
        <>
          <div className="drawer-scrim" onClick={() => setEvidenceIds(null)} />
          <aside
            className="evidence-drawer"
            role="dialog"
            aria-modal="true"
            aria-label="原文证据"
          >
            <div className="drawer-header">
              <div>
                <span className="eyebrow">SOURCE EVIDENCE</span>
                <h2>让结论回到原文</h2>
              </div>
              <button
                className="icon-button"
                aria-label="关闭证据"
                onClick={() => setEvidenceIds(null)}
              >
                <X size={22} />
              </button>
            </div>
            {result?.mode === "demo" && (
              <div className="inline-warning">
                以下为原创教学样例文本，非已发表论文。
              </div>
            )}
            {!selectedEvidence.length && (
              <p className="empty">没有有效的原文证据，需要人工核验。</p>
            )}
            {selectedEvidence.map((e) => {
              const p = papers.find((p) => p.id === e.paper_id);
              return (
                <article className="evidence-card" key={e.id}>
                  <div className="source-label">
                    <FileText size={15} />
                    <span>{p?.metadata.title}</span>
                  </div>
                  <div className="source-location">
                    {e.page ? `PDF 第 ${e.page} 页` : "页码未知"} · {e.section}
                  </div>
                  <blockquote><EvidenceText text={e.text}/></blockquote>
                  <code>{e.id}</code>
                  <button className="evidence-link" onClick={()=>{setEvidenceIds(null);askTutor({paperIds:[e.paper_id],evidenceIds:[e.id],question:'请讲解这段原文的含义和适用条件。'});}}>请助教讲解这段原文</button>
                  {result?.mode === "live" && (
                    <a
                      className="evidence-link"
                      href={`/api/jobs/${job?.id}/papers/${e.paper_id}/pdf#page=${e.page || 1}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      打开原 PDF <ExternalLink size={13} />
                    </a>
                  )}
                </article>
              );
            })}
            <p className="drawer-footnote">
              引用块来自解析结果；文本支持核验不能替代对论文实验和来源真实性的判断。
            </p>
          </aside>
        </>
      )}
      {modal && (
        <div
          className="modal-scrim"
          onClick={() => {
            if (!busy) {
              setUploadOpen(false);
              setEditing(null);
              setHistoryOpen(false);
              setRevisionLog(null);
            }
          }}
        >
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label={editing ? "人工修正" : "分析操作"}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="modal-close icon-button"
              aria-label="关闭窗口"
              disabled={busy}
              onClick={() => {
                setUploadOpen(false);
                setEditing(null);
                setHistoryOpen(false);
                setRevisionLog(null);
              }}
            >
              <X size={21} />
            </button>
            {error && (
              <div className="alert error" role="alert">
                {error}
              </div>
            )}
            {uploadOpen && (
              <>
                <div className="modal-icon">
                  <Upload size={25} />
                </div>
                <h2>新建论文分析</h2>
                <p className="muted">
                  上传同一研究领域的 PDF，每批最多 {config?.max_files || 8}{" "}
                  篇，每篇 ≤ {config?.max_file_mb || 30} MB /{" "}
                  {config?.max_pages || 50} 页。
                </p>
                {(!connected || !config?.configured) && (
                  <div className="inline-warning">
                    真实分析尚未配置。需要在服务端填写 MinerU 和模型 API
                    密钥后启动；教学示例可直接体验。
                  </div>
                )}
                {config?.configured && !config.worker_online && (
                  <div className="inline-warning">
                    后台 worker 未运行，提交后将等待处理。
                  </div>
                )}
                <div
                  className="dropzone"
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    addFiles(e.dataTransfer.files);
                  }}
                >
                  <Upload size={30} />
                  <strong>拖放 PDF 到这里</strong>
                  <span>或从设备选择论文</span>
                  <button
                    className="button secondary"
                    onClick={() => input.current?.click()}
                  >
                    选择 PDF
                  </button>
                  <input
                    ref={input}
                    type="file"
                    accept="application/pdf,.pdf"
                    multiple
                    hidden
                    onChange={(e) => {
                      addFiles(e.target.files);
                      e.target.value = "";
                    }}
                  />
                </div>
                <div className="file-list">
                  {files.map((f, i) => (
                    <div key={i}>
                      <FileText size={16} />
                      <span>
                        {f.name}
                        <small>{(f.size / 1024 / 1024).toFixed(1)} MB</small>
                      </span>
                      <button
                        className="icon-button"
                        aria-label={"移除 " + f.name}
                        onClick={() =>
                          setFiles(files.filter((_, j) => i !== j))
                        }
                      >
                        <X size={15} />
                      </button>
                    </div>
                  ))}
                </div>
                <label className="checkbox-line">
                  <input
                    type="checkbox"
                    checked={consent}
                    onChange={(e) => setConsent(e.target.checked)}
                  />
                  我有权处理这些文件，并同意将文档发送至 MinerU
                  和配置的模型服务进行分析。
                </label>
                <div className="modal-actions">
                  <button
                    className="button secondary"
                    onClick={() => {
                      setUploadOpen(false);
                      loadDemo();
                    }}
                  >
                    先体验示例
                  </button>
                  <button
                    className="button primary"
                    disabled={
                      !files.length || !consent || !config?.configured || busy
                    }
                    onClick={upload}
                  >
                    {busy ? (
                      <Loader2 size={16} className="spin" />
                    ) : (
                      <Plus size={16} />
                    )}
                    开始分析 {files.length ? `(${files.length})` : ""}
                  </button>
                </div>
              </>
            )}
            {editing && (
              <>
                <div className="modal-icon">
                  <Pencil size={23} />
                </div>
                <h2>修正{fields[editing.field]}</h2>
                <p className="muted">
                  {editing.paper.metadata.title} · v{editing.paper.revision}
                </p>
                <label className="form-label">
                  内容
                  <textarea
                    rows={5}
                    value={editText}
                    maxLength={4000}
                    onChange={(e) => setEditText(e.target.value)}
                  />
                </label>
                <label className="form-label">
                  内容性质
                  <select
                    value={editKind}
                    onChange={(e) =>
                      setEditKind(e.target.value as typeof editKind)
                    }
                  >
                    <option value="author_statement">
                      作者陈述（需要原文证据）
                    </option>
                    <option value="human_note">
                      人工备注（不作为已核验事实）
                    </option>
                  </select>
                </label>
                <div className="form-label">关联本篇原文证据</div>
                <div className="evidence-picker">
                  {editing.paper.evidence.map((e) => (
                    <label key={e.id}>
                      <input
                        type="checkbox"
                        checked={editRefs.includes(e.id)}
                        onChange={(event) =>
                          setEditRefs(
                            event.target.checked
                              ? [...editRefs, e.id]
                              : editRefs.filter((id) => id !== e.id),
                          )
                        }
                      />
                      <span>
                        <strong>
                          {e.section} · 第 {e.page || "?"} 页
                        </strong>
                        <EvidenceText text={e.text}/>
                      </span>
                    </label>
                  ))}
                </div>
                <p className="muted">
                  保存后标记为待核验，并使演进结果过期；不会自动覆盖原文。
                </p>
                <div className="modal-actions">
                  <button
                    className="button secondary"
                    onClick={() => setEditing(null)}
                  >
                    取消
                  </button>
                  <button
                    className="button primary"
                    disabled={busy}
                    onClick={saveEdit}
                  >
                    保存新版本
                  </button>
                </div>
              </>
            )}
            {historyOpen && (
              <>
                <h2>分析历史</h2>
                {error&&<p className="inline-warning" role="alert">{error}</p>}
                <p className="muted">只显示当前浏览器会话的任务。</p>
                {history.length ? (
                  history.map((h) => (
                    <div className="history-entry" key={h.id}><button
                      className="history-row"
                      onClick={() =>
                        doAction(async () => {
                          setJob(await api<Job>("/jobs/" + h.id));
                          setHistoryOpen(false);
                          setQuery("");
                          setFilter("all");
                        })
                      }
                    >
                      <FileText size={20} />
                      <span>
                        <strong>{h.stage}</strong>
                        <small>
                          {new Date(h.created * 1000).toLocaleString("zh-CN")}
                        </small>
                      </span>
                      <ChevronRight size={16} />
                    </button><button className="icon-button history-delete" aria-label={'删除分析历史：'+h.stage} title="删除分析历史" disabled={busy||['queued','running'].includes(h.status)} onClick={()=>{
                      if(!window.confirm('删除这条分析历史及关联的全部助教对话？删除后无法恢复。'))return;
                      void doAction(async()=>{
                        await api('/jobs/'+h.id,{method:'DELETE'});
                        setHistory(items=>items.filter(item=>item.id!==h.id));
                        if(job?.id===h.id){setJob(null);setTutorOpen(false);setEvidenceIds(null);setQuery('');setFilter('all');}
                      });
                    }}><Trash2 size={18}/></button></div>
                  ))
                ) : (
                  <div className="empty">暂无历史分析</div>
                )}
              </>
            )}
            {revisionLog && (
              <>
                <h2>人工修订记录</h2>
                {revisionLog.length ? (
                  revisionLog.map((r, i) => (
                    <article className="revision-entry" key={i}>
                      <strong>{r.after.metadata.title}</strong>
                      <p>
                        v{r.before.revision} → v{r.after.revision} ·{" "}
                        {new Date(r.created * 1000).toLocaleString("zh-CN")}
                      </p>
                      {(Object.keys(fields) as Field[]).flatMap((f) =>
                        r.after.extraction[f]
                          .filter(
                            (c) =>
                              JSON.stringify(c) !==
                              JSON.stringify(
                                r.before.extraction[f].find(
                                  (b) => b.id === c.id,
                                ),
                              ),
                          )
                          .map((c) => (
                            <div key={c.id}>
                              <small>{fields[f]}</small>
                              <del>
                                {
                                  r.before.extraction[f].find(
                                    (b) => b.id === c.id,
                                  )?.text
                                }
                              </del>
                              <p>{c.text}</p>
                            </div>
                          )),
                      )}
                    </article>
                  ))
                ) : (
                  <div className="empty">还没有人工修订</div>
                )}
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
