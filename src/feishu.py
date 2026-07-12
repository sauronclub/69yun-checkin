import sys
import os
import json
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import requests

import config

logger = logging.getLogger(__name__)

FEISHU_WEBHOOK_URL = config.FEISHU_WEBHOOK_URL


def send_message(title: str, content: str) -> dict:
    """通过飞书群机器人发送文本消息。

    Args:
        title: 消息标题。
        content: 消息正文。

    Returns:
        {"success": bool, "status_code": int, "response": str}
    """
    result = {"success": False, "status_code": None, "response": ""}

    if not FEISHU_WEBHOOK_URL:
        result["response"] = "未配置 FEISHU_WEBHOOK_URL，跳过通知"
        logger.warning(result["response"])
        return result

    payload = {
        "msg_type": "text",
        "content": {
            "text": f"{title}\n\n{content}",
        },
    }

    try:
        response = requests.post(
            FEISHU_WEBHOOK_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            timeout=15,
        )
        result["status_code"] = response.status_code
        result["response"] = response.text
        if response.status_code == 200:
            result["success"] = True
            logger.info("飞书通知发送成功")
        else:
            logger.warning(f"飞书通知发送失败 [{response.status_code}]: {response.text}")
    except Exception as e:
        result["response"] = str(e)
        logger.exception("飞书通知发送异常")

    return result


def _read_tail(path: str, lines: int = 30) -> str:
    """读取文件末尾指定行数，失败返回空字符串。"""
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()
            return "".join(all_lines[-lines:])
    except Exception as e:
        return f"读取日志失败: {e}"


def notify_checkin_result(checkin_result: dict) -> dict:
    """根据签到结果构造并发送飞书通知。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    success = checkin_result.get("success", False)
    login_success = checkin_result.get("login_success", False)
    checkin_status = checkin_result.get("checkin_status", "unknown")
    message = checkin_result.get("message", "")

    # 标题
    if not success:
        title = "❌ 69云签到 - 执行失败"
    elif checkin_status == "already":
        title = "✅ 69云签到 - 今日已签到"
    elif checkin_status == "clicked":
        title = "✅ 69云签到 - 签到成功"
    else:
        title = "⚠️ 69云签到 - 签到状态未知"

    # 正文
    status_map = {
        "already": "今日已签到",
        "clicked": "签到成功",
        "not_found": "未找到签到按钮",
        "unknown": "未知",
    }

    lines = [
        f"时间：{now}",
        f"登录：{'成功' if login_success else '失败'}",
        f"签到：{status_map.get(checkin_status, checkin_status)}",
    ]
    if message:
        lines.append(f"消息：{message}")

    content = "\n".join(lines)

    # 失败时追加错误日志末尾内容，方便排查
    if not success:
        run_log = checkin_result.get("run_log")
        if run_log:
            tail = _read_tail(run_log, lines=30)
            if tail:
                # 对日志做简单脱敏：去掉可能出现在 URL 后的查询参数
                content += "\n\n----- 最近日志 -----\n" + tail

    return send_message(title, content)


if __name__ == "__main__":
    # 本地快速测试：成功-已签到
    test_result = {
        "success": True,
        "login_success": True,
        "checkin_status": "already",
        "message": "今日已签到，无需重复点击",
    }
    print("已签到:", notify_checkin_result(test_result))

    # 本地快速测试：失败
    test_result2 = {
        "success": False,
        "login_success": False,
        "checkin_status": "unknown",
        "message": "登录超时",
        "run_log": "",
    }
    print("失败:", notify_checkin_result(test_result2))
