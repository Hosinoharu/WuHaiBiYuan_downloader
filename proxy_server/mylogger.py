"""
封装一个简单的日志输出，并没有使用标准库、第三方库。
可自行修改下面的方法，只要不改动接口就行。
"""

from pathlib import Path
from datetime import datetime


from settings import settings

__all__ = ["logger"]


import logging


class MyLogger:

    def __init__(self, level: str, log_file: Path | None):
        """记录日志，默认输出到控制台，可以指定文件名称输出到文件（此时就不会再输出到控制台中）"""
        self.log_file = log_file

        # 创建名为 default 的记录器
        self.logger = logging.getLogger("default")
        self.logger.setLevel(level)

        self.level = self.logger.getEffectiveLevel()
        self.default_handler = None
        self.default_formatter = None

        self._add_default_things()

        pass

    def _add_default_things(self):
        """添加默认的处理器、格式器。过滤器倒是不用了"""
        if self.default_handler and self.default_handler:  # 已经设置过了
            return

        # 记录日志默认的处理器（输出到文件），默认打开模式是 a，encoding 指定为 utf-8
        if self.log_file:
            self.default_handler = logging.FileHandler(self.log_file, encoding="utf-8")
        else:
            self.default_handler = logging.StreamHandler()

        self.default_handler.setLevel(self.level)
        # 给记录器添加处理器
        self.logger.addHandler(self.default_handler)

        # 默认的格式器
        self.default_formatter = logging.Formatter(
            "[%(asctime)s] - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        # 给处理器添加格式器
        self.default_handler.setFormatter(self.default_formatter)

    def info(self, *args, **kwargs):
        self.logger.info(*args, **kwargs)

    def error(self, *args, **kwargs):
        self.logger.error(*args, **kwargs)

    def debug(self, *args, **kwargs):
        self.logger.debug(*args, **kwargs)

    pass


logger = MyLogger(settings["logger_level"], settings["log_file"])
