# 从.env文件中读取配置
import os
from dotenv import load_dotenv

load_dotenv()

# 从环境变量中读取配置
LOGIN_URL = os.environ.get("LOGIN_URL", "")
YUN_EMAIL = os.environ.get("YUN_EMAIL", "")
YUN_PASSWORD = os.environ.get("YUN_PASSWORD", "")

# 飞书Webhook 地址
FEISHU_WEBHOOK_URL = os.environ.get("FEISHU_WEBHOOK_URL", "")
