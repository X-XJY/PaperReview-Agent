import { useEffect, useRef, useState } from "react";
import {
  getDocument,
  GlobalWorkerOptions,
  Util,
  type PDFDocumentProxy,
} from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import type { Evidence } from "./types";
import EvidenceText from "./LazyEvidenceText";
GlobalWorkerOptions.workerSrc = workerUrl;
import { matchingItems } from "./pdfMatch";
type Box = { left: number; top: number; width: number; height: number };
export default function PdfReader({
  jobId,
  evidence,
  title,
  onClose,
}: {
  jobId: string;
  evidence: Evidence;
  title: string;
  onClose: () => void;
}) {
  const [doc, setDoc] = useState<PDFDocumentProxy | null>(null),
    [page, setPage] = useState(evidence.page || 1),
    [zoom, setZoom] = useState(1),
    [width, setWidth] = useState(700),
    [boxes, setBoxes] = useState<Box[]>([]),
    [status, setStatus] = useState("正在打开 PDF…"),
    [error, setError] = useState(""),
    [searching, setSearching] = useState(false),
    [located, setLocated] = useState(evidence.page || 1);
  const canvas = useRef<HTMLCanvasElement>(null),
    frame = useRef<HTMLDivElement>(null),
    dialog = useRef<HTMLElement>(null);
  const searchGeneration = useRef(0);
  useEffect(
    () => () => {
      searchGeneration.current++;
    },
    [],
  );
  async function locate() {
    if (!doc || searching) return;
    const generation = ++searchGeneration.current;
    setSearching(true);
    setError("");
    const plain =
      new DOMParser().parseFromString(
        evidence.text.replace(/\$+/g, ""),
        "text/html",
      ).body.textContent || evidence.text;
    try {
      for (let number = 1; number <= doc.numPages; number++) {
        if (generation !== searchGeneration.current) return;
        setStatus(`正在查找依据：${number} / ${doc.numPages} 页…`);
        const content = await (await doc.getPage(number)).getTextContent();
        if (generation !== searchGeneration.current) return;
        if (
          matchingItems(
            content.items
              .filter((i) => "str" in i)
              .map((i) => ("str" in i ? i.str : "")),
            plain,
          ).length
        ) {
          setLocated(number);
          setPage(number);
          setStatus(`已在第 ${number} 页找到匹配文字。`);
          return;
        }
      }
      setStatus(
        "未找到可可靠匹配的依据文字。扫描页或公式排版可能无法自动匹配，请翻页核对。",
      );
    } catch {
      if (generation === searchGeneration.current)
        setError("查找失败，请重试。");
    } finally {
      if (generation === searchGeneration.current) setSearching(false);
    }
  }
  const url = `/api/jobs/${jobId}/papers/${evidence.paper_id}/pdf`;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialog.current?.querySelector<HTMLButtonElement>("button")?.focus();
    return () => {
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, []);
  useEffect(() => {
    const target = frame.current;
    if (!target) return;
    const obs = new ResizeObserver(() =>
      setWidth(Math.max(220, target.clientWidth - 24)),
    );
    obs.observe(target);
    return () => obs.disconnect();
  }, []);
  useEffect(() => {
    let active = true;
    setError("");
    setDoc(null);
    const task = getDocument({ url, withCredentials: true });
    task.promise
      .then((d) => {
        if (active) {
          setDoc(d);
          setPage(Math.min(d.numPages, evidence.page || 1));
        }
      })
      .catch(() => {
        if (active)
          setError(
            "无法打开原 PDF。请检查会话是否过期，或使用原 PDF 链接重试。",
          );
      });
    return () => {
      active = false;
      void task.destroy();
    };
  }, [url]);
  useEffect(() => {
    if (!doc || !canvas.current) return;
    let active = true;
    let cancel: (() => void) | undefined;
    setError("");
    setBoxes([]);
    setStatus("正在定位原文…");
    (async () => {
      const pdfPage = await doc.getPage(page);
      if (!active) return;
      const base = pdfPage.getViewport({ scale: 1 });
      const viewport = pdfPage.getViewport({
        scale: (width / base.width) * zoom,
      });
      const target = canvas.current!;
      const ratio = Math.min(devicePixelRatio || 1, 2);
      target.width = Math.floor(viewport.width * ratio);
      target.height = Math.floor(viewport.height * ratio);
      target.style.width = viewport.width + "px";
      target.style.height = viewport.height + "px";
      const render = pdfPage.render({
        canvas: target,
        viewport,
        transform: [ratio, 0, 0, ratio, 0, 0],
      });
      cancel = () => render.cancel();
      const content = await pdfPage.getTextContent();
      const items = content.items.filter(
        (item): item is Extract<typeof item, { str: string }> => "str" in item,
      );
      const plain =
        new DOMParser().parseFromString(
          evidence.text.replace(/\$+/g, ""),
          "text/html",
        ).body.textContent || evidence.text;
      const matches = matchingItems(
        items.map((i) => i.str),
        plain,
      );
      const rectangles = matches.map((i) => {
        const item = items[i];
        const t = Util.transform(viewport.transform, item.transform);
        const height = Math.hypot(t[2], t[3]);
        return {
          left: t[4],
          top: t[5] - height,
          width: Math.max(2, item.width * viewport.scale),
          height: height * 1.15,
        };
      });
      await render.promise;
      if (active) {
        setBoxes(rectangles);
        if (rectangles.length && frame.current) {
          frame.current.scrollTop = Math.max(0, rectangles[0].top - 90);
        }
        setStatus(
          rectangles.length
            ? "已高亮本页匹配的原文文字。"
            : items.length
              ? "本页未找到可可靠高亮的文字，请结合依据核对。"
              : "此页没有可读取的文字层，已定位页码；暂无法高亮扫描图像。",
        );
      }
    })().catch((e) => {
      if (active && e?.name !== "RenderingCancelledException")
        setError("此页渲染失败，请重试或打开原 PDF。");
    });
    return () => {
      active = false;
      cancel?.();
    };
  }, [doc, page, width, zoom, evidence]);
  return (
    <section
      ref={dialog}
      className="pdf-reader"
      role="dialog"
      aria-modal="true"
      aria-label="PDF 原文阅读器"
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.stopPropagation();
          onClose();
        }
        if (e.key === "Tab") {
          const controls = Array.from(
            dialog.current?.querySelectorAll<HTMLElement>(
              'button:not(:disabled),a[href],input,select,[tabindex="0"]',
            ) || [],
          );
          if (e.shiftKey && document.activeElement === controls[0]) {
            e.preventDefault();
            controls.at(-1)?.focus();
          } else if (
            !e.shiftKey &&
            document.activeElement === controls.at(-1)
          ) {
            e.preventDefault();
            controls[0]?.focus();
          }
        }
      }}
    >
      <header>
        <strong>{title}</strong>
        <button onClick={onClose} aria-label="关闭 PDF 阅读器">
          关闭
        </button>
      </header>
      <div className="pdf-reader-tools">
        <button
          disabled={!doc || page <= 1}
          onClick={() => setPage((p) => p - 1)}
        >
          上一页
        </button>
        <label>
          页码{" "}
          <input
            type="number"
            min="1"
            max={doc?.numPages || 1}
            value={page}
            onChange={(e) => {
              const n = Number(e.target.value);
              if (doc && Number.isInteger(n) && n >= 1 && n <= doc.numPages)
                setPage(n);
            }}
          />
        </label>
        <span>/ {doc?.numPages || "—"}</span>
        <button
          disabled={!doc || page >= doc.numPages}
          onClick={() => setPage((p) => p + 1)}
        >
          下一页
        </button>
        <label>
          缩放{" "}
          <select
            value={zoom}
            onChange={(e) => setZoom(Number(e.target.value))}
          >
            <option value="1">适合宽度</option>
            <option value="1.25">125%</option>
            <option value="1.5">150%</option>
            <option value="2">200%</option>
          </select>
        </label>
        <button
          disabled={!doc}
          onClick={() => setPage(Math.min(doc!.numPages, located))}
        >
          返回依据页
        </button>
        <button disabled={!doc || searching} onClick={locate}>
          {searching ? "正在查找…" : "跨页查找依据"}
        </button>
        <a href={url + "#page=" + page} target="_blank" rel="noreferrer">
          打开原 PDF
        </a>
      </div>
      <p role={error ? "alert" : "status"}>{error || status}</p>
      <div className="pdf-reader-body">
        <div
          ref={frame}
          className="pdf-pages"
          tabIndex={0}
          aria-label="PDF 页面，可滚动"
        >
          <div className="pdf-page">
            <canvas ref={canvas} aria-label={"PDF 第 " + page + " 页"} />
            {boxes.map((b, i) => (
              <div key={i} className="pdf-highlight" style={b} />
            ))}
          </div>
        </div>
        <aside>
          <strong>本次定位依据</strong>
          <p>
            {evidence.page
              ? "PDF 第 " + evidence.page + " 页"
              : "依据没有页码，可翻页查找"}{" "}
            · {evidence.section}
          </p>
          <EvidenceText text={evidence.text} />
          <small>
            高亮表示 PDF 文字与依据片段匹配，不表示结论已通过事实核验。
          </small>
        </aside>
      </div>
    </section>
  );
}
