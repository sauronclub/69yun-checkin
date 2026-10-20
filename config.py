# 69云签到 - 配置
# 所有配置均来自环境变量（或 .env 文件），不硬编码任何敏感信息

import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _env(key: str, default: str = "") -> str:
    """读环境变量。空值或纯空白视为「未设置」，回退到默认值。

    GitHub Actions 里 `${{ vars.X }}` 在变量不存在时会展开成空字符串，
    直接覆盖默认值会导致 BASE_URL 变空、拼出 `/auth/login` 这种非法 URL。
    这里统一做兜底。
    """
    val = os.environ.get(key, "")
    val = val.strip() if isinstance(val, str) else val
    return val if val else default


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

# ---- 站点 ----
# 面板根地址（含 uuid 前缀的那一层）
#
# 默认用 ui567u.337979.xyz：这是机场官网上挂的面板入口之一，
# 证书有效，SSL 校验可直接通过（已在严格校验下验证 HTTP 200）。
#
# 同一面板还有多个等价入口，证书指纹一致，可互换：
#   ui567u.337979.xyz / yydeee.337979.xyz
#
# 不要用这些：
#   china_69yun.337979.xyz —— 面板本身，但证书只签发 *.69yun69.com，
#     主机名不匹配会让 requests 抛 SSLError，GitHub Actions 必然失败
#     （浏览器能打开只是因为它对这类错误更宽容）
#   china.69yun69.net / 69yun69.com —— 是官网，不是 API 端点，
#     请求登录接口会返回 HTML 而非 JSON
BASE_URL = _env("BASE_URL", "https://ui567u.337979.xyz/uuid").rstrip("/")

# 登录接口，默认由 BASE_URL 推导
LOGIN_URL = _env("LOGIN_URL") or f"{BASE_URL}/auth/login"
# 用户中心，主要用于读取账户信息
USER_URL = _env("USER_URL") or f"{BASE_URL}/user"
# 签到接口
CHECKIN_URL = _env("CHECKIN_URL") or f"{BASE_URL}/user/checkin"

# ---- 账号 ----
YUN_EMAIL = _env("YUN_EMAIL")
YUN_PASSWORD = _env("YUN_PASSWORD")

# ---- 通知 ----
FEISHU_WEBHOOK_URL = _env("FEISHU_WEBHOOK_URL")

# ---- 配置自检 ----
if not BASE_URL.startswith(("http://", "https://")):
    raise ValueError(
        f"BASE_URL 配置无效: {BASE_URL!r}\n"
        "应为形如 https://域名/uuid 的完整地址。"
        "若在 GitHub Actions Variables 中留空，请直接删除该变量而不是留空值。"
    )

if not VERIFY_SSL and not _flag("ALLOW_INSECURE_SSL", False):
    # 关闭证书校验是安全降级，仅在明确知情时放行
    logger.warning("=" * 60)
    logger.warning("VERIFY_SSL=false：已关闭 TLS 证书校验，传输不再防中间人。")
    logger.warning("首选做法是改用证书有效的域名（见本文件 BASE_URL 处注释）。")
    logger.warning("确认要继续可设 ALLOW_INSECURE_SSL=1 消除此提示。")
    logger.warning("=" * 60)