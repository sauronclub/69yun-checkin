"""69云每日自动签到入口。"""

import logging
import sys
from datetime import datetime, timedelta, timezone

import config
from src.checkin import run_checkin
from src.feishu import notify_checkin_result


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logger = logging.getLogger(__name__)

    tz = timezone(timedelta(hours=config.TZ_OFFSET_HOURS))
    logger.info("=" * 50)
    logger.info("69云签到任务启动")
    logger.info(f"当前时间：{datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')} (UTC+{config.TZ_OFFSET_HOURS})")
    logger.info("=" * 50)

    result = run_checkin()

    logger.info("-" * 50)
    logger.info(f"执行成功：{result.get('success')}")
    logger.info(f"登录成功：{result.get('login_success')}")
    logger.info(f"签到状态：{result.get('checkin_status')}")
    logger.info(f"消息：{result.get('message')}")
    logger.info("-" * 50)

    notify = notify_checkin_result(result)
    logger.info(f"飞书通知发送成功：{notify.get('success')}")

    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
