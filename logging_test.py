from config.logging_config import logger

logger.debug("這是 debug 訊息")
logger.info("伺服器啟動中")
logger.warning("警告訊息")
logger.error("錯誤訊息")
logger.critical("嚴重錯誤")

# config/logging_config.py
import logging
import colorlog
import os

# -----------------------------
# 1️⃣ 建立 logger
# -----------------------------
logger = logging.getLogger("app")
logger.setLevel(logging.DEBUG)  # 接收 DEBUG 以上訊息

# -----------------------------
# 2️⃣ 建立 console handler（彩色輸出）
# -----------------------------
handler = colorlog.StreamHandler()
formatter = colorlog.ColoredFormatter(
    "%(log_color)s%(asctime)s [%(levelname)s]%(reset)s %(message)s",
    datefmt="%H:%M:%S",
    log_colors={
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold_red",
    },
)
handler.setFormatter(formatter)
handler.setLevel(logging.DEBUG)
logger.addHandler(handler)

# -----------------------------
# 3️⃣ 建立檔案 handler（純文字存檔）
# -----------------------------
# 確保 log 資料夾存在
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

file_handler = logging.FileHandler(os.path.join(log_dir, "app.log"), encoding="utf-8")
file_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(file_formatter)
file_handler.setLevel(logging.INFO)  # 檔案只記錄 INFO 以上
logger.addHandler(file_handler)

# -----------------------------
# 4️⃣ 防止重複加 handler
# -----------------------------
if logger.hasHandlers():
    # 防止被多次 import 重複輸出
    logger.propagate = False





# logger.py
import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# 通用 Formatter
formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    "%Y-%m-%d %H:%M:%S",
)

#region
# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.INFO)

# File handler (rotate every 5 MB)
file_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, "app.log"), maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
)
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.DEBUG)

# 根 logger（所有模組繼承）
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)

#endregion

# 各模組 logger
logger_api = logging.getLogger("api")
logger_db = logging.getLogger("db")
logger_ws = logging.getLogger("ws")
logger_ros = logging.getLogger("ros")
