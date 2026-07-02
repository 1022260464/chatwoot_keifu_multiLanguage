# Agent Demo 项目运维手册

本文档用于 Agent Demo 服务在 Amazon EC2 上的日常运维、发布、排错和 `.env` 配置管理。

默认项目信息：

```text
项目目录：/mnt/chawoot_houduan_agent/agent_demo/
服务名称：agent_demo.service
监听端口：9090
启动命令：python -m uvicorn main:app --app-dir src --host 0.0.0.0 --port 9090
```

## 1. 基础服务控制

日常对应用进行开启、关闭或重启，统一使用 `systemctl`。

### 查看运行状态

```bash
sudo systemctl status agent_demo.service
```

重点看：

- `active (running)`：服务正在运行。
- `Main PID`：当前进程号。
- `status=1/FAILURE`：服务启动失败或异常退出。

### 平滑重启服务

代码更新、`.env` 修改、依赖更新后执行：

```bash
sudo systemctl restart agent_demo.service
```

### 停止服务

```bash
sudo systemctl stop agent_demo.service
```

### 启动服务

```bash
sudo systemctl start agent_demo.service
```

### 禁用开机自启

如果后续废弃该服务：

```bash
sudo systemctl disable agent_demo.service
```

### 启用开机自启

如果需要恢复开机自启：

```bash
sudo systemctl enable agent_demo.service
```

## 2. 日志监控与排错

Systemd 会接管应用控制台输出，包括 `print` 和 `logger` 内容。使用 `journalctl` 查看日志。

### 实时滚动查看日志

```bash
sudo journalctl -u agent_demo.service -f
```

### 查看最近 100 行日志

```bash
sudo journalctl -u agent_demo.service -n 100 --no-pager
```

### 查看最近 20 行并持续滚动

发布后建议执行：

```bash
sudo journalctl -u agent_demo.service -f -n 20
```

### 按时间段过滤日志

```bash
sudo journalctl -u agent_demo.service --since "1 hour ago"
sudo journalctl -u agent_demo.service --since "2026-05-14 00:00:00" --until "2026-05-14 12:00:00"
```

### 清理陈旧日志释放磁盘空间

保留最近 500MB 日志：

```bash
sudo journalctl --vacuum-size=500M
```

## 3. 标准化代码更新发布流程

当新功能开发完毕，需要部署到 EC2 时，按以下顺序执行。

### 进入项目目录

```bash
cd /mnt/chawoot_houduan_agent/agent_demo/
```

### 拉取最新代码

```bash
git pull origin main
```

### 安装新的 Python 依赖

如果 `requirements.txt` 有变化，执行：

```bash
sudo /usr/bin/python3.11 -m pip install -r requirements.txt
```

### 重启服务让新代码生效

```bash
sudo systemctl restart agent_demo.service
```

### 查看日志确认新版本正常

```bash
sudo journalctl -u agent_demo.service -f -n 20
```

看到类似以下日志，说明服务至少已经被拉起：

```text
Uvicorn running on http://0.0.0.0:9090
```

## 4. `.env` 配置修改规则

项目配置文件位于：

```bash
/mnt/chawoot_houduan_agent/agent_demo/.env
```

修改 `.env`：

```bash
cd /mnt/chawoot_houduan_agent/agent_demo/
sudo nano .env
```

保存后只需要重启服务：

```bash
sudo systemctl restart agent_demo.service
```

注意：只修改 `.env` 不需要执行 `daemon-reload`。只有修改 `/etc/systemd/system/agent_demo.service` 才需要执行 `daemon-reload`。

## 5. `.env` 配置功能说明

下面说明运营和运维常用配置项。修改后记得重启服务。

### 5.1 基础运行配置

```env
APP_ENV=development
LOG_LEVEL=INFO
```

作用：

- `APP_ENV`：运行环境标识，一般用于区分开发、测试、生产。
- `LOG_LEVEL`：日志等级。常用值是 `INFO`、`WARNING`、`ERROR`、`DEBUG`。

建议：

- 日常线上用 `INFO`。
- 临时排查问题时可改成 `DEBUG`，排查完改回 `INFO`，避免日志过多。

### 5.2 LLM 模型配置

```env
LLM_PROVIDER=mock
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

作用：

- `LLM_PROVIDER=mock`：使用本地模拟回复，不真正调用大模型。
- `LLM_PROVIDER=deepseek`：使用 DeepSeek 进行意图识别、回答生成和转人工摘要。
- `DEEPSEEK_API_KEY`：DeepSeek API Key。
- `DEEPSEEK_BASE_URL`：DeepSeek API 地址。
- `DEEPSEEK_MODEL`：使用的模型名称。

启用真实 DeepSeek：

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=你的DeepSeekKey
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

效果：

- AI 回复会从模拟逻辑切换为真实模型生成。
- 意图分类会更灵活。
- 转人工备注会由模型自动总结。

风险：

- API Key 错误会导致服务启动失败或请求失败。
- 模型接口不可用时，日志中会出现 DeepSeek API 报错。

### 5.3 知识库配置

```env
RAG_PROVIDER=memory
DATABASE_URL=
DB_HOST=
DB_PORT=5432
DB_NAME=
DB_USER=
DB_PASS=
KNOWLEDGE_SCHEMA=public
KNOWLEDGE_TABLE_NAME=knowledge_chunks
RAG_MIN_CONFIDENCE=0.62
MAX_CONTEXT_CHUNKS=4
```

作用：

- `RAG_PROVIDER=memory`：使用代码内置的演示知识库。
- `RAG_PROVIDER=pgvector`：改用 PostgreSQL 知识库表 `knowledge_chunks`。
- `DATABASE_URL`：完整数据库连接串。
- `DB_HOST`、`DB_PORT`、`DB_NAME`、`DB_USER`、`DB_PASS`：数据库分项连接配置。
- `KNOWLEDGE_SCHEMA`：知识库表所在 schema，默认 `public`。
- `KNOWLEDGE_TABLE_NAME`：知识库表名，默认 `knowledge_chunks`。
- `RAG_MIN_CONFIDENCE`：知识库命中最低置信度。
- `MAX_CONTEXT_CHUNKS`：最多取多少条知识片段给 AI 参考。

启用 PostgreSQL 知识库：

```env
RAG_PROVIDER=pgvector
DATABASE_URL=postgresql://user:password@host:5432/dbname
```

或者：

```env
RAG_PROVIDER=pgvector
DB_HOST=数据库地址
DB_PORT=5432
DB_NAME=数据库名
DB_USER=用户名
DB_PASS=密码
KNOWLEDGE_SCHEMA=public
KNOWLEDGE_TABLE_NAME=knowledge_chunks
```

建表、索引和示例插入脚本统一维护在：

```text
db/001_create_knowledge_chunks.sql
db/002_create_knowledge_indexes.sql
db/003_create_knowledge_chunk_upsert.sql
db/004_sample_inserts.sql
db/sample_chunks.json
scripts/import_knowledge_chunks.py
src/customer_agent/document_chunking.py
src/customer_agent/knowledge_ingestion.py
db/README.md
```

效果：

- AI 会从数据库知识库检索答案。
- 可以支持更大规模、可维护的业务知识。

调整建议：

- `RAG_MIN_CONFIDENCE` 调高：回答更保守，命中不够时更容易转人工。
- `RAG_MIN_CONFIDENCE` 调低：回答更积极，但误答风险增加。
- `MAX_CONTEXT_CHUNKS` 调大：模型看到更多资料，但响应可能更慢。

### 5.4 Chatwoot 对接配置

```env
CHATWOOT_BASE_URL=
CHATWOOT_ACCOUNT_ID=2
CHATWOOT_API_ACCESS_TOKEN=
CHATWOOT_BOT_AGENT_ID=
CHATWOOT_DEFAULT_ASSIGNEE_ID=
CHATWOOT_OPEN_ON_INCOMING=false
```

作用：

- `CHATWOOT_BASE_URL`：Chatwoot 访问地址，例如 `https://chat.example.com`。
- `CHATWOOT_ACCOUNT_ID`：Chatwoot 账号 ID。
- `CHATWOOT_API_ACCESS_TOKEN`：Chatwoot API Token。
- `CHATWOOT_DEFAULT_ASSIGNEE_ID`：转人工时默认分配给哪个客服。
- `CHATWOOT_OPEN_ON_INCOMING`：用户发消息后是否立即把会话打开为 `open`。

效果：

- 三个核心配置 `CHATWOOT_BASE_URL`、`CHATWOOT_ACCOUNT_ID`、`CHATWOOT_API_ACCESS_TOKEN` 都存在时，系统会真正向 Chatwoot 发公开回复和私有备注。
- 如果缺少核心配置，系统会进入空客户端模式，只在本地处理，不会写回 Chatwoot。

Chatwoot Agent Bot URL 注意事项：

- 如果 Chatwoot 启用了 SSRF 防护，Agent Bot URL 的域名必须解析到公网 IP。
- 不要填写 `localhost`、`127.0.0.1`、`192.168.x.x`、`*.local`、hosts 映射域名，或最终解析到内网 IP 的 `nip.io` 地址。
- 临时测试可用 Cloudflare Tunnel 暴露 Agent 服务：

```bash
cloudflared tunnel --protocol http2 --url http://127.0.0.1:9091
```

Chatwoot Agent Bot URL 填：

```text
https://xxxx.trycloudflare.com/webhook/chatwoot
```

如果日志出现 `Hostname ... has no public ip addresses`，说明不是服务不可达，而是 Chatwoot 安全校验拒绝了私网地址。

常用开关：

```env
CHATWOOT_OPEN_ON_INCOMING=true
```

开启后，用户一发消息，会话会自动变成打开状态，方便客服在人工列表中看到。

```env
CHATWOOT_DEFAULT_ASSIGNEE_ID=客服ID
```

设置后，AI 判断需要转人工时，会自动分配给指定客服。

转人工状态会写入 Chatwoot 会话自定义属性，避免服务重启后 AI 再次参与同一会话：

```json
{
  "ai_handoff": true,
  "ai_handoff_reason": "业务查询工具 API 尚未接入",
  "ai_handoff_at": "2026-05-29T00:00:00+00:00"
}
```

后续同一会话的用户公开消息仍会生成 `[AI translation]` 中文私有备注，方便客服查看，但不会再进入 Agent，也不会再发送 AI 公开回复。若需要手动恢复 AI，可在 Chatwoot 会话 custom attributes 中把 `ai_handoff` 改为 `false`。

### 5.5 后台同步配置

```env
ADMIN_WEBHOOK_URL=
ADMIN_WEBHOOK_TOKEN=
```

作用：

- `ADMIN_WEBHOOK_URL`：把 Chatwoot 事件同步到你自己的后台系统。
- `ADMIN_WEBHOOK_TOKEN`：同步时附带的 Bearer Token。

效果：

- 配置后，系统会把支持的 Chatwoot 事件统一转发到后台。
- 不配置时，只处理 Chatwoot 和 Agent 逻辑，不额外同步。

适用场景：

- 自建 CRM。
- 自建工单系统。
- 运营后台需要记录 Chatwoot 对话事件。

### 5.6 翻译功能配置

```env
TRANSLATION_PRIVATE_NOTE_ENABLED=false
TRANSLATION_PROVIDER=pygtrans
TRANSLATION_TARGET_LANG=zh-CN
TRANSLATION_SKIP_CHINESE=true
TRANSLATION_MIN_TEXT_LENGTH=2
TRANSLATION_OUTGOING_ENABLED=false
TRANSLATION_DEFAULT_USER_LANG=
TRANSLATION_TIMEOUT_SECONDS=8
PYGTRANS_PROXY=
```

作用：

- `TRANSLATION_PRIVATE_NOTE_ENABLED`：是否把用户外语消息翻译成中文私有备注。
- `TRANSLATION_PROVIDER=pygtrans`：使用 Google 翻译能力。
- `TRANSLATION_PROVIDER=deepseek`：使用 DeepSeek 做翻译和语言识别。
- `TRANSLATION_TARGET_LANG=zh-CN`：入站消息翻译目标语言，默认中文。
- `TRANSLATION_SKIP_CHINESE=true`：用户消息包含中文时跳过翻译，避免重复。
- `TRANSLATION_MIN_TEXT_LENGTH=2`：少于该长度的消息不翻译。
- `TRANSLATION_OUTGOING_ENABLED`：是否把 AI 中文回复、客服中文私有备注翻译成用户语言。
- `TRANSLATION_DEFAULT_USER_LANG`：服务重启后不知道用户语言时的默认兜底语言。
- `TRANSLATION_TIMEOUT_SECONDS`：翻译超时时间。
- `PUBLIC_REPLY_FALLBACK_LANGUAGE`：公开回复无法安全翻译时使用的兜底语言，选项为 `vi` 或 `en`；实际兜底语句维护在 `src/customer_agent/support_templates.py` 的 `PUBLIC_REPLY_FALLBACKS`。
- `PYGTRANS_PROXY`：服务器访问 Google 翻译不稳定时使用代理。

推荐配置：

```env
TRANSLATION_PROVIDER=pygtrans
TRANSLATION_PRIVATE_NOTE_ENABLED=true
TRANSLATION_TARGET_LANG=zh-CN
TRANSLATION_SKIP_CHINESE=true
TRANSLATION_OUTGOING_ENABLED=true
TRANSLATION_DEFAULT_USER_LANG=
TRANSLATION_TIMEOUT_SECONDS=8
PUBLIC_REPLY_FALLBACK_LANGUAGE=vi
PYGTRANS_PROXY=
```

效果：

- 用户发英文、日文、韩文等外语时，客服后台会收到中文私有备注。
- AI 中文回复、客服中文私有备注会尝试翻译成用户语言后发给用户。
- 用户发中文时不会重复生成中文翻译备注。

如果绝大多数用户都是英文，可以设置：

```env
TRANSLATION_DEFAULT_USER_LANG=en
```

这样服务重启后，即使还没重新识别用户语言，也可以默认把中文回复翻译成英文。

### 5.7 快捷菜单与标准 FAQ

快捷菜单和前置过滤统一模板文件：

```text
src/customer_agent/support_templates.py
```

当前 FAQ 菜单只对中文、英文、越南语会话自动发送。流程是：

- 用户打开 Web Widget 时，Chatwoot 通常只发送 `webwidget_triggered`，但没有 `conversation_id`，此时系统不能主动发菜单。
- 用户发送第一条公开消息后，Chatwoot 创建会话并触发 `message_created + incoming`。
- 系统先执行原有语言识别和私有备注翻译逻辑。
- 如果语言是中文、英文或越南语，系统发送两条公开消息：一条说明气泡，一条 `input_select` 按钮气泡。
- 如果语言不在支持范围内，系统不发送 FAQ 菜单，继续走原 Agent / 翻译流程。
- 用户点击按钮后，Chatwoot 可能发送 `message_updated`，系统会从提交字段中识别 `CMD_...` 并直接回复标准答案，不调用 LLM。
- 用户只发送 `你好`、`hi`、`test`、`??` 等低价值消息时，系统会先发送 `LOW_VALUE_REPLIES` 引导话术，再补发 FAQ 菜单模板，同样不调用 LLM。

当前标准问题：

```text
公司和产品介绍
为什么额度不高
还款再次申请被拒
利率问题
```

修改 FAQ 后需要重启服务：

```bash
sudo systemctl restart agent_demo.service
```

发布 FAQ 或前置过滤相关改动时，至少上传：

```text
src/main.py
src/customer_agent/faq_config.py
src/customer_agent/message_guard.py
src/customer_agent/support_templates.py
```

如果正式环境还没有交互按钮发送能力，还需要上传：

```text
src/customer_agent/chatwoot.py
src/customer_agent/clients.py
src/customer_agent/workflow.py
```

前置过滤规则：

- 无意义消息直接本地回复，并补发 FAQ 菜单模板，不进入 LLM。
- 敏感/高风险关键词直接转人工，并写私有备注。
- 手机号、身份证号、银行卡号、验证码、邮箱等隐私字段会脱敏后再进入 Agent。
- 维护入口均在 `support_templates.py`，逻辑入口在 `message_guard.py`。

### 5.8 语义缓存配置

```env
SEMANTIC_CACHE_THRESHOLD=0.95
```

作用：

- 控制语义缓存命中阈值。
- 数值越高，越严格，只有非常相似的问题才复用缓存。
- 数值越低，越宽松，缓存命中更多，但误用风险增加。

建议：

- 线上保持 `0.95` 左右。
- 如果发现相似问题没有复用，可以略微调低。
- 如果发现不同问题误用同一答案，应调高。

## 6. Service 配置修改规则

如果需要修改端口、启动命令、运行用户、项目路径或 Python 路径，需要编辑 systemd service 文件。

### 编辑服务文件

```bash
sudo nano /etc/systemd/system/agent_demo.service
```

### 重新加载 systemd 守护进程

只要修改了 `.service` 文件，必须执行：

```bash
sudo systemctl daemon-reload
```

否则即使重启服务，新的 service 配置也可能不生效。

### 重启应用服务

```bash
sudo systemctl restart agent_demo.service
```

### 查看状态

```bash
sudo systemctl status agent_demo.service
```

## 7. 修改端口的正确方式

如果要把服务从 `9090` 改成其他端口，需要检查两处：

1. `/etc/systemd/system/agent_demo.service` 里的启动命令。
2. Chatwoot 后台配置的 webhook 地址。

例如把端口改为 `9091`：

```bash
sudo nano /etc/systemd/system/agent_demo.service
```

把启动命令中的：

```text
--port 9090
```

改为：

```text
--port 9091
```

然后执行：

```bash
sudo systemctl daemon-reload
sudo systemctl restart agent_demo.service
```

最后把 Chatwoot webhook 地址同步改成：

```text
http://服务器地址:9091/webhook/chatwoot
```

## 8. 常见故障速查表

### 服务无限重启，状态显示 `status=1/FAILURE`

查看最近错误：

```bash
sudo journalctl -u agent_demo.service -n 50 --no-pager
```

常见原因：

- 代码语法错误。
- Python 依赖包缺失。
- `.env` 配置错误。
- DeepSeek API Key 为空但启用了 `LLM_PROVIDER=deepseek`。
- 端口被占用。
- 数据库配置错误但启用了 `RAG_PROVIDER=pgvector`。

### 端口被占用

查找占用 `9090` 的进程：

```bash
sudo lsof -i :9090
```

结束进程：

```bash
sudo kill -9 <PID>
```

重启服务：

```bash
sudo systemctl restart agent_demo.service
```

### Chatwoot 没收到 AI 回复或私有备注

检查 `.env`：

```env
CHATWOOT_BASE_URL=
CHATWOOT_ACCOUNT_ID=
CHATWOOT_API_ACCESS_TOKEN=
```

这三个必须都有值。

然后查看日志：

```bash
sudo journalctl -u agent_demo.service -n 100 --no-pager
```

重点搜索：

```text
Chatwoot API error
Chatwoot settings are incomplete
```

### FAQ 菜单或按钮回复不生效

先实时看日志：

```bash
sudo journalctl -u agent_demo.service -f -n 50
```

正常首次用户消息后应看到：

```text
Detected conversation language conversation_id=...
Sending FAQ menu conversation_id=... language=...
Sent Chatwoot message conversation_id=... private=False
```

如果首次用户消息是低价值消息，例如 `你好`，正常应看到：

```text
Message guard replied conversation_id=... reason=low_value_message
Sending FAQ menu conversation_id=... language=...
Sent Chatwoot message conversation_id=... private=False
```

正常点击按钮后应看到：

```text
Queued FAQ command from Chatwoot submission conversation_id=... command=CMD_...
Handling FAQ command conversation_id=...
Sent Chatwoot message conversation_id=... private=False
```

常见原因：

- 只打开气泡，没有发送第一条消息。Chatwoot 的 `webwidget_triggered` 通常没有 `conversation_id`，系统无法给不存在的会话发菜单。
- 用户语言不是中文、英文或越南语，系统会跳过 FAQ 菜单。
- Chatwoot webhook 没有订阅 `message_updated`，按钮点击提交不会进入后端。
- 只上传了 `faq_config.py`，但没有上传 `main.py`、`support_templates.py`、`message_guard.py` 或交互消息相关文件。

### 翻译不生效

入站翻译检查：

```env
TRANSLATION_PRIVATE_NOTE_ENABLED=true
TRANSLATION_PROVIDER=pygtrans
```

出站翻译检查：

```env
TRANSLATION_OUTGOING_ENABLED=true
```

常见原因：

- 服务器无法访问 Google 翻译。
- `pygtrans` 没安装。
- 用户消息是中文且设置了 `TRANSLATION_SKIP_CHINESE=true`。
- 服务刚重启，语言缓存为空。
- 未设置 `TRANSLATION_DEFAULT_USER_LANG`。

### DeepSeek 不工作

检查：

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=你的Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

查看日志：

```bash
sudo journalctl -u agent_demo.service -n 100 --no-pager
```

重点搜索：

```text
DeepSeek API error
DeepSeek API request failed
DEEPSEEK_API_KEY is required
```

### 数据库知识库不工作

如果配置了：

```env
RAG_PROVIDER=pgvector
```

需要确认：

- `DATABASE_URL` 或 `DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASS` 已正确配置。
- 数据库能从 EC2 访问。
- 表 `knowledge_chunks` 存在。
- 表中有 `id`、`chunk_text`、`metadata`、`search_vector` 字段。
- 建表、索引、插入函数脚本已按顺序执行：`db/001_create_knowledge_chunks.sql`、`db/002_create_knowledge_indexes.sql`、`db/003_create_knowledge_chunk_upsert.sql`。

## 9. 发布后检查清单

每次发布或修改配置后，建议按顺序检查：

```bash
sudo systemctl status agent_demo.service
sudo journalctl -u agent_demo.service -n 50 --no-pager
curl http://127.0.0.1:9090/health
```

健康检查正常返回：

```json
{"status":"ok"}
```

再到 Chatwoot 发一条测试消息，确认：

- webhook 能触发。
- 日志中出现 `Queued Agent processing`。
- 如果开启翻译，能看到 `[AI translation]` 私有备注。
- 如果开启出站翻译，AI 中文回复或客服中文私有备注能被翻译成用户语言。

### 运营测试流程

发布 FAQ、前置过滤、Chatwoot webhook 或 Tunnel 相关改动后，按下面流程验收：

1. 服务健康检查

```bash
curl http://127.0.0.1:9091/health
```

期望返回：

```json
{"status":"ok"}
```

2. 如果使用 Cloudflare Tunnel，确认公网地址可访问

```bash
curl https://xxxx.trycloudflare.com/health
```

期望同样返回 `{"status":"ok"}`。如果 `cloudflared` 日志出现 `Registered tunnel connection ... protocol=http2`，说明隧道已连上。

3. 打开实时日志

```bash
sudo journalctl -u agent_demo.service -f -n 80
```

如果是手动运行 `uvicorn`，直接看当前终端输出。

4. 在 Chatwoot Web Widget 发送低价值消息

测试输入：

```text
你好
```

用户侧期望看到：

- 一条低价值引导回复。
- 一条 FAQ 说明气泡。
- 一条 FAQ 按钮菜单。

日志期望包含：

```text
POST /webhook/chatwoot HTTP/1.1" 200 OK
Message guard replied conversation_id=... reason=low_value_message
Sending FAQ menu conversation_id=... language=...
Sent Chatwoot message conversation_id=... private=False
```

5. 点击 FAQ 菜单按钮

任选一个按钮，例如“公司介绍 / 产品优势”。用户侧期望收到对应标准答案。

日志期望包含：

```text
Queued FAQ command from Chatwoot submission conversation_id=... command=CMD_...
Handling FAQ command conversation_id=...
Sent Chatwoot message conversation_id=... private=False
```

6. 发送正常业务问题

测试输入：

```text
我想咨询一下产品售后维修流程，需要提供哪些资料？
```

期望进入 Agent 流程。日志应出现：

```text
Queued Agent processing conversation_id=...
Processing Chatwoot conversation_id=...
Processed Chatwoot conversation_id=...
```

7. 发送敏感或高风险问题

测试输入：

```text
我要投诉你们
```

期望转人工并写私有备注，不进入 LLM。日志应出现：

```text
Message guard handed off conversation_id=... reason=sensitive_keyword:...
```

8. 发送隐私字段测试

测试输入：

```text
我的手机号是13800138000，请帮我查一下
```

期望进入 Agent 前被脱敏，并写私有备注。日志应出现：

```text
Message guard sanitized content conversation_id=... reason=privacy_masked:phone
```

测试完成后，把 Chatwoot 里的测试会话关闭或标记，避免影响真实运营统计。

## 10. 安全注意事项

- `.env` 中包含 API Key 和 Token，不要提交到 Git。
- 不要在群聊、截图、文档里暴露 `CHATWOOT_API_ACCESS_TOKEN`、`DEEPSEEK_API_KEY`、数据库密码。
- 修改生产配置前，建议先备份：

```bash
cp .env .env.bak.$(date +%Y%m%d_%H%M%S)
```

- 出现异常时，优先回滚 `.env` 或代码，再重启服务。
