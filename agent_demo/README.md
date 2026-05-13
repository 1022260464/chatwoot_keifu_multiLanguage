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

Webhook 地址：

```text
http://你的服务地址:9090/webhook/chatwoot
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
```

当前 `PgVectorRagStore` 预期存在 `knowledge_chunks` 表，包含：

```sql
id
chunk_text
metadata
search_vector
```

后续接 embedding 后，可以把 `PgVectorRagStore.search()` 的 SQL 改成全文检索 + `pgvector` 混合检索。

## 后续接入点

- PGVector：用 `RagStore.search()` 接口替换 `InMemoryRagStore`。
