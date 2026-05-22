# Agent Demo 运营仪表盘

这是 Agent Demo 的前端运营仪表盘工程，基于 Vue 3、Vite、TypeScript 和 Element Plus。

当前功能是 Chatwoot 会话群发，面向运营和客服主管使用：

- 自动从 Chatwoot 拉取会话列表
- 勾选目标会话，不需要手动找 conversation ID
- 支持按状态筛选会话
- 支持按客户姓名、邮箱或关键词搜索
- 支持公开消息和内部备注
- 支持发送前手动选择目标语言并自动翻译
- 支持发送间隔，避免请求过快
- 支持查看每个会话的发送结果

## 目录结构

```text
frontend/dashboard/
  index.html
  package.json
  vite.config.ts
  tsconfig.json
  src/
    main.ts
    App.vue
    styles/main.css
    features/
      mass-message/
        MassMessageView.vue
        types.ts
        components/
          ConversationPicker.vue
          MassMessageForm.vue
          MassMessageResultTable.vue
        composables/
          useDashboardConversations.ts
          useMassMessages.ts
```

## 本地启动

先启动后端 FastAPI。后端负责保存 Chatwoot Token，并提供中转接口：

```bash
cd /mnt/chawoot_houduan_agent/agent_demo/
sudo systemctl restart agent_demo.service
```

本地开发前端：

```bash
cd /mnt/chawoot_houduan_agent/agent_demo/frontend/dashboard/
npm install
npm run dev
```

默认前端地址：

```text
http://服务器地址:5173
```

开发环境下，Vite 会把 `/dashboard/*` 代理到：

```text
http://127.0.0.1:9090
```

如果通过 `nip.io` 域名访问，例如：

```text
http://192.168.2.102.nip.io:5173
```

`vite.config.ts` 已默认允许 `192.168.2.102.nip.io`。如果后续换了别的测试域名，可以临时追加：

```bash
VITE_ALLOWED_HOSTS=你的新域名 npm run dev
```

也可以写入 `agent_demo/.env`：

```env
VITE_ALLOWED_HOSTS=chat.wupiantech.com,其他测试域名
```

注意：修改 `vite.config.ts` 后，需要重启前端 `npm run dev`，只重启后端 Python 服务不会生效。

## 后端必要配置

`agent_demo/.env` 需要配置：

```env
CHATWOOT_BASE_URL=http://你的Chatwoot地址
CHATWOOT_ACCOUNT_ID=1
CHATWOOT_API_ACCESS_TOKEN=你的ChatwootToken
DASHBOARD_API_TOKEN=前端页面自动使用的DashboardToken
```

`DASHBOARD_API_TOKEN` 不会显示在页面输入框里，前端启动或构建时会从 `agent_demo/.env` 读取并自动带到请求头里。

修改后需要重启后端和前端：

```bash
sudo systemctl restart agent_demo.service
cd /mnt/chawoot_houduan_agent/agent_demo/frontend/dashboard/
npm run dev
```

## 生产构建

```bash
cd /mnt/chawoot_houduan_agent/agent_demo/frontend/dashboard/
npm run build
```

构建产物在：

```text
frontend/dashboard/dist/
```

可以用 Nginx 托管 `dist`，并把 `/dashboard/` API 请求反向代理到 FastAPI 的 `9090` 端口。

## 后续扩展建议

后续新增功能时，建议继续按 feature 拆目录：

```text
src/features/
  mass-message/
  contact-segment/
  message-template/
  send-history/
```

每个功能内部保持：

```text
components/
composables/
types.ts
FeatureView.vue
```
