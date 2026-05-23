# Customer Service Agent Demo

这是一个只包含后端 Agent 核心逻辑的 demo。外部 API 都留在 `.env` 中占位，默认使用 mock LLM 和内存知识库，方便先验证工作流。

## 目录

```text
agent_demo/
  src/customer_agent/
    workflow.py      # Agent 状态机
    clients.py       # LLM / RAG / Chatwoot 可替换接口
    factory.py       # 根据 .env 选择 mock / DeepSeek / PGVector 实现
    schemas.py       # 消息、状态、动作模型
    config.py        # 环境变量配置
  run_demo.py        # 本地命令行演示
  src/main.py        # FastAPI Webhook 网关
```

## 快速运行

```bash
cd agent_demo
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python run_demo.py "你们的退款政策是什么？"
```

## 启动 Chatwoot Webhook 网关

```bash
cd agent_demo
python -m uvicorn main:app --app-dir src --host 0.0.0.0 --port 9090
```

服务器上如果固定使用 `9091`，可以用脚本一键启动 Agent 后端和 Cloudflare Tunnel：

```bash
chmod +x scripts/start_agent_demo.sh
./scripts/start_agent_demo.sh start
./scripts/start_agent_demo.sh status
```

脚本会直接打印完整的 Chatwoot Agent Bot URL：

```text
https://xxxx.trycloudflare.com/webhook/chatwoot
```

如果只想重新查看当前 URL：

```bash
./scripts/start_agent_demo.sh url
```

停止：

```bash
./scripts/start_agent_demo.sh stop
```

Webhook 地址：

```text
http://你的服务地址:9090/webhook/chatwoot
```

如果配置的是 Chatwoot Agent Bot URL，Chatwoot 可能会先做 SSRF 安全校验。此时不要使用 `localhost`、内网 IP、`*.local`、hosts 映射或解析到内网 IP 的 `nip.io` 地址；需要使用公网可访问的 HTTPS 地址，例如 Cloudflare Tunnel：

```bash
cloudflared tunnel --protocol http2 --url http://127.0.0.1:9090
```

然后在 Chatwoot Agent Bot URL 中填写：

```text
https://xxxx.trycloudflare.com/webhook/chatwoot
```

建议在 Chatwoot 后台订阅这些事件：

```json
[
  "conversation_created",
  "conversation_status_changed",
  "conversation_updated",
  "message_created",
  "message_updated",
  "webwidget_triggered"
]
```

网关会先接收这些事件用于同步完整历史。只有 `event=message_created` 且 `message_type=incoming` 的公开用户消息才会触发 Agent；AI / 客服发出的 `outgoing` 消息、状态变化和私有备注只同步不触发 Agent，避免循环回复。

## 快捷菜单与标准 FAQ

网关内置了 Chatwoot 快捷菜单拦截：

- 业务可维护模板统一在 `src/customer_agent/support_templates.py`，包括 FAQ、多语言文案、无意义消息、敏感词、隐私脱敏规则等。
- `src/customer_agent/faq_config.py` 只保留 FAQ 查询和菜单构造函数，业务内容不放在这里。
- Chatwoot 打开气泡时的 `webwidget_triggered` 事件通常没有 `conversation_id`，所以系统会等用户第一条公开消息创建会话后再弹菜单。
- 首次用户消息会先走原有语言识别和私有备注翻译逻辑；只有识别为中文、英文或越南语时，才发送 FAQ 菜单。其它语言继续进入原来的 Agent / 翻译流程。
- 菜单由两条公开消息组成：第一条是普通说明气泡，第二条是 `input_select` 按钮气泡。
- 用户点击菜单按钮后，Chatwoot 可能通过 `message_updated` 提交按钮值。webhook 会在调用 LLM 前拦截 `CMD_...` 指令，命中后直接发送标准答案。
- 用户输入 `帮助`、`菜单`、`help`、`/help`、`faq` 时，也会尝试按当前会话语言发送 FAQ 菜单。
- 用户只发送 `你好`、`hi`、`test`、`??` 等低价值消息时，系统会先回复本地引导话术，再发送 FAQ 菜单模板，不进入 LLM。

当前标准问题包括：

```text
公司和产品介绍
为什么额度不高
还款再次申请被拒
利率问题
```

修改标准答案、按钮标题、语言模板、敏感词或过滤话术时，只需要调整 `support_templates.py`。

## LLM 前置过滤

为减少无效 token 消耗，网关在调用 Agent / RAG / LLM 前加入了本地 `message_guard`：

- 无意义消息，如 `你好`、`hi`、`test`，直接本地回复并补发 FAQ 菜单模板，不调用 LLM。
- 敏感/高风险消息，如投诉、报警、高利贷、暴力催收、隐私泄露等，直接转人工并写入私有备注，不调用 LLM。
- 隐私字段，如手机号、身份证号、银行卡号、验证码、邮箱，会先脱敏，再进入后续 Agent 流程。
- 词库和话术统一维护在 `src/customer_agent/support_templates.py`。

如果要把 Chatwoot 历史同步到你自己的后台管理系统，在 `.env` 中配置：

```env
ADMIN_WEBHOOK_URL=https://你的后台地址/api/chatwoot/events
ADMIN_WEBHOOK_TOKEN=可选的BearerToken
```

网关会把支持的 Chatwoot 事件统一 `POST` 到 `ADMIN_WEBHOOK_URL`。如果这个变量为空，服务只会记录日志，不会真正发送到后台。

如果希望用户一开始发消息就出现在 Chatwoot 人工对话列表里，可以开启：

```env
CHATWOOT_OPEN_ON_INCOMING=true
```

开启后，每条公开用户消息触发 Agent 前，网关会先把对应会话状态切到 `open`。关闭或不配置时，会保持 Chatwoot 默认的 bot/pending 展示逻辑，只在转人工时打开会话。

## 私有备注自动翻译

如果希望人工座席看到用户外语消息的中文参考译文，可以开启：

```env
TRANSLATION_PRIVATE_NOTE_ENABLED=true
TRANSLATION_TARGET_LANG=zh-CN
TRANSLATION_SKIP_CHINESE=true
PYGTRANS_PROXY=
```

网关收到 `message_created + incoming + sender.type=contact` 的公开用户消息后，会用 `pygtrans.Translate` 翻译非中文内容，并作为 Chatwoot 私有备注写回当前会话。用户看不到这条备注，只有后台座席可见。

如果希望座席/AI 发出的中文消息再自动翻译成该会话用户语言，可以开启：

```env
TRANSLATION_OUTGOING_ENABLED=true
TRANSLATION_DEFAULT_USER_LANG=
```

系统会先从用户 incoming 消息中识别语言并按 `conversation_id` 缓存在内存里；之后检测到该会话出现中文 `outgoing` 公开消息时，会自动发送一条翻译后的公开回复。`TRANSLATION_DEFAULT_USER_LANG` 可作为服务重启后尚未识别到用户语言时的兜底值，例如 `en`、`ja`、`ko`。

## 使用真实 DeepSeek

在 `.env` 中配置：

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=你的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

## 使用 PostgreSQL

先保持：

```env
RAG_PROVIDER=memory
```

等知识库表建好后再切换：

```env
RAG_PROVIDER=pgvector
DB_HOST=你的数据库地址
DB_PORT=5432
DB_NAME=你的数据库名
DB_USER=你的用户名
DB_PASS=你的密码
KNOWLEDGE_SCHEMA=public
KNOWLEDGE_TABLE_NAME=knowledge_chunks
```

当前 `PgVectorRagStore` 预期存在 `knowledge_chunks` 表，包含：

```sql
id
chunk_text
metadata
search_vector
```

建表、索引和示例插入脚本统一放在：

```text
db/001_create_knowledge_chunks.sql
db/002_create_knowledge_indexes.sql
db/003_create_knowledge_chunk_upsert.sql
db/004_sample_inserts.sql
db/sample_chunks.json
scripts/import_knowledge_chunks.py
src/customer_agent/document_chunking.py
src/customer_agent/knowledge_ingestion.py
```

执行顺序见 `db/README.md`。

后续接 embedding 后，可以把 `PgVectorRagStore.search()` 的 SQL 改成全文检索 + `pgvector` 混合检索。

## 后续接入点

- PGVector：用 `RagStore.search()` 接口替换 `InMemoryRagStore`。
