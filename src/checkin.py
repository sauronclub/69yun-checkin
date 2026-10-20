"""
69云（Metron / V2Board 面板）自动签到核心逻辑。

设计要点
--------
1. 纯 HTTP 实现，不依赖浏览器。实测该面板的签到就是两个 XHR：
       POST {base}/auth/login      参数 email / passwd
       POST {base}/user/checkin    无参数，靠 Cookie 里的会话
   原先用 Playwright 模拟点击，页面一改版选择器就全失效，且 CI 里要装
   几百 MB 浏览器；这里直接打接口，快且稳。

2. 返回码语义（已实测）：
       ret == 1  签到成功，msg 里带本次获得的流量
       ret == 0  今日已签到过，不算失败
       其他      异常，msg 会说明原因

3. 任何异常都不打印账号密码；日志里的 URL 统一去掉查询串。
"""

import logging
import re
import time
from datetime import datetime

import requests

import config

logger = logging.getLogger(__name__)

# 面板返回给浏览器的标识，缺失时部分站点会判定为非法请求
AJAX_HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://" + config.BASE_URL.split("//")[-1].split("/")[0],
}

# 常见的 2FA / 验证相关提示，用于更友好地报错
TWO_FA_HINTS = ("2fa", "两步", "二步", "动态码", "google", "totp", "验证器")


def _clean(msg) -> str:
    """把接口返回的 msg 压成一行，去掉活动广告等噪音换行。"""
    if msg is None:
        return ""
    text = str(msg).strip()
    # 保留首段（真正的结果），丢弃后面追加的活动文案
    text = text.split("\n\n")[0].strip()
    return re.sub(r"\s+", " ", text)


def _looks_like_two_fa(msg: str) -> bool:
    low = msg.lower()
    return any(h in low for h in TWO_FA_HINTS)


def _parse_traffic(msg: str) -> str:
    """从签到成功文案里抠出流量数值，例如「您获得了 2.985GB 流量」。"""
    m = re.search(r"([\d.]+\s*(?:[KMGTP]?B|字节|流量))", msg, re.IGNORECASE)
    return m.group(1) if m else ""


def _parse_account(html: str) -> dict:
    """从用户中心 HTML 里提取账户概况（仅用于通知展示，失败不影响签到）。"""
    info = {}
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)

    patterns = {
        "level": r"(?:会员时长|等级)\s*(?:时长)?\s*[:：]?\s*([\u4e00-\u9fa5A-Za-z]{1,6}\s*Lv\s*\d+)",
        "expire": r"(\d{4}-\d{2}-\d{2})\s*(?:到期|过期)",
        "traffic_remain": r"([\d.]+\s*[GMK]B)\s*剩余流量",
        "traffic_used": r"已用流量[：:]\s*([\d.]+\s*[GMK]B)",
        "devices": r"(\d+)\s*/\s*\d+\s*在线设备",
    }
    for key, pat in patterns.items():
        m = re.search(pat, text)
        if m:
            info[key] = m.group(1).strip()

    # 等级单独兜底：面板文案形如「王者Lv7」
    if "level" not in info:
        m = re.search(r"([\u4e00-\u9fa5A-Za-z]{1,6}\s*Lv\s*\d+)", text)
        if m:
            info["level"] = m.group(1).strip()
    return info


def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": config.USER_AGENT})
    if not config.VERIFY_SSL:
        # 本机若走了代理导致证书主机名不匹配，可设 VERIFY_SSL=false 临时绕过
        s.verify = False
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    return s


def _request_with_retry(
    session: requests.Session,
    method: str,
    url: str,
    *,
    desc: str,
    **kwargs,
) -> requests.Response:
    """带指数退避的请求。5xx 和网络抖动才重试，4xx 直接抛。"""
    last_err = None
    for attempt in range(1, config.REQUEST_RETRY + 1):
        try:
            resp = session.request(method, url, timeout=config.REQUEST_TIMEOUT, **kwargs)
            if resp.status_code >= 500 and attempt < config.REQUEST_RETRY:
                wait = config.RETRY_BACKOFF * (2 ** (attempt - 1))
                logger.warning(
                    f"{desc} 返回 {resp.status_code}，{wait}s 后重试 ({attempt}/{config.REQUEST_RETRY})"
                )
                time.sleep(wait)
                continue
            return resp
        except requests.RequestException as e:
            last_err = e
            # 证书问题重试没有意义，重试只会浪费时间
            if _is_ssl_error(e):
                raise RuntimeError(_ssl_hint(e)) from e
            if attempt < config.REQUEST_RETRY:
                wait = config.RETRY_BACKOFF * (2 ** (attempt - 1))
                logger.warning(f"{desc} 失败: {e}，{wait}s 后重试 ({attempt}/{config.REQUEST_RETRY})")
                time.sleep(wait)
            else:
                break
    raise RuntimeError(f"{desc} 请求失败: {last_err}")


def _is_ssl_error(exc: Exception) -> bool:
    """判断是否为 TLS 证书类错误。"""
    text = str(exc).lower()
    return any(
        k in text
        for k in ("ssl", "certificate", "hostname mismatch", "certificate_verify_failed")
    )


def _ssl_hint(exc: Exception) -> str:
    """针对证书问题给出可照做的排查提示，而不是抛一堆原始堆栈。"""
    text = str(exc)
    lines = [
        "TLS 证书校验失败，已停止重试。",
        f"当前站点: {config.BASE_URL}",
        f"原因: {text[:220]}",
    ]
    if "hostname mismatch" in text.lower():
        lines += [
            "",
            "这是「域名与证书不匹配」：该域名的证书没有覆盖你正在访问的主机名。",
            "浏览器往往仍能打开（它对这类错误更宽容），但脚本会严格拒绝。",
            "解决办法：改用证书有效的域名。本项目默认域名见 config.py 的 BASE_URL 处注释。",
        ]
    else:
        lines += ["请检查域名是否正确、系统时间是否准确。"]
    lines += [
        "",
        "若确认要临时绕过（降低安全性，不推荐长期使用），可设环境变量 VERIFY_SSL=false。",
    ]
    return "\n".join(lines)


def _json_of(resp: requests.Response, desc: str) -> dict:
    """解析 JSON 响应，失败时抛出可读异常。"""
    try:
        return resp.json()
    except ValueError:
        snippet = resp.text[:200].replace("\n", " ")
        raise RuntimeError(f"{desc} 返回非 JSON (HTTP {resp.status_code}): {snippet}")


def login(session: requests.Session) -> dict:
    """登录并建立会话 Cookie。"""
    # 先 GET 一次登录页，让服务端种下会话/风控 cookie
    _request_with_retry(session, "GET", config.LOGIN_URL, desc="预热登录页")

    resp = _request_with_retry(
        session,
        "POST",
        config.LOGIN_URL,
        desc="登录",
        headers={**AJAX_HEADERS, "Referer": config.LOGIN_URL},
        data={"email": config.YUN_EMAIL, "passwd": config.YUN_PASSWORD, "remember": "1"},
        allow_redirects=False,
    )
    data = _json_of(resp, "登录")
    msg = _clean(data.get("msg", ""))

    if data.get("ret") == 1:
        # 会话 cookie 是签到凭证，确认一下真的种上了
        names = {c.name for c in session.cookies}
        logger.info(f"登录成功，会话 cookie: {sorted(names)}")
        return {"success": True, "message": msg}
    if _looks_like_two_fa(msg):
        return {
            "success": False,
            "message": "账号开启了两步验证，接口登录被拒。需在 YUN_2FA_CODE 配置当前动态码，"
            "或先关闭面板的 2FA 后重试",
        }
    return {"success": False, "message": msg or "登录失败"}


def do_checkin(session: requests.Session) -> dict:
    """调用签到接口。"""
    resp = _request_with_retry(
        session,
        "POST",
        config.CHECKIN_URL,
        desc="签到",
        headers={**AJAX_HEADERS, "Referer": config.USER_URL},
        data={},
        allow_redirects=False,
    )
    # 未登录时面板会 302 到登录页
    if resp.status_code in (301, 302, 303, 307, 308):
        return {"success": False, "status": "session_lost", "message": "会话已失效，请重试"}
    if resp.status_code == 401:
        return {"success": False, "status": "session_lost", "message": "未授权，会话已失效"}

    data = _json_of(resp, "签到")
    raw_msg = data.get("msg", "")
    msg = _clean(raw_msg)
    ret = data.get("ret")

    if ret == 1:
        logger.info(f"签到成功: {msg}")
        return {
            "success": True,
            "status": "success",
            "message": msg,
            "traffic": _parse_traffic(raw_msg),
        }
    if ret == 0:
        # 「您似乎已经签到过了」——今天已完成，视为正常
        logger.info(f"今日已签到: {msg}")
        return {"success": True, "status": "already", "message": msg or "今日已签到"}
    return {"success": False, "status": "failed", "message": msg or f"未知返回 ret={ret}"}


def fetch_account(session: requests.Session) -> dict:
    """读取账户概况，失败不影响主流程。"""
    try:
        resp = _request_with_retry(session, "GET", config.USER_URL, desc="账户信息")
        if resp.status_code != 200:
            return {}
        return _parse_account(resp.text)
    except Exception as e:
        logger.warning(f"读取账户信息失败（不影响签到）: {e}")
        return {}


def run_checkin() -> dict:
    """完整流程：登录 → 签到 → 读取账户。返回结果字典。"""
    result = {
        "success": False,
        "login_success": False,
        "checkin_status": "unknown",
        "message": "",
        "account": {},
    }

    logger.info("=" * 50)
    logger.info("69云签到开始（纯 HTTP 模式）")
    logger.info(f"站点: {config.BASE_URL}")
    logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("-" * 50)

    if not config.YUN_EMAIL or not config.YUN_PASSWORD:
        result["message"] = "缺少 YUN_EMAIL 或 YUN_PASSWORD，请检查 GitHub Secrets"
        logger.error(result["message"])
        return result

    session = _make_session()

    # 1) 登录
    try:
        login_res = login(session)
    except Exception as e:
        result["message"] = f"登录异常: {e}"
        logger.error(result["message"])
        return result

    result["login_success"] = login_res["success"]
    if not login_res["success"]:
        result["message"] = f"登录失败: {login_res['message']}"
        logger.error(result["message"])
        return result

    # 2) 签到
    try:
        checkin_res = do_checkin(session)
    except Exception as e:
        result["message"] = f"签到异常: {e}"
        logger.error(result["message"])
        return result

    result["checkin_status"] = checkin_res["status"]
    result["success"] = checkin_res["success"]
    result["message"] = checkin_res["message"]
    if checkin_res.get("traffic"):
        result["traffic"] = checkin_res["traffic"]
        logger.info(f"本次获得流量: {checkin_res['traffic']}")

    # 会话失效时重登一次再试（应对 token 过期）
    if checkin_res["status"] == "session_lost":
        logger.info("会话失效，重新登录后再试一次")
        try:
            if login(session)["success"]:
                retry = do_checkin(session)
                result["checkin_status"] = retry["status"]
                result["success"] = retry["success"]
                result["message"] = retry["message"]
                if retry.get("traffic"):
                    result["traffic"] = retry["traffic"]
            else:
                result["message"] = "重新登录失败，会话已失效"
        except Exception as e:
            logger.error(f"重试失败: {e}")
            result["message"] = f"重试失败: {e}"

    # 3) 账户概况
    result["account"] = fetch_account(session)
    if result["account"]:
        logger.info(f"账户信息: {result['account']}")

    logger.info("=" * 50)
    return result


if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    print(json.dumps(run_checkin(), ensure_ascii=False, indent=2))
