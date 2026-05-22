# Dashboard API 说明

本文档说明 Agent Demo 提供给前端运营仪表盘调用的接口。运营页面会自动拉取 Chatwoot 会话列表，运营人员勾选目标会话即可群发，不需要手动查找 conversation ID。

## 安全说明

前端不要直接保存或调用 Chatwoot 的 `api_access_token`。

正确方式是：

1. 后端 `.env` 中配置 Chatwoot Token。
2. 后端 `.env` 中配置单独的 `DASHBOARD_API_TOKEN`。
3. 前端只访问 Agent Demo 的 dashboard 接口。
4. 后端代替前端调用 Chatwoot API。

## 必要配置

在 `agent_demo/.env` 中配置：

```env
CHATWOOT_BASE_URL=http://你的Chatwoot地址
CHATWOOT_ACCOUNT_ID=1
CHATWOOT_API_ACCESS_TOKEN=你的ChatwootToken
DASHBOARD_API_TOKEN=前端访问Dashboard接口用的Token
```

修改 `.env` 后重启服务：

```bash
sudo systemctl restart agent_demo.service
```

## 获取会话列表接口

前端通过这个接口自动识别和展示 Chatwoot 会话 ID。

接口地址：

```http
GET /dashboard/conversations
```

请求头：

```http
X-Dashboard-Token: 你的DASHBOARD_API_TOKEN
```

查询参数：

- `status`：会话状态，例如 `open`、`pending`、`resolved`，为空表示全部。
- `q`：搜索关键词，可填客户名、邮箱或关键词。
- `page`：页码，默认 `1`。

响应示例：

```json
{
  "total": 2,
  "conversations": [
    {
      "id": "123",
      "display_name": "Nguyen Van A",
      "email": "user@example.com",
      "status": "open",
      "inbox_id": "1",
      "last_activity_at": "1715670000",
      "assignee_name": "客服A"
    }
  ]
}
```

前端页面会把这里的 `id` 自动作为群发目标，不需要运营手动填写。

## 群发消息接口

接口地址：

```http
POST /dashboard/mass-messages
```

完整示例：

```http
POST http://服务器地址:9090/dashboard/mass-messages
```

## Vue 前端工程

当前项目里已经提供一个独立 Vue 3 前端工程：

```text
frontend/dashboard/
```

工程技术栈：

- Vue 3
- Vite
- TypeScript
- Element Plus

目录结构：

```text
frontend/dashboard/
  package.json
  vite.config.ts
  src/
    main.ts
    App.vue
    features/
      mass-message/
        MassMessageView.vue
        components/
        composables/
        types.ts
```

启动前端开发服务：

```bash
cd /mnt/chawoot_houduan_agent/agent_demo/frontend/dashboard/
npm install
npm run dev
```

默认访问：

```text
http://服务器地址:5173
```

开发环境下，`vite.config.ts` 已经配置代理：

```text
/dashboard/* -> http://127.0.0.1:9090
```

所以前端页面可以直接请求：

```text
/dashboard/mass-messages
```

请求头：

```http
Content-Type: application/json
X-Dashboard-Token: 你的DASHBOARD_API_TOKEN
```

请求体：

```json
{
  "conversation_ids": ["1", "2", "3"],
  "content": "您好！这是一条通过仪表盘群发的消息测试。",
  "private": false,
  "delay_seconds": 0.5,
  "translate_before_send": true,
  "target_language": "en"
}
```

字段说明：

- `conversation_ids`：目标 Chatwoot 会话 ID 列表，最多 200 个。前端会从已勾选的会话中自动生成。
- `content`：要发送的消息内容。
- `private`：`false` 表示客户可见公开消息，`true` 表示仅客服可见私有备注。
- `delay_seconds`：每个会话之间的发送间隔，默认 0.5 秒，避免发送过快。
- `translate_before_send`：发送前是否先翻译内容。
- `target_language`：手动选择的目标语言，例如 `en`、`vi`、`ja`、`ko`、`th`。

注意：仪表盘群发的翻译是在发送接口里主动调用翻译模块完成，不依赖 Chatwoot webhook。

响应示例：

```json
{
  "total": 3,
  "success": 2,
  "failed": 1,
  "results": [
    {
      "conversation_id": "1",
      "ok": true,
      "error": ""
    },
    {
      "conversation_id": "2",
      "ok": true,
      "error": ""
    },
    {
      "conversation_id": "3",
      "ok": false,
      "error": "Chatwoot API error 404: ..."
    }
  ]
}
```

## curl 测试

```bash
curl -X POST "http://127.0.0.1:9090/dashboard/mass-messages" \
  -H "Content-Type: application/json" \
  -H "X-Dashboard-Token: 你的DASHBOARD_API_TOKEN" \
  -d '{
    "conversation_ids": ["1"],
    "content": "您好！这是一条测试消息。",
    "private": false,
    "delay_seconds": 0.5,
    "translate_before_send": false,
    "target_language": ""
  }'
```

## 前端使用方式

运营人员只需要：

1. 打开前端仪表盘。
2. 点击“刷新会话”。
3. 勾选要群发的会话。
4. 填写群发内容。
5. 如需翻译，开启“发送前翻译”并选择目标语言。
6. 点击“开始群发”。

如果自动列表里确实找不到目标会话，也可以在“高级备用：手动补充会话 ID”里补充 ID。

## 前端调用示例

```javascript
await fetch('/dashboard/mass-messages', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Dashboard-Token': dashboardToken,
  },
  body: JSON.stringify({
    conversation_ids: ['1', '2', '3'],
    content: '您好！这是一条群发消息。',
    private: false,
    delay_seconds: 0.5,
    translate_before_send: true,
    target_language: 'en',
  }),
})
```

## 常见问题

### 返回 `DASHBOARD_API_TOKEN is not configured`

说明后端 `.env` 没有配置：

```env
DASHBOARD_API_TOKEN=
```

配置后重启后端服务；如果使用前端页面，也要重启或重新构建前端，因为页面启动时会读取该 Token。

### 返回 `Invalid dashboard token`

说明请求头里的 `X-Dashboard-Token` 和 `.env` 里的 `DASHBOARD_API_TOKEN` 不一致。前端页面不会展示 Token，它会在启动或构建时从 `agent_demo/.env` 读取。

### 所有会话都发送失败

优先检查：

```env
CHATWOOT_BASE_URL=
CHATWOOT_ACCOUNT_ID=
CHATWOOT_API_ACCESS_TOKEN=
```

这三个配置必须正确。

### 部分会话发送失败

常见原因：

- 会话 ID 不存在。
- 会话不属于当前 `CHATWOOT_ACCOUNT_ID`。
- Chatwoot API Token 权限不足。
- Chatwoot 服务暂时不可用。
