# Chatwoot 翻译功能运营说明

这份文档面向运营和客服管理人员，用来说明本项目里的 Chatwoot 自动翻译功能是如何工作的，以及出现问题时应该优先检查哪些配置。

## 功能目标

该翻译功能主要解决跨语言客服场景：

- 用户发外语消息时，系统自动翻译成中文，作为 Chatwoot 私有备注展示给客服。
- AI 或客服用中文回复时，系统可以自动翻译成用户语言，再发送给用户。
- 翻译内容不会替换用户原始消息，原文仍然保留在 Chatwoot 对话里。

## 默认翻译服务

当前默认使用 Google 翻译能力，对应项目里的配置是：

```env
TRANSLATION_PROVIDER=pygtrans
```

`pygtrans` 是一个 Python 翻译库，项目通过它调用 Google 翻译的翻译和语言检测能力。

如果未来切换为 DeepSeek 翻译，可以改为：

```env
TRANSLATION_PROVIDER=deepseek
```

但运营侧默认只需要知道：当前默认是 Google 翻译。

## 入站翻译：用户消息翻译给客服看

当用户在 Chatwoot 里发送一条公开消息时，系统会收到 Chatwoot webhook。

只有满足以下条件的消息才会触发翻译：

- 事件类型是 `message_created`
- 消息类型是 `incoming`
- 不是私有备注
- 消息内容不为空
- 消息来自用户或访客

触发后，系统会把用户消息翻译成中文，并写入当前会话的私有备注。

客服在 Chatwoot 后台看到的效果类似：

```text
[AI translation]
您好，我想了解退款政策。
```

这条私有备注只有后台客服能看到，用户看不到。

## 与 FAQ 快捷菜单的关系

FAQ 菜单不会跳过原有语言识别流程。用户第一条公开消息进入后，系统会先识别语言，并按配置生成中文私有备注翻译；随后才判断是否发送 FAQ 菜单。

当前只有以下语言会自动发送 FAQ 菜单：

```text
中文
英文
越南语
```

如果识别到其它语言，系统不会弹 FAQ 菜单，会继续走原来的 Agent / 翻译流程。这样可以避免把中文、英文、越南语之外的固定模板错误发给用户。

FAQ 菜单本身分成两条公开消息：第一条是普通说明气泡，第二条是按钮气泡。用户点击按钮后，后端会直接回复对应语言的标准答案，不调用 LLM。

## 出站翻译：中文回复翻译给用户看

如果开启了出站翻译，AI 或客服发出的中文内容可以自动翻译成用户语言。

开关是：

```env
TRANSLATION_OUTGOING_ENABLED=true
```

典型场景：

1. 用户用英文发消息。
2. 系统识别出该会话用户语言是英文。
3. AI 或客服用中文回复。
4. 系统自动把中文翻译成英文。
5. 翻译后的英文作为公开消息发给用户。

如果是 AI 回复，系统还会保留一条私有备注，记录原始中文回复：

```text
[Original AI reply]
您好，我们支持 7 天内退款。
```

这样客服可以同时看到“发给用户的外语内容”和“系统原始中文内容”。

## 系统如何识别用户是什么语言

系统会在用户发消息时自动识别语言，并按 Chatwoot 会话 ID 缓存。

识别逻辑分两步：

### 第一步：本地快速判断

系统会先做简单判断：

- 如果内容包含中文，认为是中文。
- 如果内容是纯英文字符，认为是英文。

这样可以减少不必要的外部翻译接口调用。

### 第二步：Google 自动检测

如果本地无法判断，比如：

- 日语
- 韩语
- 越南语
- 法语
- 西班牙语
- 阿拉伯语
- 俄语

系统会调用 Google 翻译的语言检测能力，自动识别语言。

识别结果会保存到内存里，格式可以理解为：

```text
会话 123 -> 英文
会话 456 -> 日文
会话 789 -> 韩文
```

后续同一个会话里，如果客服发中文，系统就知道应该翻译成哪种语言。

## 语言缓存说明

当前语言缓存保存在服务内存里。

这意味着：

- 同一个会话中，用户第一次发外语消息后，系统会记住该会话语言。
- 服务重启后，内存缓存会丢失。
- 如果服务刚重启，还没有识别到用户语言，出站翻译可能暂时不会触发。

可以设置默认用户语言作为兜底：

```env
TRANSLATION_DEFAULT_USER_LANG=en
```

例如主要客户都是英文用户，可以设置为 `en`。

## 常用配置

### 开启用户消息翻译成中文私有备注

```env
TRANSLATION_PRIVATE_NOTE_ENABLED=true
TRANSLATION_TARGET_LANG=zh-CN
```

### 跳过中文消息翻译

```env
TRANSLATION_SKIP_CHINESE=true
```

开启后，如果用户发中文，系统不会再生成中文翻译备注，避免重复。

### 开启中文回复自动翻译成用户语言

```env
TRANSLATION_OUTGOING_ENABLED=true
```

### 设置翻译超时时间

```env
TRANSLATION_TIMEOUT_SECONDS=8
```

如果 Google 翻译响应超过 8 秒，系统会放弃本次翻译，避免影响主流程。

### 设置 Google 翻译代理

如果服务器访问 Google 翻译不稳定，可以配置代理：

```env
PYGTRANS_PROXY=http://127.0.0.1:7890
```

## 推荐运营配置

如果业务主要是“外语用户咨询，中文客服处理”，推荐：

```env
TRANSLATION_PROVIDER=pygtrans
TRANSLATION_PRIVATE_NOTE_ENABLED=true
TRANSLATION_TARGET_LANG=zh-CN
TRANSLATION_SKIP_CHINESE=true
TRANSLATION_OUTGOING_ENABLED=true
TRANSLATION_DEFAULT_USER_LANG=
TRANSLATION_TIMEOUT_SECONDS=8
```

如果大部分用户都是英文，可以增加：

```env
TRANSLATION_DEFAULT_USER_LANG=en
```

## 哪些内容不会被翻译

以下内容不会触发用户入站翻译：

- Chatwoot 私有备注
- 客服或 AI 发出的普通 outgoing 消息
- 空消息
- 非 `message_created` 事件
- 中文消息，且开启了 `TRANSLATION_SKIP_CHINESE=true`
- 太短的消息，短于 `TRANSLATION_MIN_TEXT_LENGTH`

以下内容不会触发出站翻译：

- 没有开启 `TRANSLATION_OUTGOING_ENABLED`
- 系统不知道当前会话的用户语言
- 目标语言是中文
- 出站内容不包含中文
- 系统自己生成的翻译备注

## Chatwoot 里的展示效果

用户发英文：

```text
I want to know your refund policy.
```

客服后台会看到私有备注：

```text
[AI translation]
我想了解你们的退款政策。
```

如果客服回复中文：

```text
您好，我们支持 7 天内退款。
```

用户实际收到：

```text
Hello, we support refunds within 7 days.
```

客服后台可能还会看到系统备注，用于追踪原始中文：

```text
[Original AI reply]
您好，我们支持 7 天内退款。
```

## 排查问题

### 用户外语消息没有生成中文备注

优先检查：

```env
TRANSLATION_PRIVATE_NOTE_ENABLED=true
```

然后确认：

- 消息是不是用户公开消息。
- 消息是不是私有备注。
- 内容是不是太短。
- 服务器是否能访问 Google 翻译。
- `pygtrans` 是否已安装。

### 客服中文回复没有自动翻译给用户

优先检查：

```env
TRANSLATION_OUTGOING_ENABLED=true
```

然后确认：

- 系统是否已经识别过该会话用户语言。
- 服务是否刚重启导致语言缓存丢失。
- 是否配置了 `TRANSLATION_DEFAULT_USER_LANG`。
- 客服回复内容是否包含中文。

### 翻译偶尔失败

常见原因：

- Google 翻译网络不稳定。
- 服务器无法访问 Google。
- 翻译请求超时。
- 代理配置不可用。

可以检查：

```env
PYGTRANS_PROXY=
TRANSLATION_TIMEOUT_SECONDS=8
```

## 注意事项

- 自动翻译适合客服辅助，不建议作为法律、合同、医疗等高风险内容的唯一依据。
- 机器翻译可能存在语气或术语误差，客服需要结合原文判断。
- 如果客服手动修改翻译后的内容，需要以实际发出的公开消息为准。
- 服务重启会清空会话语言缓存，如需要长期稳定保存语言，可后续扩展为数据库存储。
