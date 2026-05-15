# Chatwoot User Admin Script

这个目录存放 Chatwoot 运维脚本。当前脚本用于在 Chatwoot 前端不显示“发送激活邮件”按钮时，直接从服务器后台处理客服账号验证。

## 文件

```text
chatwoot_user_admin.sh
```

## 使用前提

- 已经能 SSH 登录 Chatwoot 服务器。
- Chatwoot 使用 Docker Compose 部署。
- 在服务器的 Chatwoot 项目目录执行，通常是：

```bash
cd /home/ec2-user/chatwoot/scripts
```

脚本默认执行：

```bash
sudo docker compose exec -T rails bundle exec rails runner ...
```

如果你的 Rails 服务名不是 `rails`，或者不需要 `sudo`，可以通过环境变量覆盖。

## 上传和授权

把 `chatwoot_user_admin.sh` 上传到服务器的 `/home/ec2-user/chatwoot/` 目录，然后执行：

```bash
chmod +x chatwoot_user_admin.sh
```

## 发送官方验证邮件

这会触发 Chatwoot 官方的确认邮件，效果等同于前端“重新发送确认邮件”按钮。

```bash
./chatwoot_user_admin.sh send 2772471736@qq.com
```

## 强制激活并设置初始密码

默认初始密码是 `12345678`：

```bash
./chatwoot_user_admin.sh activate 2772471736@qq.com
```

也可以指定密码：

```bash
./chatwoot_user_admin.sh activate 2772471736@qq.com 'NewPassword123'
```

## 交互模式

不传参数时，脚本会提示选择操作并输入邮箱：

```bash
./chatwoot_user_admin.sh
```

## 常见覆盖配置

如果 Docker Compose 不需要 `sudo`：

```bash
COMPOSE_CMD="docker compose" ./chatwoot_user_admin.sh send user@example.com
```

如果 Rails 服务名不是 `rails`：

```bash
RAILS_SERVICE=chatwoot-rails ./chatwoot_user_admin.sh send user@example.com
```

如果想修改默认初始密码：

```bash
DEFAULT_PASSWORD='NewPassword123' ./chatwoot_user_admin.sh activate user@example.com
```

## 注意事项

- `send` 适合 SMTP 已打通、希望用户自己点邮件链接设置密码的场景。
- `activate` 会直接确认账号并重置密码，适合邮件不可用或需要立即开通的场景。
- 执行 `activate` 后，建议让客服首次登录后自行修改密码。
