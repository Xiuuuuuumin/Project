import os
import copy
import logging.config
from uvicorn.config import LOGGING_CONFIG as UVICORN_LOGGING_CONFIG

#file i/o initialization
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "app.log")

#logging config initialization
LOGGING_CONFIG = copy.deepcopy(UVICORN_LOGGING_CONFIG)


# 純文字 formatter for file
LOGGING_CONFIG["formatters"]["file_plain"] = {
    "format": "[%(asctime)s] [PID:%(process)d] [%(levelname)s] [%(name)s]: %(message)s",
    "datefmt": "%Y-%m-%d %H:%M:%S",
}

# file handler
LOGGING_CONFIG["handlers"]["file"] = {
    "class": "logging.FileHandler",
    "formatter": "file_plain",
    "filename": LOG_FILE,
    "encoding": "utf-8",
}

# add file handler to uvicorn logger
for name in ["uvicorn"]: #, "uvicorn.error", "uvicorn.access"
    if "handlers" not in LOGGING_CONFIG["loggers"][name]:
        LOGGING_CONFIG["loggers"][name]["handlers"] = []
    if "file" not in LOGGING_CONFIG["loggers"][name]["handlers"]:
        LOGGING_CONFIG["loggers"][name]["handlers"].append("file")
    # **保留 propagate=True**，讓 uvicorn terminal log 照常顯示

# app logger
LOGGING_CONFIG["loggers"]["app"] = {
    "handlers": ["file"],
    "level": "INFO",
    "propagate": True,  # 可選 True，方便錯誤 propagate 到 uvicorn
}

def setup_logging():
    logging.config.dictConfig(LOGGING_CONFIG)
