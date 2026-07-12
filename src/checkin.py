import os
import sys
import json
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from playwright.sync_api import sync_playwright, Request, Response

import config

# -------------------- 配置 --------------------
LOGIN_URL = config.LOGIN_URL or "https://china_69yun.337979.xyz/uuid/auth/login"
EMAIL = config.YUN_EMAIL
PASSWORD = config.YUN_PASSWORD
HEADLESS = os.environ.get("HEADLESS", "false").lower() in ("1", "true", "yes")
CHROME_PATH = os.environ.get("CHROME_PATH", r"C:\Program Files\Google\Chrome\Application\chrome.exe")

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
SCREENSHOT_DIR = os.path.join(PROJECT_ROOT, "screenshots")
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
NETWORK_LOG = os.path.join(LOG_DIR, f"network_{RUN_ID}.log")
RUN_LOG = os.path.join(LOG_DIR, f"run_{RUN_ID}.log")

# 模块日志：只添加文件处理器，控制台输出交给 root logger（main.py 配置）
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

file_handler = logging.FileHandler(RUN_LOG, encoding="utf-8")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


def _safe_url(url: str) -> str:
    """去除 URL 中的查询参数，避免日志泄露 token 等敏感信息。"""
    try:
        from urllib.parse import urlsplit, urlunsplit
        parts = urlsplit(url)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    except Exception:
        return url


def log_network(req: Request, res: Response = None, tag: str = ""):
    """将请求/响应关键信息写入网络日志。"""
    data = {
        "time": datetime.now().isoformat(),
        "tag": tag,
        "url": _safe_url(req.url),
        "method": req.method,
        "resource_type": req.resource_type,
    }
    if res:
        data["status"] = res.status
        data["status_text"] = res.status_text
        try:
            data["content_type"] = res.headers.get("content-type", "")
        except Exception:
            pass

    with open(NETWORK_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")


def flush_logs():
    """强制刷新日志处理器到磁盘，避免异常退出时丢失日志。"""
    for handler in logger.handlers:
        handler.flush()
        if hasattr(handler, "stream") and hasattr(handler.stream, "fileno"):
            try:
                os.fsync(handler.stream.fileno())
            except Exception:
                pass


def run_checkin():
    """执行签到流程，返回结果字典供 main.py 使用。"""
    result = {
        "success": False,
        "login_success": False,
        "checkin_status": "unknown",
        "message": "",
        "current_url": "",
        "screenshots": [],
        "network_log": NETWORK_LOG,
        "run_log": RUN_LOG,
    }

    logger.info("=" * 50)
    logger.info("开始 69 云签到流程")
    logger.info(f"登录地址: {LOGIN_URL}")
    logger.info(f"有头模式: {not HEADLESS}")
    logger.info(f"网络日志: {NETWORK_LOG}")
    flush_logs()

    if not EMAIL or not PASSWORD:
        result["message"] = "缺少邮箱或密码，请检查 .env 或环境变量"
        logger.error(result["message"])
        return result

    with sync_playwright() as p:
        browser_kwargs = {
            "headless": HEADLESS,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        }

        # CI 环境（如 GitHub Actions）或无显式配置时，直接用 Playwright Chromium
        in_ci = os.environ.get("CI", "").lower() in ("1", "true", "yes")
        if CHROME_PATH and os.path.exists(CHROME_PATH) and not in_ci:
            logger.info(f"使用本机 Chrome: {CHROME_PATH}")
            browser = p.chromium.launch(executable_path=CHROME_PATH, **browser_kwargs)
        else:
            if in_ci:
                logger.info("CI 环境，使用 Playwright 自带 Chromium")
            else:
                logger.info("使用 Playwright 自带 Chromium")
            browser = p.chromium.launch(**browser_kwargs)

        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
        )

        page = context.new_page()

        def on_request(req: Request):
            log_network(req, tag="request")

        def on_response(res: Response):
            log_network(res.request, res=res, tag="response")
            if "/auth/login" in res.url and res.request.method == "POST":
                try:
                    body = res.body()
                    text = body.decode("utf-8", errors="ignore")[:2000]
                    logger.info(f"登录接口响应 [{res.status}] URL={_safe_url(res.url)}: {text}")
                    flush_logs()
                except Exception as e:
                    logger.warning(f"读取登录响应失败: {e}")
            if "/user/authcode" in res.url and res.request.method == "POST":
                try:
                    body = res.body()
                    text = body.decode("utf-8", errors="ignore")[:2000]
                    logger.info(f"authcode 接口响应 [{res.status}] URL={_safe_url(res.url)}: {text}")
                    flush_logs()
                except Exception as e:
                    logger.warning(f"读取 authcode 响应失败: {e}")

        page.on("request", on_request)
        page.on("response", on_response)

        try:
            # 1. 访问登录页
            logger.info("正在打开登录页面...")
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_selector('input[name="email"], input[type="email"], #email', timeout=15000)
            page.wait_for_timeout(1500)
            shot1 = os.path.join(SCREENSHOT_DIR, f"01_login_{RUN_ID}.png")
            page.screenshot(path=shot1)
            result["screenshots"].append(shot1)
            logger.info("登录页面已加载")
            flush_logs()

            # 2. 填充表单
            logger.info("填充用户名/密码...")
            page.locator('input[name="email"], input[type="email"], #email').first.fill(EMAIL)
            page.locator('input[name="passwd"], input[type="password"], #passwd, #password').first.fill(PASSWORD)

            try:
                remember = page.locator('input[name="remember_me"], input[name="remember"]').first
                if remember.count() > 0:
                    remember.check(timeout=3000)
                    logger.info("已勾选 remember_me")
            except Exception as e:
                logger.info(f"remember_me 不存在或无需勾选: {e}")

            shot2 = os.path.join(SCREENSHOT_DIR, f"02_filled_{RUN_ID}.png")
            page.screenshot(path=shot2)
            result["screenshots"].append(shot2)
            flush_logs()

            # 3. 点击登录
            logger.info("点击登录按钮...")
            login_btn = page.locator(
                'button[type="submit"], button:has-text("登录"), button:has-text("Login"), '
                'a:has-text("登录"), input[type="submit"]'
            ).first
            login_btn.click(timeout=10000)

            # 4. 等待跳转/页面稳定
            logger.info("等待登录后页面稳定...")
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                logger.info("networkidle 未在 5s 内触发，继续执行（可能是第三方 widget 长连接）")
            page.wait_for_timeout(2500)
            result["current_url"] = page.url
            logger.info(f"当前页面 URL: {result['current_url']}")
            shot3 = os.path.join(SCREENSHOT_DIR, f"03_after_login_{RUN_ID}.png")
            page.screenshot(path=shot3)
            result["screenshots"].append(shot3)
            flush_logs()

            # 5. 判断登录是否成功
            if "/user" in result["current_url"] or "/auth/login" not in result["current_url"]:
                result["login_success"] = True
                flush_logs()
            else:
                result["message"] = "登录后未跳转到用户页，可能登录失败"
                logger.warning(result["message"])
                flush_logs()
                return result

            # 6. 查找签到按钮
            checkin_selectors = [
                'button:has-text("签到")',
                'a:has-text("签到")',
                'button:has-text("每日签到")',
                'a:has-text("每日签到")',
                'button:has-text("Checkin")',
                'a:has-text("Checkin")',
                'button:has-text("Check In")',
                '[id*="checkin" i]',
                '[class*="checkin" i]',
                '[data-action="checkin"]',
            ]

            checkin_btn = None
            for selector in checkin_selectors:
                loc = page.locator(selector).first
                try:
                    if loc.count() > 0 and loc.is_visible(timeout=2000):
                        checkin_btn = loc
                        logger.info(f"找到签到按钮: {selector}")
                        break
                except Exception:
                    # 当前选择器不可见或已 detached，继续尝试下一个
                    continue

            if checkin_btn:
                btn_text = checkin_btn.inner_text(timeout=3000).strip()
                logger.info(f"按钮文案: {btn_text}")
                if "已签到" in btn_text:
                    result["checkin_status"] = "already"
                    result["message"] = "今日已签到，无需重复点击"
                    logger.info(result["message"])
                else:
                    checkin_btn.click(timeout=10000)
                    result["checkin_status"] = "clicked"
                    result["message"] = "已点击签到按钮"
                    logger.info(result["message"])
                    page.wait_for_timeout(2000)
                shot4 = os.path.join(SCREENSHOT_DIR, f"04_checkin_done_{RUN_ID}.png")
                page.screenshot(path=shot4)
                result["screenshots"].append(shot4)
            else:
                result["checkin_status"] = "not_found"
                result["message"] = "未找到签到按钮"
                logger.warning(result["message"])

            result["success"] = True

            # 7. 保存最终页面信息
            final_info = {
                "url": page.url,
                "title": page.title(),
                "run_id": RUN_ID,
                "result": result,
            }
            info_path = os.path.join(LOG_DIR, f"final_{RUN_ID}.json")
            with open(info_path, "w", encoding="utf-8") as f:
                json.dump(final_info, f, ensure_ascii=False, indent=2)
            logger.info(f"最终页面信息已保存: {info_path}")
            flush_logs()

        except Exception as e:
            logger.exception("运行过程出现错误")
            result["message"] = f"异常: {str(e)}"
            try:
                error_shot = os.path.join(SCREENSHOT_DIR, f"error_{RUN_ID}.png")
                page.screenshot(path=error_shot)
                result["screenshots"].append(error_shot)
            except Exception:
                pass
        finally:
            context.close()
            browser.close()

    logger.info("流程结束")
    return result


if __name__ == "__main__":
    r = run_checkin()
    print(json.dumps(r, ensure_ascii=False, indent=2))
