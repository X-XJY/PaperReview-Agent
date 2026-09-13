# Ubuntu 原生部署

生产入口：`https://134.175.147.254`。需要云安全组放行 TCP 80、443；8000 仅监听本机。仓库：<https://github.com/X-XJY/PaperReview-Agent>。

适用于 Ubuntu 22.04、2GB 内存。前端在开发电脑构建，服务器运行 Nginx、FastAPI、论文 worker 和助教 worker。Docker Compose 仍可作为另一种部署方式。

## 安装

1. 开发电脑执行 `npm ci`、`npm run build`，将已提交源码和 `dist/` 上传到 `/home/ubuntu/PaperReview-Agent`。
2. 服务器安装 `python3-venv nginx`，在项目内执行 `python3 -m venv .venv` 和 `.venv/bin/pip install -r requirements.txt`。
3. 单独创建 `.env`，填入供应商密钥并 `chmod 600 .env`。不得放入源码仓库。模型名称以供应商账号返回为准；本次验证使用 `deepseek-flash`，`LLM_JSON_SCHEMA=false`、`LLM_THINKING=disabled`、`LLM_MAX_OUTPUT_TOKENS=16000`。关闭该模型默认思考模式，避免思考消耗输出预算导致 JSON 截断；其他供应商保持 `LLM_THINKING` 为空。
4. `deploy/*.service` 默认用户为 `ubuntu`、目录为上述路径；换服务器时同步调整。复制 API 和 worker 单元到 `/etc/systemd/system/`，执行 `sudo systemctl daemon-reload`、`sudo systemctl enable --now paperreview-api paperreview-worker`。
5. 将 `deploy/nginx-http.conf` 安装到 `/etc/nginx/sites-available/default`，先 `sudo nginx -t`，再 reload。配置已含请求限流和上传大小限制。

## IP HTTPS 与自动续期

修改 Nginx 配置中的 IP 为实际地址。使用支持 IP webroot 的 Certbot 5.4+：

```bash
sudo python3 -m venv /opt/certbot
sudo /opt/certbot/bin/pip install 'certbot>=5.4'
sudo /opt/certbot/bin/certbot certonly --preferred-profile shortlived \
  --webroot --webroot-path /var/www/html --ip-address 134.175.147.254 \
  --deploy-hook 'systemctl reload nginx'
```

获得证书后安装 `deploy/nginx-https.conf`，设置 `.env` 中 `COOKIE_SECURE=true`、`ALLOWED_ORIGINS=https://134.175.147.254`，重启 API/worker 并 reload Nginx。

复制 `deploy/paperreview-certbot.service` 和 `.timer` 到 `/etc/systemd/system/`，执行：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now paperreview-certbot.timer
sudo /opt/certbot/bin/certbot renew --dry-run
```

IP 证书只有六天有效期，定时器每天检查两次并在续期后 reload Nginx。保持 80 端口可达用于 ACME 验证。[Let's Encrypt 官方说明](https://letsencrypt.org/2026/03/11/shorter-certs-certbot/)。

## 运维

AI 助教上线时先安装更新后的 requirements.txt，启动 API 自动创建新增 SQLite 表，再安装 `deploy/paperreview-tutor.service` 并执行 `sudo systemctl daemon-reload`、`sudo systemctl enable --now paperreview-tutor`。原 worker 也应重启以加载聊天数据清理逻辑。仅运行一个 tutor worker。详细参数见 [助教说明](AI_TUTOR.md)。

```bash
sudo systemctl status paperreview-api paperreview-worker paperreview-tutor nginx
sudo journalctl -u paperreview-worker -n 80 --no-pager
sudo systemctl list-timers paperreview-certbot.timer
curl https://134.175.147.254/api/health
```

更新时保留 `.env`、`data/` 和 `.venv/`，上传新源码及完整 `dist/` 后重启三个应用服务。每类 worker 仅运行一个实例。备份数据时先停止三个应用服务，再备份 `data/`；该目录包含论文和会话数据，应保持私有。

若本机 TLS 正常而公网 443 超时，先检查云控制台安全组；服务器内 UFW 规则与云安全组相互独立。未放行 443 前不能将 HTTPS 配置成功等同于公网访问验收通过。

助教 PDF 导出需要安装 `sudo apt-get install fonts-wqy-zenhei`，更新 requirements.txt 并重启 API；Docker 镜像已包含该字体。
