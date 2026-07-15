# grok_reg-protocol_cpa

> **致谢**  
> 感谢 [https://api.jinkundong.store](https://api.jinkundong.store) 对本项目的大力支持。该网站是一个 API 中转站，支持目前主流编码模型，欢迎使用。

基于 **Chromium + DrissionPage + turnstilePatch** 的 Grok 账号注册机。

注册成功后自动：

1. 写入账本 `email----password----sso`
2. **协议优先**铸造 CPA 用的 OIDC 文件 `cpa_auths/xai-<email>.json`（失败再回退浏览器）
3. 可选：上传到远程 [CLIProxyAPI](https://github.com)（CPA）管理接口

> **硬约束：SSO ≠ OIDC。**  
> 免费 **Grok 4.5 / Grok Build** 不能直接用账本里的 sso JWT 调 API。  
> 必须再走 `accounts.x.ai` device-auth，写成 CPA 的 `type=xai` 认证文件。

---

## 功能一览

| 能力 | 说明 |
|------|------|
| 批量注册 | CLI / GUI，多线程 |
| 邮箱 | Cloudflare 临时邮箱 / Hotmail / CloudMail / DuckMail 等 |
| CPA 导出 | 协议 mint 优先，失败回退浏览器 consent |
| 远程上传 | `scripts/cpa_watch_upload.py` 监控 `cpa_auths/` 并上传 |
| Turnstile | 内置 `turnstilePatch` 扩展辅助 |

---

## 环境要求

- Python **3.13**
- [uv](https://github.com/astral-sh/uv)
- Chrome / Chromium
- 可访问 `accounts.x.ai` 的代理（常见 `http://127.0.0.1:7890`）
- 有头桌面环境（协议 mint 失败回退浏览器时需要）

```bash
git clone https://github.com/Infinite-Approximation/grok_reg-protocol_cpa.git
cd grok_reg-protocol_cpa
uv sync
uv run python -c "from DrissionPage import Chromium; from curl_cffi import requests; print('OK')"
```

---

## 5 分钟上手

### 1. 准备临时邮箱（推荐 Cloudflare）

本项目 `email_provider=cloudflare` 对接开源项目：

- https://github.com/dreamhunter2333/cloudflare_temp_email
- 文档：https://temp-mail-docs.awsl.uk

你需要：

1. Cloudflare 账号 + 已托管域名  
2. 启用 **Email Routing**（建议用子域名，如 `mail.example.com`）  
3. 创建 **D1** 并执行官方 `db/schema.sql`  
4. 部署 **Worker**（`nodejs_compat` + 上传 `worker.js`）  
5. 绑定 D1，变量名必须是 **`DB`**  
6. 配置变量：`DOMAINS` / `JWT_SECRET` / `ADMIN_PASSWORDS` / `ENABLE_USER_CREATE_EMAIL=true`  
7. Catch-all 指向该 Worker  

验证：

```bash
curl -sS -X POST "https://你的worker.workers.dev/api/new_address" \
  -H "Content-Type: application/json" -d "{}"
# 期望返回 address + jwt
```

更细的截图式步骤见：

- [docs/Grok注册与CPA上传完整教程.md](docs/Grok注册与CPA上传完整教程.md)

### 2. 配置注册机

```bash
cp config.example.json config.json
```

最少修改：

```json
{
  "email_provider": "cloudflare",
  "cloudflare_api_base": "https://你的worker.workers.dev",
  "cloudflare_auth_mode": "none",
  "defaultDomains": "mail.example.com",
  "proxy": "http://127.0.0.1:7890",
  "cpa_proxy": "http://127.0.0.1:7890",
  "grok2api_auto_add_remote": false,
  "cpa_export_enabled": true,
  "cpa_auth_dir": "./cpa_auths",
  "cpa_base_url": "https://cli-chat-proxy.grok.com/v1",
  "cpa_prefer_protocol": true,
  "cpa_headless": false
}
```

说明：

| 字段 | 含义 |
|------|------|
| `cloudflare_api_base` | 临时邮箱 Worker 根地址，不要末尾 `/` |
| `cpa_base_url` | **必须** `https://cli-chat-proxy.grok.com/v1` |
| `cpa_prefer_protocol` | 有 SSO 时优先纯 HTTP mint（快） |
| `proxy` / `cpa_proxy` | 注册与 mint 代理 |

### 3. 先注册 1 个号

```bash
uv run python -u register_cli.py --extra 1 --threads 1
```

成功后会有：

| 文件 | 内容 |
|------|------|
| `accounts_cli.txt` | `email----password----sso` |
| `cpa_auths/xai-<email>.json` | CPA OIDC 认证 |

### 4. 上传到 CPA

#### 方式 A：管理页手动导入

打开 `http://你的CPA:8317/management.html`，导入 `cpa_auths/xai-*.json`。

#### 方式 B：管理 API 单文件上传

```bash
curl -sS -X POST "http://你的CPA:8317/v0/management/auth-files" \
  -H "X-Management-Key: 你的管理密码" \
  -F "file=@./cpa_auths/xai-xxx.json;type=application/json;filename=xai-xxx.json"
```

期望：`{"status":"ok"}`

#### 方式 C：监控自动上传

```bash
# Windows PowerShell
$env:CPA_BASE="http://你的CPA:8317"
$env:CPA_MANAGEMENT_KEY="你的管理密码"
uv run python -u scripts/cpa_watch_upload.py
```

```bash
# Linux / macOS
export CPA_BASE="http://你的CPA:8317"
export CPA_MANAGEMENT_KEY="你的管理密码"
uv run python -u scripts/cpa_watch_upload.py
```

停止：在项目根创建空文件 `logs/STOP_UPLOADER`。

> 注意：`CPA_MANAGEMENT_KEY` 是管理密码，不是 `sk-...` API Key。

### 5. 调用验证

```bash
curl -sS "http://你的CPA:8317/v1/chat/completions" \
  -H "Authorization: Bearer sk-你的APIKey" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "grok-4.5",
    "messages": [{"role":"user","content":"Reply with exactly OK"}],
    "stream": false
  }'
```

---

## 批量注册

```bash
# 再注册 100 个，3 线程
uv run python -u register_cli.py --extra 100 --threads 3
```

| 参数 | 含义 |
|------|------|
| `--extra N` | 再新注册 N 个（推荐） |
| `--count N` | 账本总数目标（含已有） |
| `--threads N` | 并发 1–10，有头浏览器建议 1–3 |
| `--accounts-file` | 账本路径 |

建议：一个终端跑注册，另一个终端跑 `cpa_watch_upload.py`。

---

## 其它邮箱方案

### Hotmail / Outlook

```json
{
  "email_provider": "hotmail",
  "hotmail_accounts_file": "mail_credentials.txt"
}
```

```bash
cp mail_credentials.example.txt mail_credentials.txt
```

每行：

```text
邮箱----密码----ClientID----Microsoft_refresh_token
```

### CloudMail / DuckMail / Cloudflare Worker 自定义路径

见 `config.example.json` 注释键（以 `//` 开头的键加载时忽略）。

---

## 存量账号补 CPA

账本第三段已有 SSO 时，可只 mint 不重新注册：

```bash
uv run python -u scripts/backfill_cpa_xai_from_accounts.py \
  --accounts accounts_cli.txt \
  --limit 0 --probe --timeout 300
```

从本机 Grok CLI 导出：

```bash
uv run python scripts/export_cpa_xai_from_grok_auth.py --out-dir ./cpa_auths
```

---

## 目录结构

```text
grok_reg-protocol_cpa/
  register_cli.py                 # CLI 批量注册
  grok_register_ttk.py            # 注册核心 + 邮箱
  cpa_export.py                   # 注册成功后 mint
  cpa_xai/                        # 协议/浏览器 OIDC 铸造
  scripts/
    cpa_watch_upload.py           # 监控上传到远程 CPA
    backfill_cpa_xai_from_accounts.py
    export_cpa_xai_from_grok_auth.py
  docs/
    Grok注册与CPA上传完整教程.md   # 详细图文步骤
  config.example.json
  turnstilePatch/
  pyproject.toml / uv.lock
```

本地运行后才会出现（**不要提交**）：

- `config.json`
- `accounts_cli.txt`
- `cpa_auths/`
- `mail_credentials.txt`
- `logs/`

---

## 链路示意

```text
临时邮箱 API
    → Chromium 注册 accounts.x.ai
    → accounts_cli.txt (SSO)
    → protocol mint (失败则浏览器)
    → cpa_auths/xai-*.json
    → 上传 CPA auth-files
    → http://CPA:8317  model=grok-4.5
```

---

## 关于 CPA「额度」面板

管理页「Grok 额度」对免费 Build 号常显示：

- 周限额 `--`
- 月度积分 `$0.00 / $0.00`

这通常**不等于**不能用。  
以 `/v1/models` 是否含 `grok-4.5`、chat 是否 200 为准。

---

## 故障排查

| 现象 | 处理 |
|------|------|
| 创建邮箱失败 | 检查 Worker / `DOMAINS` / D1 绑定名是否为 `DB` |
| 收不到验证码 | Catch-all 是否指向 Worker；子域 MX 是否正确 |
| Turnstile 卡住 | 有头浏览器、代理、确认 `turnstilePatch` |
| mint 失败 | 看日志；协议失败会回退浏览器 |
| 无 grok-4.5 | `cpa_base_url` 是否为 cli-chat-proxy |
| 上传 401/400 | 管理密码、`file=@...` multipart 格式 |
| 管理密码不能聊天 | 聊天必须用 `sk-...` API Key |

---

## 安全

请勿把下列文件推到公开仓库：

- `config.json`
- `accounts_*.txt`
- `cpa_auths/*.json`
- `mail_credentials.txt`
- CPA 管理密码 / API Key

公网 CPA 建议限制访问来源，并定期轮换密钥。

---

## 参考与引用

- [LINUX DO 讨论帖](https://linux.do/t/topic/2561088)

---

## 许可与声明

本项目仅供学习与技术研究。请遵守 xAI / Cloudflare 等相关服务条款，自行承担使用风险。

详细部署与踩坑记录：

→ [docs/Grok注册与CPA上传完整教程.md](docs/Grok注册与CPA上传完整教程.md)
