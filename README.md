# 研脉 · 论文方法梳理智能体

面向计算机科研的多论文方法比较工具。初版聚焦 RAG，支持每批 1—8 篇 PDF，输出带原文证据的论文卡片、对比矩阵、时间轴、方法图谱和待验证研究方向。

**MIT 开源。业务逻辑、Prompt、分类本体、数据结构和教学样例自主实现，未 fork 或复制参考项目完整代码。**

部署与运维见 [Ubuntu 部署文档](docs/DEPLOYMENT.md)，包含 systemd、Nginx、IP HTTPS 和自动续期配置。

## 当前可用功能

- React 工作区：搜索/筛选、论文详情、矩阵、时间轴、力导向图谱、研究方向与证据侧栏。
- 真实接口：MinerU 托管精准解析 → 4+1 结构化 Agent → 证据与标签校验。
- SQLite 持久任务、文件内容哈希缓存、模型阶段缓存、远程解析任务复用、失败恢复。
- 方法/优势/作者局限/未来工作人工修正、版本冲突检查、修订历史和重新推导。
- 整体 Markdown 报告及独立对比矩阵导出。
- 会话隔离、上传与每日处理限额、单任务模型调用上限、过期清理。

**没有密钥也能体验教学样例。样例是原创虚构文档，非真实论文，不可作为科研引用。** 静态站点只提供样例交互；真实 PDF 分析需要下面的 Python 后端和 worker。

## 本地启动

要求 Node.js 22、Python 3.12。所有命令在仓库根目录执行。

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS / Linux 使用 source .venv/bin/activate
pip install -r requirements.txt
npm ci
```

复制 `.env.example` 为 `.env`。只浏览示例可以保持密钥为空；真实分析填写：

| 配置 | 用途 |
|---|---|
| `MINERU_API_KEY` | MinerU 官方 API Token |
| `LLM_BASE_URL` | 供应商的兼容接口根地址，末尾 `/v1` 以供应商文档为准 |
| `LLM_API_KEY` | 模型服务密钥，仅后端使用 |
| `LLM_MODEL` | 账号实际可用的模型 ID |
| `LLM_JSON_SCHEMA` | 供应商支持严格 JSON Schema 时设为 true；否则使用 JSON mode |
| `LLM_THINKING` | DeepSeek 可设置 `disabled`，避免思考占满 JSON 输出预算；其他供应商留空 |
| `LLM_MAX_OUTPUT_TOKENS` | 单次输出上限，默认 10000；本次部署使用 16000 |

分别打开三个终端：

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

```bash
python -m backend.worker
```

```bash
npm run dev
```

浏览器打开 http://127.0.0.1:5173 。默认读取教学示例；“新建分析”用于真实 PDF。不能配置密钥时按钮明确禁用，不模拟模型成功。

生产构建后，FastAPI 也可直接提供前端：`npm run build`，重启后端，再访问 http://127.0.0.1:8000 。

## Docker 部署

```bash
# 确保已经创建 .env
docker compose up --build -d
```

默认只绑定服务器本机 `127.0.0.1:8000`，前面配置 HTTPS 反向代理。`COOKIE_SECURE=true`，`ALLOWED_ORIGINS=https://你的域名`。反向代理需保留 Host、传递 HTTPS scheme，并限制请求体与并发。不要将 Vite 开发服务器暴露到公网。

`compose.yaml` 包含 app 和单个 worker，两者共享持久 volume。不要把 worker 扩到多个副本。建议先以 2 核 / 4GB 验证低并发容量；没有 GPU 需求。镜像配置已提供，Docker 运行验证需在有 Docker 的环境执行。

## Windows / Linux / macOS 打包

项目构建直接通过 Node 启动 TypeScript 与 Vite，不依赖 Bash 或嵌套调用 npm.cmd；可在 `E:\PaperReview Agent` 这类包含空格的路径运行。部署包使用 Windows 自带的 `tar.exe`（Linux/macOS 使用系统 tar）。

```bash
npm run build
npm run test:packaging
# 提交源码变更后，生成与该提交一致的发布文件
npm run package
```

产物：`artifacts/site.tar.gz`（静态示例部署包）、`artifacts/paper-method-agent-source.zip`（完整已提交源码），以及记录校验和/提交号的 manifest。部署包仅包含编译后的 dist 和站点标识，不包含 Python 后端、密钥或缓存；源码包包含 Docker 后端。源码未提交时明确拒绝生成发布包，防止源码和部署内容不一致。

已有构建可运行 `npm run package:site` 或 `npm run package:source` 单独打包。打包程序检查归档路径、完整文件列表和逐文件 SHA-256；中间文件保存在 `artifacts/`，不会递归清理项目目录。

## 处理限制

默认每批最多 8 篇、每篇 30MB / 50 页，全服务每日 40 篇、每任务累计 100 次模型请求，可通过 `.env` 调整。API Token 额度和实际费用以供应商为准。超长阶段输入会明确失败，不静默截断。单篇失败允许其他论文继续；可重试并复用已成功阶段。

会话与缓存默认保留 7 天；worker 每小时清理过期数据。当前不提供账号登录，多人通过浏览器会话隔离。生产部署应增加网关限流；公开竞赛体验建议限制实际上传额度。

## 幻觉约束

1. 所有模型阶段输出通过 Pydantic 结构校验。
2. 分类只能从 `backend/ontology.json` 选择，不匹配保持未归类。
3. 作者明确局限与系统假设分开，未找到不补编。
4. 原文块为唯一证据来源，核验附带相邻上下文。
5. 年份排序不等于继承；仅有支持的关系进入图谱。
6. 人工编辑保留历史，重新核验之前不能标为支持。

“有据支持”表示文本前提有支持，不保证论文事实、研究方向创新性或假设实验有效性。自检与抽取使用同一配置模型，不宣称完全消除幻觉。

## 测试与项目结构

```bash
python -m pytest -q
npm run build
```

```text
backend/             FastAPI、worker、Agent、证据校验和缓存
backend/prompts.py   原创分阶段 System Prompt
backend/schemas.py   强约束输入输出结构
backend/ontology.json  RAG 分类本体
src/                 React 工作区与 ECharts 图谱
public/demo.json     原创虚构教学样例
tests/               接口、证据、缓存及完整 mock 流程测试
docs/                架构说明与人工评测方案
```

自动测试使用 mock 外部 API；真实 MinerU 任务创建和 DeepSeek JSON 接口已验证。真实论文效果仍需要按照 [评测方案](docs/EVALUATION.md) 进行人工评测，不以连通性测试代替科研质量验证。详情见 [架构](docs/ARCHITECTURE.md)。

## 参考与开源

参考 PaperAgent 的证据映射与有限修复思路，Meta Knowledge Graph 的图谱交互，Literature Review Agent 的证据卡片，PaperQA 的先证据后生成思路。完整链接、许可证和原创范围见 [第三方声明](THIRD_PARTY_NOTICES.md)。

本项目使用 OpenDataLab **MinerU** 托管 API 进行 PDF 文档解析，不本地部署 MinerU 模型。MinerU 及模型供应商各自条款保持独立。

发布 GitHub/Gitee 时创建空仓库，将本目录提交推送即可。不要提交 `.env`、`data/`、密钥或真实论文原文。建议保留自动检查并为比赛提交打发布标签。
