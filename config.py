# 69云签到 - 配置
# 所有配置均来自环境变量（或 .env 文件），不硬编码任何敏感信息

import os

from dotenv import load_dotenv

load_dotenv()


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _flag(key: str, default: bool = False) -> bool:
    raw = _env(key)
    if not raw:
        return default
    return raw.lower() in ("1", "true", "yes", "on")


def _int(key: str, default: int) -> int:
    try:
        return int(_env(key))
    except ValueError:
        return default


# ---- 站点 ----
# 面板根地址（含 uuid 前缀的那一层，例如 https://xxx.com/uuid）
BASE_URL = _env("BASE_URL", "https://china_69yun.337979.xyz/uuid").rstrip("/")
# 登录接口，默认由 BASE_URL 推导
LOGIN_URL = _env("LOGIN_URL") or f"{BASE_URL}/auth/login"
# 用户中心，主要用于读取账户信息
USER_URL = _env("USER_URL") or f"{BASE_URL}/user"
# 签到接口
CHECKIN_URL = _env("CHECKIN_URL") or f"{BASE_URL}/user/checkin"

# ---- 账号 ----
YUN_EMAIL = _env("YUN_EMAIL")
YUN_PASSWORD = _env("YUN_PASSWORD")

# ---- 网络 ----
REQUEST_TIMEOUT = _int("REQUEST_TIMEOUT", 30)
REQUEST_RETRY = _int("REQUEST_RETRY", 3)
RETRY_BACKOFF = _int("RETRY_BACKOFF", 5)  # 秒，重试间隔基数（指数退避）
VERIFY_SSL = _flag("VERIFY_SSL", True)
USER_AGENT = _env(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
)

# ---- 通知 ----
FEISHU_WEBHOOK_URL = _env("FEISHU_WEBHOOK_URL")
