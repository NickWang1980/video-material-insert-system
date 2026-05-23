# uncompyle6 version 3.9.2
# Python bytecode version base 3.8.0 (3413)
# Decompiled from: Python 3.6.5 (v3.6.5:f59c0932b4, Mar 28 2018, 17:00:18) [MSC v.1900 64 bit (AMD64)]
# Embedded file name: /code/y_utils/logger.py
# Compiled at: 2024-03-27 17:15:16
# Size of source mod 2**32: 1006 bytes
"""
File: logger.py
Author: YuFangHui
Date: 2019/11/19
Description:
"""
import logging.handlers, os
from y_utils import config

def create_logger(log_path="/home/y_demo/log/", log_name="y_demo.log", level=logging.INFO):
    logging_msg_format = "[%(asctime)s] [%(filename)s[line:%(lineno)d]] [%(levelname)s] [%(message)s]"
    logging_date_format = "%Y-%m-%d %H:%M:%S"
    logging.basicConfig(level=level,
      format=logging_msg_format,
      datefmt=logging_date_format)
    if not os.path.exists(log_path):
        os.makedirs(log_path)
    log_path = os.path.join(log_path, log_name)
    file_handler = logging.handlers.WatchedFileHandler(log_path)
    file_handler.setFormatter(logging.Formatter(logging_msg_format))
    logger_h = logging.getLogger()
    logger_h.addHandler(file_handler)
    return logger_h


config = config.get_config()
logger = create_logger(config.get("log", "log_dir"), config.get("log", "log_file"), logging.WARNING)
