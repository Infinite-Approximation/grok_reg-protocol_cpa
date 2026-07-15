# Grok 批量注册 + 导出 CPA 完整教程

本文档记录一次完整成功流程：从零搭建 Cloudflare 临时邮箱 → 配置本注册机 → 批量注册 Grok 账号 → 铸造 CPA OIDC 认证 → 上传到 CLIProxyAPI（CPA）。

目标产物：

| 产物 | 路径/位置 | 用途 |
|------|-----------|------|
| 账本（SSO） | `accounts_cli.txt` | `email----password----sso` |
| CPA 认证文件 | `cpa_auths/xai-<email>.json` | 免费 Grok 4.5 / Grok Build |
| CPA 热加载 | CPA 管理后台 auth-files | 通过 `http://CPA:8317` 调用 |

> 重要：`SSO ≠ OIDC`。  
> 免费 Grok 4.5 **不能**直接用账本里的 sso JWT 打 API，必须再铸造成 CPA 的 `type=xai` OIDC 文件。

---

## 0. 你需要准备什么

1. **一台 Windows / macOS / Linux 电脑**
   - 建议有桌面环境（浏览器注册 + 协议失败回退时需要）
   - Python 3.13
   - [uv](https://github.com/astral-sh/uv)
   - Chrome / Chromium
   - 可访问 `accounts.x.ai` / xAI 的代理（如 `http://127.0.0.1:7890`）

2. **Cloudflare 账号 + 一个已接入 Cloudflare 的域名**
   - 本文示例域名：`example.com`
   - 临时邮箱使用子域名：`mail.example.com`
   - 推荐用**子域名**做临时邮箱，根域名可留给其他业务

3. **一台已部署的 CLIProxyAPI（CPA）**
   - 管理页类似：`http://你的IP:8317/management.html`
   - 管理密码（Management Key）
   - 调用 API 用的 `sk-...` Key（不是管理密码）

---

## 1. 获取本项目并安装依赖

```bash
cd /path/to/grok_reg-protocol_cpa
uv sync
uv run python -c "from DrissionPage import Chromium; from curl_cffi import requests; print('OK')"
```

复制配置模板：

```bash
cp config.example.json config.json
```

---

## 2. 搭建 Cloudflare 临时邮箱（cloudflare_temp_email）

本注册机的 `email_provider=cloudflare` 对接的是开源项目：

- 项目：https://github.com/dreamhunter2333/cloudflare_temp_email
- 文档：https://temp-mail-docs.awsl.uk

本质是：你自己在 Cloudflare 上部署一套临时邮箱服务，注册机通过 API 自动创建地址并收验证码。

推荐用 **UI 部署**（无需本机 wrangler 熟练度）。

### 2.1 启用 Email Routing（建议用子域名）

1. 打开 [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. 进入你的主域名（如 `example.com`）
3. 左侧：**Email → Email Routing / 电子邮件路由**
4. 启用 Email Routing，并完成 DNS 记录下发
5. 添加并验证一个 **目标地址**（你自己能登录的邮箱，如 Gmail）
6. 在 **设置** 中添加子域名，例如：

```text
mail
```

最终临时邮箱后缀为：

```text
xxx@mail.example.com
```

确认 DNS 里存在 `mail` 子域名对应的 Cloudflare MX 记录（`route*.mx.cloudflare.net`）。

> 说明：根域名若已有其他邮件服务，优先使用子域名，避免互相抢 MX。

### 2.2 创建 D1 数据库

1. Cloudflare → **Storage & Databases → D1 SQL Database**
2. **Create database**
3. 名称示例：

```text
temp-email-db
```

4. 打开该数据库 → **Console / 控制台**
5. 打开并全选复制：

https://raw.githubusercontent.com/dreamhunter2333/cloudflare_temp_email/main/db/schema.sql

6. 粘贴到 Console，点 **Execute**
7. 看到“查询已成功执行”即可

### 2.3 创建并部署 Worker（后端 API）

1. Cloudflare → **Compute → Workers & Pages → Create → Worker**
2. 名称可自定义（示例：`temp-email-api` 或系统自动名）
3. Deploy 默认 Worker 后进入该 Worker

#### 2.3.1 打开 nodejs_compat

**设置 → 运行时 / Runtime**

- Compatibility date：选较新日期
- Compatibility flags：添加

```text
nodejs_compat
```

#### 2.3.2 上传 worker.js

1. 下载最新：

https://github.com/dreamhunter2333/cloudflare_temp_email/releases/latest/download/worker.js

2. Worker → **Edit code**
3. 左侧 Explorer 中右键 **Upload**，上传 `worker.js`
4. **Deploy**

#### 2.3.3 绑定 D1

**设置 → 绑定 / Bindings → Add**

| 项 | 值 |
|----|-----|
| 类型 | D1 Database |
| 变量名 | **`DB`**（必须大写） |
| 数据库 | `temp-email-db` |

#### 2.3.4 配置变量

**设置 → 变量和机密 / Variables and Secrets**，添加：

| 变量名 | 类型 | 示例值 |
|--------|------|--------|
| `DOMAINS` | 文本 | `["mail.example.com"]` |
| `JWT_SECRET` | Secret | 一串足够长的随机密钥 |
| `ADMIN_PASSWORDS` | 文本 | `["你的管理密码"]` |
| `ENABLE_USER_CREATE_EMAIL` | 文本 | `true` |
| `ENABLE_USER_DELETE_EMAIL` | 文本 | `true` |

注意：

- 值外面不要再套一层多余引号
- `DOMAINS` / `ADMIN_PASSWORDS` 必须是 JSON 数组格式

保存并部署。

### 2.4 把邮件 Catch-all 指到 Worker

1. 域名 → **Email Routing → 路由规则**
2. 找到 **全收 / Catch-all**
3. 编辑：
   - 操作：**发送到 Worker**
   - Worker：选你刚部署的 Worker
   - 状态：**启用 / 活跃**

### 2.5 验证临时邮箱 API

假设你的 Worker 地址为：

```text
https://你的worker名.你的子域.workers.dev
```

浏览器或命令行测试：

```bash
# 1) 根路径
curl -sS "https://你的worker/health_check"
# 期望：OK

# 2) 公开配置
curl -sS "https://你的worker/open_api/settings"
# 期望：JSON，且 domains 含 mail.xxx

# 3) 创建临时邮箱
curl -sS -X POST "https://你的worker/api/new_address" \
  -H "Content-Type: application/json" \
  -d "{}"
# 期望：{"address":"...@mail.xxx","jwt":"..."}
```

创建成功后再测收件接口（把 JWT 换掉）：

```bash
curl -sS "https://你的worker/api/mails?limit=10&offset=0" \
  -H "Authorization: Bearer 你的jwt"
# 期望：{"results":[],"count":0} 或邮件列表
```

到这里，临时邮箱服务就算搭好了。

---

## 3. 配置注册机 `config.json`

最少改这些字段：

```json
{
  "email_provider": "cloudflare",
  "cloudflare_api_base": "https://你的worker名.你的子域.workers.dev",
  "cloudflare_api_key": "",
  "cloudflare_auth_mode": "none",
  "cloudflare_path_domains": "/api/domains",
  "cloudflare_path_accounts": "/api/new_address",
  "cloudflare_path_token": "/api/token",
  "cloudflare_path_messages": "/api/mails",
  "defaultDomains": "mail.example.com",

  "proxy": "http://127.0.0.1:7890",
  "cpa_proxy": "http://127.0.0.1:7890",

  "register_count": 1,
  "register_threads": 1,

  "grok2api_auto_add_remote": false,

  "cpa_export_enabled": true,
  "cpa_auth_dir": "./cpa_auths",
  "cpa_copy_to_hotload": false,
  "cpa_hotload_dir": "",
  "cpa_base_url": "https://cli-chat-proxy.grok.com/v1",
  "cpa_prefer_protocol": true,
  "cpa_protocol_only": false,
  "cpa_headless": false,
  "cpa_force_standalone": true,
  "cpa_probe_after_write": true
}
```

### 关键说明

| 配置 | 含义 |
|------|------|
| `email_provider=cloudflare` | 用上面自建临时邮箱 |
| `cloudflare_api_base` | Worker API 根地址，**不要末尾 `/`** |
| `defaultDomains` | 临时邮箱域名，用于创建时轮换/指定 |
| `proxy` / `cpa_proxy` | 注册与 OIDC mint 代理 |
| `cpa_export_enabled=true` | 注册成功后自动 mint OIDC |
| `cpa_base_url` | **必须**是 `https://cli-chat-proxy.grok.com/v1` |
| `cpa_prefer_protocol=true` | 优先纯 HTTP Device Flow（快）；失败再回退浏览器 |
| `grok2api_auto_add_remote=false` | 没跑 grok2api 就关掉，避免无意义报错 |

代理优先级：

```text
cpa_proxy > proxy > 环境变量 https_proxy/http_proxy
```

---

## 4. 确认 CPA 可用

### 4.1 管理入口

```text
http://你的CPA:8317/management.html
```

- 管理密码：用于后台 / `X-Management-Key`
- API Key：形如 `sk-...`，用于 `/v1/chat/completions`

两者不是同一个东西。

### 4.2 快速探测

```bash
# 管理接口（用管理密码）
curl -sS "http://你的CPA:8317/v0/management/auth-files" \
  -H "X-Management-Key: 你的管理密码"

# 业务接口（用 sk- API Key）
curl -sS "http://你的CPA:8317/v1/models" \
  -H "Authorization: Bearer sk-你的APIKey"
```

`/v1/models` 中应能看到 `grok-4.5`（有 xAI 认证后）。

---

## 5. 先注册 1 个号验证全链路

```bash
cd /path/to/grok_reg-protocol_cpa
uv run python -u register_cli.py --extra 1 --threads 1
```

成功日志大致包括：

```text
+ 注册成功: xxx@mail.xxx
[cpa] mint try protocol (SSO HTTP device flow)
[cpa] mint protocol SUCCESS
[cpa] wrote .../cpa_auths/xai-xxx@mail.xxx.json
[cpa] probe models: ... has_grok_45=True
+ CPA auth: .../cpa_auths/xai-xxx@mail.xxx.json
=== 完成: 注册成功 1, ... CPA成功 1 ... ===
```

本地应出现：

1. `accounts_cli.txt` 多一行：`email----password----sso`
2. `cpa_auths/xai-<email>.json`

### 5.1 上传到 CPA

远程 CPA 不能直接写本地目录，用管理 API 上传：

```bash
curl -sS -X POST "http://你的CPA:8317/v0/management/auth-files" \
  -H "X-Management-Key: 你的管理密码" \
  -F "file=@./cpa_auths/xai-xxx@mail.xxx.json;type=application/json;filename=xai-xxx@mail.xxx.json"
```

期望返回：

```json
{"status":"ok"}
```

也可在管理页手动导入该 JSON。

### 5.2 验证可调用

```bash
curl -sS "http://你的CPA:8317/v1/chat/completions" \
  -H "Authorization: Bearer sk-你的APIKey" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "grok-4.5",
    "messages": [{"role":"user","content":"Reply with exactly OK"}],
    "stream": false,
    "max_tokens": 32
  }'
```

成功时应返回 200，内容含 `OK`，模型名可能显示为 `grok-4.5-build-free`。

---

## 6. 批量注册并自动上传 CPA

### 6.1 批量注册

示例：再注册 100 个，3 线程：

```bash
uv run python -u register_cli.py --extra 100 --threads 3
```

常用参数：

| 参数 | 含义 |
|------|------|
| `--extra N` | 再新注册 N 个（推荐） |
| `--count N` | 账本总数目标（含已有） |
| `--threads N` | 注册并发（有头浏览器建议 1–3） |
| `--accounts-file` | 账本路径，默认 `accounts_cli.txt` |

实测参考（环境不同会变）：

- 3 线程，约 14 分钟完成 100 号
- 注册成功率可接近 100%
- mint 多数走协议路径（数秒级），少数回退浏览器

### 6.2 边注册边上传（推荐）

注册机默认只写本地 `cpa_auths/`。远程 CPA 需要额外上传。

可用本仓库脚本持续上传（Windows / 通用 Python）：

```bash
# 终端 1：注册
uv run python -u register_cli.py --extra 100 --threads 3

# 终端 2：监控上传（需先改脚本里的 CPA 地址与管理密码）
uv run python -u scripts/cpa_watch_upload.py
```

或结束后一次性补传所有本地文件：

```bash
# 伪代码：对 cpa_auths/xai-*.json 逐个 POST /v0/management/auth-files
for f in cpa_auths/xai-*.json; do
  curl -sS -X POST "http://你的CPA:8317/v0/management/auth-files" \
    -H "X-Management-Key: 你的管理密码" \
    -F "file=@${f};type=application/json;filename=$(basename "$f")"
done
```

上传后在 CPA 管理页 **Auth Files / 认证文件** 中应看到大量：

```text
xai-xxxxx@mail.你的域名.json
provider=xai
```

### 6.3 可选：本机热加载目录

若 CPA 与注册机在同一台机器，可直接：

```json
{
  "cpa_copy_to_hotload": true,
  "cpa_hotload_dir": "/path/to/cpa/auth-dir"
}
```

远程 CPA **不要**把 URL 写进 `cpa_hotload_dir`；那是服务器本地路径，不是 HTTP 地址。

---

## 7. 整条链路示意

```text
Cloudflare 临时邮箱 (mail.域名)
        │  创建地址 + 收验证码
        ▼
注册机 Chromium + DrissionPage
  accounts.x.ai 注册 → SSO cookie
        │
        ├─► accounts_cli.txt   (email----password----sso)
        │
        └─► CPA mint（协议优先 → 浏览器回退）
                │
                ▼
        cpa_auths/xai-email.json
                │  管理 API 上传 / 手动导入
                ▼
        CLIProxyAPI :8317
                │
                ▼
        model=grok-4.5  (免费 Build)
```

---

## 8. 关于“额度面板显示 $0 / --”

CPA 管理页「Grok 额度 / 刷新额度」常显示：

- 周限额：`--`
- 按量付费：未启用
- 月度积分：`US$0.00 / US$0.00`

对**免费 Build 号**这通常是正常现象。  
该面板更偏向付费/团队账单字段，**不等于**账号不能用。

正确判断方式：

1. `/v1/models` 是否含 `grok-4.5`
2. `/v1/chat/completions` 是否 200 并返回内容

免费号仍可能有频率或风控限制，那是另一套机制，不一定反映在该额度面板。

---

## 9. 常见问题排查

| 现象 | 处理 |
|------|------|
| `/api/new_address` 失败 | 检查 Worker 是否部署、`DOMAINS`、`DB` 绑定名是否为 `DB` |
| 收不到验证码 | Catch-all 是否指向 Worker；`mail` 子域 MX 是否正确 |
| 注册页找不到「Sign up」按钮 | 更新注册机按钮匹配逻辑（英文页文案去空格后是 `signup`） |
| 卡在 Turnstile | 确认 `turnstilePatch` 扩展存在；有头浏览器；代理稳定 |
| mint 报 sso invalid | SSO 过期；看账本第三段；会自动回退浏览器 mint |
| 有 CPA 文件但无 grok-4.5 | `cpa_base_url` 必须是 `cli-chat-proxy.grok.com/v1` |
| 上传 400 invalid name | 用 multipart 字段 `file=@xxx.json`，并带正确 filename |
| 管理密码不能调 `/v1/models` | 管理密码只给管理接口；聊天用 `sk-...` |

调试原则：

1. 临时邮箱：`new_address` + 收信 API 通
2. 注册：拿到 sso
3. mint：写出 `xai-*.json` 且 probe 含 grok-4.5
4. CPA：auth-files 列表可见
5. 调用：chat completions 返回 200

---

## 10. 推荐操作顺序（速查）

1. Cloudflare 域名 + Email Routing（子域名 `mail`）
2. D1 + schema.sql
3. Worker：`nodejs_compat` + `worker.js` + 绑定 `DB` + 变量
4. Catch-all → Worker
5. 测通 `/api/new_address`
6. `uv sync`，配置 `config.json`
7. `register_cli.py --extra 1 --threads 1`
8. 上传 `cpa_auths/xai-*.json` 到 CPA
9. 用 `sk-...` 测 `grok-4.5`
10. 批量：`--extra N --threads 2~3` + 自动/批量上传

---

## 11. 安全提醒

- `config.json`、`accounts_cli.txt`、`cpa_auths/*.json`、CPA 管理密码、`sk-` API Key 都是敏感信息
- 不要提交到公开仓库
- 公网暴露的 CPA 建议限制来源 IP，并定期轮换管理密码与 API Key

---

## 12. 本次成功环境参考（可对照）

以下为一次真实跑通时的参考，不要求完全一致：

| 项 | 值 |
|----|-----|
| 临时邮箱域名 | `mail.example.com` |
| 邮箱方案 | cloudflare_temp_email + Catch-all → Worker |
| 注册命令 | `uv run python -u register_cli.py --extra 100 --threads 3` |
| 结果 | 注册 100 成功 / CPA mint 100 成功 / 上传 100+ 成功 |
| 上传接口 | `POST /v0/management/auth-files` + `X-Management-Key` |
| 调用模型 | `grok-4.5`（上游免费 Build） |

---

## 13. 相关文件

| 文件 | 作用 |
|------|------|
| `register_cli.py` | CLI 批量注册入口 |
| `grok_register_ttk.py` | 浏览器注册核心 + 邮箱逻辑 |
| `cpa_export.py` | 注册成功后 mint hook |
| `cpa_xai/` | 协议 mint / 浏览器 mint / 写出 JSON |
| `config.json` | 本地配置（勿外泄） |
| `accounts_cli.txt` | 账本 |
| `cpa_auths/` | 本地 CPA 认证归档 |
| `turnstilePatch/` | Cloudflare Turnstile 辅助扩展 |

按本文顺序做完，即可复现：**临时邮箱 → 自动注册 Grok → 导出 xAI OIDC → 导入 CPA → 调用 grok-4.5**。
