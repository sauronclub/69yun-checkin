# 69云签到

基于 Playwright 的 69 云机场每日自动签到脚本，支持 GitHub Actions 定时执行，并可通过飞书群机器人推送签到结果。

## 解决什么问题

- **忘记签到**：69 云机场通常有每日签到奖励，手动签到容易忘记。
- **自动化运维**：部署到 GitHub Actions 后每天自动运行一次，无需人工干预。
- **结果可感知**：签到成功/失败/已签到都会通过飞书消息通知，方便掌握状态。
- **失败可排查**：自动保存运行日志和页面截图，方便定位问题。

## 功能特性

- 使用 Playwright 模拟真实浏览器登录
- 自动检测并点击签到按钮
- 若当日已签到，会识别为“已签到”并跳过点击
- 支持飞书群机器人消息推送
- 失败时自动附带最近日志片段，便于排查
- 网络日志自动脱敏（去除 URL 查询参数）
- GitHub Actions 每日定时运行（北京时间 09:00）

## 项目结构

```
.
├── .github/workflows/checkin.yml   # GitHub Actions 工作流
├── main.py                          # 入口文件
├── config.py                        # 读取环境变量 / .env
├── requirements.txt                 # Python 依赖
├── src/
│   ├── checkin.py                   # 登录 + 签到核心逻辑
│   └── feishu.py                    # 飞书通知
├── logs/                            # 运行日志（不提交到仓库）
└── screenshots/                     # 页面截图（不提交到仓库）
```

## 本地使用

### 1. 克隆仓库

```bash
git clone https://github.com/sauronclub/69yun-checkin.git
cd 69yun-checkin
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. 配置环境变量

复制 `.env.example` 为 `.env`（或直接在 shell 中设置环境变量）：

```bash
# Linux / macOS
export LOGIN_URL="https://china_69yun.337979.xyz/uuid/auth/login"
export YUN_EMAIL="your_email@example.com"
export YUN_PASSWORD="your_password"
export FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/xxxx"

# Windows PowerShell
$env:LOGIN_URL="https://china_69yun.337979.xyz/uuid/auth/login"
$env:YUN_EMAIL="your_email@example.com"
$env:YUN_PASSWORD="your_password"
$env:FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/xxxx"
```

> `.env` 文件已通过 `.gitignore` 排除，不会上传到 GitHub。

### 4. 运行

```bash
# 有头模式（本地调试用，可看到浏览器窗口）
python main.py

# 无头模式
$env:HEADLESS="true"  # Windows
# 或
export HEADLESS=true  # Linux / macOS
python main.py
```

运行后会在 `logs/` 和 `screenshots/` 目录生成日志与截图。

## 部署到 GitHub Actions

### 1. Fork 或创建仓库

将本项目代码推送到你的 GitHub 仓库。

### 2. 配置 Secrets

进入仓库 **Settings → Secrets and variables → Actions → New repository secret**，添加以下 Secrets：

| Secret 名称 | 说明 | 是否必填 |
|------------|------|---------|
| `YUN_EMAIL` | 69 云账号邮箱 | 是 |
| `YUN_PASSWORD` | 69 云账号密码 | 是 |
| `FEISHU_WEBHOOK_URL` | 飞书群机器人 Webhook 地址 | 否 |

### 3. 飞书机器人配置（可选）

1. 在飞书群聊中添加自定义机器人
2. 复制 Webhook 地址
3. 将地址填入 `FEISHU_WEBHOOK_URL`

### 4. 触发运行

工作流默认每天北京时间 09:00 自动运行。你也可以在 Actions 页面手动点击 **Run workflow** 触发。

## 通知示例

### 签到成功

```
✅ 69云签到 - 签到成功

时间：2026-07-12 09:00:00
登录：成功
签到：签到成功
消息：已点击签到按钮
```

### 今日已签到

```
✅ 69云签到 - 今日已签到

时间：2026-07-12 09:00:00
登录：成功
签到：今日已签到
消息：今日已签到，无需重复点击
```

### 执行失败

```
❌ 69云签到 - 执行失败

时间：2026-07-12 09:00:00
登录：失败
签到：未知
消息：登录超时

----- 最近日志 -----
[最近 30 行运行日志]
```

## 安全说明

- 账号密码通过 GitHub Secrets 注入，不会出现在代码或日志中
- `.env`、日志、截图已加入 `.gitignore`，避免误提交
- 网络日志会去除 URL 查询参数，降低 token 泄露风险
- 截图仅作为 GitHub Actions artifact 保留，不会发送到飞书

## 常见问题

### Q: GitHub Actions 提示找不到 `requirements.txt`？

A: 确保 `requirements.txt` 位于仓库根目录，而不是某个子文件夹中。

### Q: 飞书没有收到通知？

A: 检查 `FEISHU_WEBHOOK_URL` 是否正确配置。未配置时脚本会跳过通知，不会报错。

### Q: 签到按钮找不到？

A: 网站页面结构可能发生变化。可以下载 artifact 中的截图，查看当前页面状态，并调整 `src/checkin.py` 中的选择器。

### Q: 每天运行时间不准？

A: GitHub Actions 的 `schedule` 事件可能会有几分钟到十几分钟的延迟，属于正常现象。

## 免责声明

本项目仅供学习和技术交流使用。请遵守相关网站的服务条款，合理使用自动化工具。
