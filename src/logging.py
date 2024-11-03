import os
import logging
import tkinter as tk
from datetime import datetime


class Logger:

    def __init__(self, name="TwitchRecorderLogger", log_dir="logs"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        self.log_file_name = datetime.now().strftime("%Y-%m-%d %H_%M_%S") + ".log"
        self.log_file_path = os.path.join(log_dir, self.log_file_name)

        self.formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

        # 建立檔案處理器並設定格式
        self.fh = logging.FileHandler(self.log_file_path)
        self.fh.setLevel(logging.DEBUG)
        self.fh.setFormatter(self.formatter)

        # 建立控制台處理器並設定格式
        self.ch = logging.StreamHandler()
        self.ch.setLevel(logging.DEBUG)
        self.ch.setFormatter(self.formatter)

        # 新增處理器到記錄器
        self.logger.addHandler(self.fh)
        self.logger.addHandler(self.ch)

    def add_textbox_handler(self, text_widget, restore_window):
        """新增文字方塊處理器以將日誌訊息傳送至Tkinter文字方塊"""
        textbox_handler = TextBoxLogger(text_widget, restore_window)
        textbox_handler.setLevel(logging.DEBUG)  # 設定日誌等級
        textbox_handler.setFormatter(self.formatter)
        self.logger.addHandler(textbox_handler)

    def debug(self, message):
        self.logger.debug(message)

    def info(self, message):
        self.logger.info(message)

    def warning(self, message):
        self.logger.warning(message)

    def error(self, message):
        self.logger.error(message)

    def critical(self, message):
        self.logger.critical(message)

    def exception(self, message):
        self.logger.exception(message)


class TextBoxLogger(logging.Handler):
    """寫入文本框"""

    def __init__(self, text_widget, restore_window):
        super().__init__()
        self.text_widget = text_widget
        self.restore_window = restore_window
        # 設置標記顏色
        self.text_widget.tag_configure("DEBUG", foreground="blue")
        self.text_widget.tag_configure("INFO", foreground="#e6e6e6")
        self.text_widget.tag_configure("WARNING", foreground="orange")
        self.text_widget.tag_configure("ERROR", foreground="red")
        self.text_widget.tag_configure("CRITICAL", foreground="#e2df00")
        self.text_widget.tag_configure("EXCPTION", foreground="#ff2ac3")

    def emit(self, log):
        msg = self.format(log)
        level_name = log.levelname  # 獲取日誌級別

        if level_name in ["WARNING", "ERROR", "CRITICAL", "EXCPTION"]:
            self.restore_window()
        # 根據日誌級別選擇顏色
        if level_name in self.text_widget.tag_names():
            tag = level_name
        else:
            tag = "INFO"

        self.text_widget["state"] = tk.NORMAL  # 允許編輯
        self.text_widget.insert(tk.END, msg + "\n", tag)  # 插入日誌消息
        self.text_widget["state"] = tk.DISABLED  # 禁止編輯
        self.text_widget.yview(tk.END)  # 滾動到底部
