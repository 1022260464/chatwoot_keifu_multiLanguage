# Chatwoot 出站翻译重复发送问题日志报告

生成日期：2026-05-29  
涉及服务：`agent_demo.service` / Chatwoot Webhook 网关  
涉及会话：`conversation_id=58`

## 1. 问题概述

测试过程中发现 Chatwoot 会话中出现中文公开回复和越南语翻译回复重复展示的情况，看起来像“循环发送”。

经日志分析，问题不是用户消息反复触发 Agent 主流程，而是 Chatwoot 的 `outgoing` 公开消息触发了出站翻译模块。系统把已经公开发给用户的中文消息再次翻译成越南语，并通过 Chatwoot API 再发送一条公开消息，因此用户侧会看到重复回复。

## 2. 关键日志

### 2.1 打开聊天窗口但未发送消息

```text
Skipped FAQ menu because conversation_id or language is missing event=webwidget_triggered conversation_id=unknown language=unknown
Skipped Agent processing reason=Not a message_created event
Synced Chatwoot event=webwidget_triggered conversation_id=unknown message_type=unknown sender_type=unknown
```

说明：

- `webwidget_triggered` 只是访客打开聊天气泡。
- 此时 Chatwoot 通常还没有创建有效会话，因此 `conversation_id=unknown` 是正常现象。
- 该日志不属于错误，不会触发 Agent 主流程。

### 2.2 出站公开消息触发翻译

```text
Skipped Agent processing reason=Not an incoming user message
Synced Chatwoot event=message_created conversation_id=58 message_type=outgoing sender_type=user
Sent Chatwoot message conversation_id=58 private=False
Sent outgoing translation conversation_id=58 target_language=vi
```

说明：

- `message_type=outgoing` 表示消息来自客服侧或系统侧，不是访客发来的消息。
- Agent 主流程正确跳过了这条消息：`Not an incoming user message`。
- 但出站翻译模块继续处理了这条公开消息。
- 系统随后调用 Chatwoot API 发送了一条新的公开翻译消息：`private=False`。

## 3. 用户侧表现

用户可能先看到中文公开消息：

```text
您好，我们已经收到您的问题，请稍等，人工客服会继续为您处理。
```

随后又看到越南语翻译消息：

```text
Xin chào, chúng tôi đã nhận được câu hỏi của bạn, vui lòng chờ một chút, nhân viên hỗ trợ sẽ tiếp tục xử lý cho bạn.
```

这会造成两个问题：

- 中文内容先暴露给越南语用户，体验不专业。
- 系统自己发送的新公开消息也会再次触发 Chatwoot webhook，存在重复触发风险。

## 4. 根因分析

原逻辑中，开启以下配置后：

```env
TRANSLATION_OUTGOING_ENABLED=true
```

系统会监听 `message_created + outgoing` 消息，并尝试把中文内容翻译成会话语言。

旧逻辑没有严格区分：

- 客服公开回复
- 客服私有备注草稿
- 系统自己发出的公开翻译消息

因此，当客服或系统发出一条中文公开消息时，出站翻译模块会把它当成“待翻译草稿”，再次发送一条公开翻译消息。

## 5. 循环触发链路

```text
1. 客服/系统发送一条公开中文消息
   ↓
2. Chatwoot 触发 webhook：message_created + outgoing
   ↓
3. Agent 主流程跳过：Not an incoming user message
   ↓
4. 出站翻译模块检测到中文内容
   ↓
5. 系统发送越南语公开翻译消息
   ↓
6. Chatwoot 再次触发 webhook：message_created + outgoing
```

如果系统没有识别并跳过自己生成的消息，就可能继续重复触发。

## 6. 修复方案

已调整出站翻译策略：

- 不再翻译公开 `outgoing` 消息。
- 只允许客服使用 **私有备注** 作为中文草稿触发翻译。
- 系统检测到中文私有备注后，再把翻译结果作为公开消息发给用户。

修复后正确流程：

```text
1. 客服在 Chatwoot 后台写中文私有备注
   ↓
2. 用户看不到这条中文私有备注
   ↓
3. 系统翻译为越南语
   ↓
4. 系统发送越南语公开消息给用户
```

这样既避免中文直接暴露给用户，也避免公开消息再次触发出站翻译。

## 7. 相关代码变更

主要变更文件：

```text
agent_demo/src/main.py
```

核心逻辑：

- `_is_translatable_outgoing_message()` 增加判断：公开 outgoing 消息直接跳过。
- `translate_outgoing_to_user_language_task()` 不再对公开 outgoing 消息生成额外私有备注。

同时更新了文档说明：

```text
agent_demo/README.md
agent_demo/docs/ops_README.md
agent_demo/docs/translation_README.md
```

文档已明确：

- 客服不要用公开回复发送中文给外语用户。
- 客服需要发中文草稿时，应使用私有备注。
- 系统会把中文私有备注翻译后公开发送给用户。

## 8. 当前验证结果

已在本地执行语法检查：

```bash
uv run python -m py_compile src/main.py
```

结果：通过。

越南语有声调模板也已验证：

```bash
uv run python -m py_compile src/customer_agent/support_templates.py src/customer_agent/faq_config.py src/main.py
```

结果：通过。

## 9. 建议测试流程

### 9.1 测试 FAQ 菜单

访客聊天框输入：

```text
xin chào
```

预期看到有声调越南语菜单：

```text
[Menu câu hỏi thường gặp] Chọn câu hỏi bên dưới để nhận câu trả lời có sẵn...
```

### 9.2 测试 FAQ 按钮

点击：

```text
Công ty / Sản phẩm
```

预期收到有声调越南语标准答案。

### 9.3 测试正常问题

访客输入：

```text
Tôi muốn hỏi về hạn mức vay, vì sao hạn mức của tôi thấp?
```

预期：

- Chatwoot 后台出现 `[AI translation]` 中文私有备注。
- Agent 进入处理流程。

### 9.4 测试客服中文私有备注翻译

客服后台使用 **私有备注** 输入：

```text
您好，我们已经收到您的问题，请稍等，人工客服会继续为您处理。
```

预期：

- 用户不会看到中文。
- 用户只看到越南语公开回复。
- 日志出现：

```text
Sent outgoing translation conversation_id=... target_language=vi
```

### 9.5 测试公开中文不会再触发翻译

客服后台直接发送公开中文：

```text
这是一条公开中文测试
```

预期：

- 用户会看到这条中文，因为这是客服直接公开发送的。
- 系统不会再补发越南语翻译。
- 日志不应出现新的：

```text
Sent outgoing translation conversation_id=... target_language=vi
```

## 10. 临时止血方案

如果服务器尚未部署修复代码，可临时关闭出站翻译：

```env
TRANSLATION_OUTGOING_ENABLED=false
```

然后重启服务：

```bash
sudo systemctl restart agent_demo.service
```

该方案会停止客服中文草稿自动翻译功能，但可以立即避免重复公开发送。

## 11. 后续建议

- 正式运营时，客服回复外语用户应使用“私有备注草稿”触发翻译。
- 不建议客服直接公开发送中文给越南语用户。
- 上线后观察日志中是否还出现异常的连续：

```text
message_created message_type=outgoing
Sent outgoing translation
```

- 如果仍出现重复发送，需要进一步检查 Chatwoot webhook 是否订阅了多个重复入口，或是否存在多个 Agent 服务实例同时处理同一 webhook。
