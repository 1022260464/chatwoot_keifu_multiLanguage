from __future__ import annotations

import os
from typing import Any

from flask import Flask, jsonify, request
import requests


app = Flask(__name__)

# 企业微信机器人 Webhook 地址。生产环境建议用环境变量覆盖，避免把 key 写死在代码里。
WECOM_WEBHOOK_URL = os.getenv(
    "WECOM_WEBHOOK_URL",
    "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=0cab60e3-dead-49c2-b4ae-c087981369d6",
)


def _field_value(fields: list[dict[str, Any]], *names: str) -> str:
    expected = {name.lower() for name in names}
    for field in fields:
        title = str(field.get("title", "")).strip().lower()
        if title in expected:
            return str(field.get("value", "")).strip()
    return ""


def _extract_alert(data: dict[str, Any]) -> dict[str, str]:
    """兼容 GlitchTip Alert Webhook 和手动 curl 的简单测试 JSON。"""
    attachments = data.get("attachments")
    attachment = attachments[0] if isinstance(attachments, list) and attachments else {}
    fields = attachment.get("fields") if isinstance(attachment, dict) else []
    fields = fields if isinstance(fields, list) else []

    project = (
        str(data.get("project_name") or data.get("project") or "").strip()
        or _field_value(fields, "Project", "Project Name")
        or "未知项目"
    )
    environment = (
        str(data.get("environment") or "").strip()
        or _field_value(fields, "Environment")
        or "未知环境"
    )
    server_name = (
        str(data.get("server_name") or data.get("server") or "").strip()
        or _field_value(fields, "Server Name", "Server")
        or "未知服务器"
    )
    location = (
        str(data.get("culprit") or data.get("transaction") or data.get("location") or "").strip()
        or str(attachment.get("text") or "").strip()
        or _field_value(fields, "Culprit", "Transaction", "Location", "URL", "Path")
        or ""
    )
    message = (
        str(data.get("message") or "").strip()
        or str(attachment.get("title") or "").strip()
        or str(data.get("text") or "").strip()
        or "无错误详情"
    )
    url = (
        str(data.get("url") or "").strip()
        or str(attachment.get("title_link") or "").strip()
        or str(attachment.get("footer_link") or "").strip()
    )
    level = (
        str(data.get("level") or "").strip()
        or _field_value(fields, "Level", "Severity")
        or "error"
    )

    return {
        "project": project,
        "environment": environment,
        "server_name": server_name,
        "location": location,
        "message": message,
        "url": url,
        "level": level,
    }


@app.route("/glitchtip", methods=["POST"])
def receive_glitchtip_alert():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "No JSON object received"}), 400

    alert = _extract_alert(data)
    level = alert["level"].upper()
    color = "warning" if level in {"ERROR", "FATAL", "WARNING"} else "info"
    report_link = alert["url"] or ""
    location = alert["location"] or f"{alert['environment']} / {alert['server_name']}"
    link_line = f"> [点击查看完整报告]({report_link})" if report_link else "> 完整报告链接：未提供"

    wecom_payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": (
                f"**<font color='{color}'>GlitchTip 异常告警</font>**\n"
                f"> **项目:** {alert['project']}\n"
                f"> **级别:** <font color='{color}'>{level}</font>\n"
                f"> **环境:** {alert['environment']}\n"
                f"> **服务器:** {alert['server_name']}\n"
                f"> **位置:** {location}\n"
                f"> **详情:** {alert['message']}\n"
                f"{link_line}"
            )
        },
    }

    try:
        response = requests.post(WECOM_WEBHOOK_URL, json=wecom_payload, timeout=10)
        response.raise_for_status()
    except Exception as exc:
        app.logger.exception("Failed to forward GlitchTip alert to WeCom")
        return jsonify({"status": "failed", "error": str(exc)}), 500

    return jsonify({"status": "success"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
