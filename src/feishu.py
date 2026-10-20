"""飞书群机器人通知。"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

import config

logger = logging.getLogger(__name__)

# 与签到日志保持一致，用北京时间而非 runner 的 UTC
TZ = timezone(timedelta(hours=config.TZ_OFFSET_HOURS))


def send_message(title: str, content: str) -> dict:
    """发送文本消息到飞书群机器人。

    Returns:
        {"success": bool, "status_code": int, "response": str}
    """
    result = {"success": False, "status_code": None, "response": ""}
    webhook = config.FEISHU_WEBHOOK_URL

    if not webhook:
        result["response"] = "未配置 FEISHU_WEBHOOK_URL，跳过通知"
        logger.warning(result["response"])
        return result

    payload = {"msg_type": "text", "content": {"text": f"{title}\n\n{content}"}}

    try:
        resp = requests.post(
            webhook,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            timeout=15,
        )
        result["status_code"] = resp.status_code
        result["response"] = resp.text
        if resp.status_code == 200:
            result["success"] = True
            logger.info("飞书通知发送成功")
        else:
            logger.warning(f"飞书通知失败 [{resp.status_code}]: {resp.text}")
    except Exception as e:
        result["response"] = str(e)
        logger.exception("飞书通知异常")

    return result


# 签到状态 -> 中文说明
STATUS_TEXT = {
    "success": "签到成功",
    "already": "今日已签到",
    "failed": "签到失败",
    "session_lost": "会话失效",
    "unknown": "未知",
}


def notify_checkin_result(result: dict) -> dict:
    """根据签到结果构造并发送飞书通知。"""
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")

    success = result.get("success", False)
    status = result.get("checkin_status", "unknown")
    message = result.get("message", "")
    traffic = result.get("traffic", "")
    account = result.get("account", {}) or {}

    if not success:
        title = "❌ 69云签到 - 执行失败"
    elif status == "already":
        title = "✅ 69云签到 - 今日已签到"
    else:
        title = "✅ 69云签到 - 签到成功"

    lines = [
        f"时间：{now}",
        f"登录：{'成功' if result.get('login_success') else '失败'}",
        f"签到：{STATUS_TEXT.get(status, status)}",
    ]
    if traffic:
        lines.append(f"获得流量：{traffic}")
    if message:
        lines.append(f"消息：{message}")

    # 账户概况（有就带上，方便一眼看到剩余流量）
    if account:
        bits = []
        if account.get("traffic_remain"):
            bits.append(f"剩余 {account['traffic_remain']}")
        if account.get("traffic_used"):
            bits.append(f"已用 {account['traffic_used']}")
        if account.get("expire"):
            bits.append(f"到期 {account['expire']}")
        if account.get("level"):
            bits.append(account["level"])
        if bits:
            lines.append("账户：" + " / ".join(bits))

    return send_message(title, "\n".join(lines))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(
        notify_checkin_result(
            {
                "success": True,
                "login_success": True,
                "checkin_status": "success",
                "message": "尊贵的王者Lv7，您获得了 2.985GB 流量.",
                "traffic": "2.985GB",
                "account": {
                    "traffic_remain": "330.31GB",
                    "traffic_used": "93.54GB",
                    "expire": "2053-06-25",
                    "level": "王者Lv7",
                },
            }
        )
    )
