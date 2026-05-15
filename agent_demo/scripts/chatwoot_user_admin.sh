#!/usr/bin/env bash
#
# Chatwoot user confirmation helper.
#
# Upload this file to the Chatwoot server, usually:
#   /home/ec2-user/chatwoot/chatwoot_user_admin.sh
#
# Then run:
#   chmod +x chatwoot_user_admin.sh
#   ./chatwoot_user_admin.sh send user@example.com
#   ./chatwoot_user_admin.sh activate user@example.com
#
set -euo pipefail

COMPOSE_CMD="${COMPOSE_CMD:-sudo docker compose}"
RAILS_SERVICE="${RAILS_SERVICE:-rails}"
DEFAULT_PASSWORD="${DEFAULT_PASSWORD:-12345678}"

usage() {
  cat <<'EOF'
Usage:
  ./chatwoot_user_admin.sh send EMAIL
  ./chatwoot_user_admin.sh activate EMAIL [PASSWORD]
  ./chatwoot_user_admin.sh

Actions:
  send      Resend Chatwoot official confirmation email.
  activate  Confirm the user and reset password.

Environment overrides:
  COMPOSE_CMD        Default: sudo docker compose
  RAILS_SERVICE      Default: rails
  DEFAULT_PASSWORD   Default: 12345678

Run this script on the Chatwoot server, inside /home/ec2-user/chatwoot.

Examples:
  chmod +x chatwoot_user_admin.sh
  ./chatwoot_user_admin.sh send 2772471736@qq.com
  ./chatwoot_user_admin.sh activate user@example.com
  ./chatwoot_user_admin.sh activate user@example.com 'NewPassword123'
EOF
}

is_email() {
  [[ "$1" =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]]
}

prompt_if_missing() {
  local action="${1:-}"
  local email="${2:-}"
  local password="${3:-}"

  if [[ -z "$action" ]]; then
    echo "请选择操作："
    echo "  1) 发送官方验证邮件"
    echo "  2) 强制激活并重置初始密码"
    read -r -p "输入 1 或 2: " choice
    case "$choice" in
      1) action="send" ;;
      2) action="activate" ;;
      *) echo "操作取消：无效选择。"; exit 1 ;;
    esac
  fi

  if [[ -z "$email" ]]; then
    read -r -p "请输入客服邮箱: " email
  fi

  if [[ "$action" == "activate" && -z "$password" ]]; then
    read -r -p "请输入初始密码 [${DEFAULT_PASSWORD}]: " password
    password="${password:-$DEFAULT_PASSWORD}"
  fi

  ACTION="$action"
  EMAIL="$email"
  PASSWORD="$password"
}

run_rails() {
  local ruby_code="$1"

  $COMPOSE_CMD exec -T \
    -e "CHATWOOT_TARGET_EMAIL=$EMAIL" \
    -e "CHATWOOT_TARGET_PASSWORD=${PASSWORD:-}" \
    "$RAILS_SERVICE" \
    bundle exec rails runner "$ruby_code"
}

send_confirmation() {
  run_rails "
email = ENV.fetch('CHATWOOT_TARGET_EMAIL')
user = User.find_by(email: email)

if user.nil?
  abort \"错误：找不到邮箱 #{email}。请先在 Chatwoot 后台添加该客服。\"
end

user.send_confirmation_instructions
puts \"成功：官方验证邮件已发送到 #{email}。\"
"
}

activate_user() {
  run_rails "
email = ENV.fetch('CHATWOOT_TARGET_EMAIL')
password = ENV.fetch('CHATWOOT_TARGET_PASSWORD')
user = User.find_by(email: email)

if user.nil?
  abort \"错误：找不到邮箱 #{email}。请先在 Chatwoot 后台添加该客服。\"
end

user.confirm unless user.confirmed?
user.password = password
user.password_confirmation = password

if user.save
  puts \"成功：账号已激活。登录邮箱：#{email}，初始密码：#{password}\"
else
  abort \"保存失败：#{user.errors.full_messages.join(', ')}\"
end
"
}

main() {
  if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
  fi

  prompt_if_missing "${1:-}" "${2:-}" "${3:-}"

  if [[ "$ACTION" != "send" && "$ACTION" != "activate" ]]; then
    echo "错误：未知操作 $ACTION"
    usage
    exit 1
  fi

  if ! is_email "$EMAIL"; then
    echo "错误：邮箱格式不正确：$EMAIL"
    exit 1
  fi

  if [[ "$ACTION" == "activate" && "${#PASSWORD}" -lt 8 ]]; then
    echo "错误：密码至少需要 8 位。"
    exit 1
  fi

  echo "正在连接 Chatwoot 容器处理 [$EMAIL] ..."
  case "$ACTION" in
    send) send_confirmation ;;
    activate) activate_user ;;
  esac
}

main "$@"
