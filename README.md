# 69yun-checkin

69云（Metron / V2Board 面板）每日自动签到，通过 GitHub Actions 定时执行。

## 特点

- **纯 HTTP 实现**，不依赖 Playwright / Chromium。原版用无头浏览器模拟点击，页面一改版选择器就失效；实测该面板的签到就是两个 XHR，直接打接口更快更稳，单次运行约 3 秒。
- 依赖极少，只有 `requests` 和 `python-dotenv`。
- 失败会发飞书通知，并附账户概况（剩余流量、到期日、等级）。

## 面板接口

| 用途 | 方法 | 路径 | 说明 |
|---|---|---|---|
| 登录 | POST | `/uuid/auth/login` | 表单参数 `email`、`passwd`、`remember` |
| 签到 | POST | `/uuid/user/checkin` | 无参数，依赖会话 Cookie |
| 账户信息 | GET | `/uuid/user` | 解析 HTML 取流量/到期等 |

返回码语义（实测）：

- `{"ret":1,...}` 签到成功，`msg` 内含本次获得的流量
- `{"ret":0,...}` 今日已签到过，**不算失败**
- 其他 为异常，`msg` 说明原因

## 配置

在仓库 **Settings → Secrets and variables → Actions** 中配置：

### Secrets（必填）

| 名称 | 说明 |
|---|---|
| `YUN_EMAIL` | 登录邮箱 |
| `YUN_PASSWORD` | 登录密码 |
| `FEISHU_WEBHOOK_URL` | 飞书群机器人 webhook，可选，不配则跳过通知 |

### Variables（可选）

| 名称 | 默认值 | 说明 |
|---|---|---|
| `BASE_URL` | `https://ui567u.337979.xyz/uuid` | 面板根地址，换机场时改这里 |

> **注意**：这个默认值请不要改成 `https://china_69yun.337979.xyz/uuid`。
> 该域名虽然也是面板入口，但其证书只签发了 `*.69yun69.com`，
> 主机名不匹配会让脚本抛 `SSLError`——浏览器能打开只是因为它对这类错误更宽容。
>
> 换域名时可先验证证书是否覆盖该主机名：
> ```bash
> echo | openssl s_client -connect 你的域名:443 2>/dev/null \
>   | openssl x509 -noout -ext subjectAltName
> ```
> 输出里的 DNS 列表必须包含你要用的域名。

> 密码只存在 GitHub Secrets 里，不进代码库。

## 运行

定时任务：每天北京时间 **09:00**（UTC 01:00）自动执行。

手动触发：Actions 页点 **Run workflow**。

本地运行：

```bash
pip install -r requirements.txt
export YUN_EMAIL="you@example.com"
export YUN_PASSWORD="your-password"
python main.py
```

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `REQUEST_TIMEOUT` | `30` | 单次请求超时（秒） |
| `REQUEST_RETRY` | `3` | 最大尝试次数 |
| `RETRY_BACKOFF` | `5` | 重试退避基数（秒），指数增长 |
| `TZ_OFFSET_HOURS` | `8` | 日志/通知的时区偏移，默认北京时间 |
| `USER_AGENT` | Chrome UA | 请求使用的 UA |
| `VERIFY_SSL` | `true` | 是否校验 TLS 证书，**不建议关** |
| `ALLOW_INSECURE_SSL` | 未设置 | 设为 `1` 时不再提示「已关闭证书校验」 |

## 常见问题

**收到「已签到」但其实没签到成功？**

不会。`ret=0` 是面板的通用失败码，「今日已签到」只是其中一种。
脚本会检查提示文案，只有明确包含「已签到/签到过」才判定为成功；
套餐过期、账号被封、流量用完等一律按失败处理并返回非零退出码。

**提示「账号开启了两步验证」**
面板给账号开了 2FA，接口登录会被拒。需先在面板关闭 2FA；这类场景确实无法用无状态接口自动完成。

**CI 报 `Hostname mismatch` / `certificate verify failed`**

域名和证书不匹配。这不是网络故障，重试也没用。根治办法是**换用证书覆盖该主机的域名**，
用上面 `openssl s_client` 的方法先验一下。

把 `VERIFY_SSL=false` 当临时手段可以跑通，但会关闭证书校验、降低传输安全性，
且面板每次换证书都会再坏一次——不建议长期用。

**本地能跑但 CI 失败**

最常见原因就是本地开了 `VERIFY_SSL=false` 而 CI 没开。
建议本地也保持证书校验开启，用 `openssl s_client` 先确认域名没问题再跑。

**运行时间**
纯 HTTP 无需下载浏览器，通常 3～5 秒完成。
