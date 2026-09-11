# 第三方工具与设计参考

本仓库原创代码、Prompt、数据结构、本体与虚构教学样例按 MIT 授权。没有 fork 或复制下述项目的完整代码，也未引入其业务模块。依赖自身许可证继续有效。

## 设计参考（不是运行依赖）

- [whut09/paper_agent](https://github.com/whut09/paper_agent)：分层工作流、证据映射、有限修复和人工修正思路；AGPL-3.0，不复制其实现。
- [Seaual/meta-knowledge-graph](https://github.com/Seaual/meta-knowledge-graph)：方法图交互、研究机会组织思路；MIT，不复制其界面或业务代码。
- [littlelelephant/literature-review-agent](https://github.com/littlelelephant/literature-review-agent)：结构化证据卡与阶段审计思路；AGPL-3.0，不复制其实现。
- [Future-House/paper-qa](https://github.com/Future-House/paper-qa)：先证据后回答与内容缓存思路；Apache-2.0，不引入其框架。

## 运行依赖

- AI 助教仅参考 [kotaemon](https://github.com/Cinnamon/kotaemon) 的引用交互、[OpenTutor](https://github.com/zijinz456/OpenTutor) 与 [Socratic Tutor](https://github.com/utsabpanta/ai-tutoring) 的教学流程、[AnythingLLM](https://github.com/Mintplex-Labs/anything-llm) 和 [Open WebUI](https://github.com/open-webui/open-webui) 的会话界面思路，未复制上述项目源码或 Prompt。
- rank-bm25：Apache-2.0；NumPy：BSD-3-Clause；react-markdown、remark-math、rehype-katex、KaTeX：MIT。保留安装包及字体中相应许可证。

- React / React DOM、Vite、TypeScript、Lucide：MIT / ISC 等原项目许可证，详见安装包内 LICENSE。
- Apache ECharts / zrender：Apache-2.0 / BSD-3-Clause，详见安装包内 LICENSE。
- FastAPI、Pydantic、HTTPX、python-dotenv、pytest：MIT 等许可证。
- Starlette、Uvicorn、python-multipart、pypdf：BSD / Apache-2.0 等许可证，以锁定版本包内文件为准。
- **MinerU**：本项目仅调用 OpenDataLab 提供的托管 API，不内嵌模型或源码。MinerU 受其 [独立许可证](https://github.com/opendatalab/MinerU/blob/master/LICENSE.md)及托管服务条款约束。界面和 README 保留使用标识。

论文原文不因仓库使用 MIT 而自动变为 MIT。不得提交密钥、用户上传文件或未获分发许可的论文。`public/demo.json` 是本团队原创虚构材料，不涉及真实论文结论。

- rehype-raw、rehype-sanitize（MIT）：将 MinerU 的 HTML 表格解析并进行安全过滤；原文数据不改写。
