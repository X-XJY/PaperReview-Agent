# 部署验收记录

日期：2026-09-10。环境：Windows 构建，Ubuntu 22.04 / Python 3.10 / 2GB 服务器。

- Python 自动测试：16 项通过，包括 5/8 篇 mock 流水线、人工修正、证据约束、会话隔离和模型截断处理。
- Windows 打包测试：5 项通过；带空格项目路径下生产构建及归档成功。
- 公网 `https://134.175.147.254` 首页、JS/CSS、会话接口均返回 200；HTTP 返回 301 到 HTTPS，Cookie 设置 Secure。
- systemd API、worker、Nginx 与续期定时器正常；Let's Encrypt 证书验证及模拟续期通过。
- 真实 MinerU + DeepSeek 测试使用公开论文 [Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401)。成功解析 197 个证据块，完成元信息、方法、分类、核验、研究方向和 Markdown 报告导出。
- 未找到充分证据的年份/会议保持空值；推导方向包含待核验与部分支持标记，没有强制把全部结果判为可靠。
- 模型配置变化后新建任务并复用阶段缓存；同配置再次上传返回同一任务 `reused=true`。
- 不同浏览器会话访问其他任务返回 404。

真实测试只覆盖一篇论文，5/8 篇并发批次目前由 mock 测试覆盖；未完成真实多论文科研质量人工评测。此记录证明连通性和功能流程，不代表研究方向具有新颖性或全部抽取准确。

浏览器自动化因无法可靠识别网址而停止，尚未完成浏览器视觉验收。PDF 原文、完整解析报告、会话 Cookie 和 API 密钥仅保存在私有运行目录，未纳入源码。
