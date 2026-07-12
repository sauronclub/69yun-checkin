import sys
import logging
from datetime import datetime

from src.checkin import run_checkin
from src.feishu import notify_checkin_result

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main():
    logger.info("=" * 50)
    logger.info("69云签到任务启动")
    logger.info(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 执行签到（checkin 内部已做好：不打印账号密码、不记录请求体中的密码）
    result = run_checkin()

    # 打印结果摘要（仅包含状态、页面、消息，不包含敏感信息）
    logger.info("-" * 50)
    logger.info(f"执行成功: {result.get('success')}")
    logger.info(f"登录成功: {result.get('login_success')}")
    logger.info(f"签到状态: {result.get('checkin_status')}")
    logger.info(f"当前页面: {result.get('current_url')}")
    logger.info(f"消息: {result.get('message')}")
    logger.info("-" * 50)

    # 发送飞书通知（失败时会自动附带最近日志）
    notify_result = notify_checkin_result(result)
    logger.info(f"通知发送成功: {notify_result.get('success')}")

    # 执行失败时返回非零退出码，让 GitHub Actions 标记为失败
    if not result.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()
