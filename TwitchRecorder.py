import os
import json
import tkinter as tk
from tkinter import ttk, messagebox
import threading

import asyncio
import pystray
from PIL import Image

from src.recorder import TwitchRecord
from src.logging import Logger


class TwitchRecorderApp:
    CONFIG_FILE = "config.json"
    ICON_PATH = os.path.join(os.path.dirname(__file__), "dep", "icon.png")

    def __init__(self, root):
        self.root = root
        self.root.title("Twitch Recorder")
        self.root.geometry("420x750")
        self.root.configure(bg="#1f1f1f")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.iconphoto(True, tk.PhotoImage(file=self.ICON_PATH))
        self.root.bind("<Unmap>", lambda event: self.minimize_to_tray())

        self.messagebox = messagebox
        self.logger = Logger()
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.run_loop)
        self.thread.start()

        self.strayicon = None
        self.recorder = None
        self.token = None
        self.record_task = None
        self.create_window()
        self.load_config()

    def run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def close(self):
        """關閉視窗"""
        if self.record_task is not None and not self.recorder._done:
            self.messagebox.showerror("ERROR", "Please wait for the running to stop")
            return
        elif self.record_task is None:
            self.close_loop_thread()
            self.save_config()
            self.root.destroy()
        else:
            self.stop_Record()
            self.close_loop_thread()
            self.save_config()
            self.root.destroy()

    def close_loop_thread(self):
        """終止異步循環和線程"""
        if self.loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self.shutdown_asyncgens(), self.loop)
            try:
                future.result()
            except Exception as e:
                self.logger.error(f"Error in shutdown_asyncgens: {e}")

            self.loop.call_soon_threadsafe(self.loop.stop)

        if self.thread.is_alive():
            self.thread.join()

    async def shutdown_asyncgens(self):
        """關閉異步生成器"""
        await self.loop.shutdown_asyncgens()

    def minimize_to_tray(self):
        """建立托盤圖標"""
        try:
            if self.root.state() == "iconic":
                image = Image.open(self.ICON_PATH)
                self.root.withdraw()  # 隱藏窗口
                self.strayicon = pystray.Icon(
                    "icon",
                    image,
                    menu=pystray.Menu(
                        pystray.MenuItem(text="Show App", action=self.restore_window, default=True)
                    )
                )
                self.strayicon.run_detached()
        except Exception as e:
            self.logger.error(f"Stray Error: {e}")

    def restore_window(self):
        """復原窗口"""
        if self.strayicon is not None:
            self.strayicon.visible = True  # 隱藏托盤圖標
            self.strayicon.stop()
            self.strayicon = None
            self.root.deiconify()  # 顯示窗口

    def create_window(self):
        """建立介面"""
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("T.TFrame", background="#1f1f1f")
        self.style.configure(
            "T.TLabel",
            font=("Comic Sans MS", 20, "bold"),
            background="#1f1f1f",
            foreground="#c753e8"
        )
        self.style.configure("T.TEntry", foreground="#e6e6e6", fieldbackground="#49444a")
        self.style.map(
            "C.TButton",
            relief=[("active", "RAISED"), ("!active", "RAISED")],
            font=[("active", ("Comic Sans MS", 16, "bold")),
                  ("!active", ("Comic Sans MS", 12, "bold"))],
            background=[("disabled", "#1f1f1f"), ("active", "#2f2f2f"), ("!active", "#1f1f1f")],
            foreground=[("disabled", "gray"), ("pressed", "gray"), ("active", "#c753e8"),
                        ("!active", "#e6e6e6")],
            width=[("active", 18), ("!active", 18)]
        )
        self.style.map(
            "R.TButton",
            font=[("active", ("Comic Sans MS", 15, "bold")),
                  ("!active", ("Comic Sans MS", 14, "bold"))],
            background=[("disabled", "#1f1f1f"), ("active", "#2f2f2f"), ("!active", "#2f2f2f")],
            foreground=[("disabled", "gray"), ("pressed", "gray"), ("active", "#c753e8"),
                        ("!active", "#c753e8")],
            width=[("active", 11), ("!active", 11)]
        )
        self.style.map(
            "R1.TButton",
            font=[("active", ("Comic Sans MS", 15, "bold")),
                  ("!active", ("Comic Sans MS", 14, "bold"))],
            background=[("active", "#2f2f2f"), ("!active", "#2f2f2f")],
            foreground=[("pressed", "gray"), ("active", "#ff0000"), ("!active", "#ff0000")],
            width=[("active", 11), ("!active", 11)]
        )

        self.style.map(
            "Vertical.TScrollbar",
            background=[("disabled", "#1f1f1f"), ("pressed", "#2f2f2f"), ("active", "#1f1f1f"),
                        ("!active", "#1f1f1f")],
            troughcolor=[("pressed", "#2f2f2f"), ("active", "#1f1f1f"), ("!active", "#1f1f1f")],
            arrowcolor=[("disabled", "#1f1f1f"), ("active", "#1f1f1f"), ("!active", "#1f1f1f")],
            # gripcolor=[("active", "#1f1f1f"), ("!active", "#1f1f1f")],
            # borderwidth=[("active", 0), ("!active", 0)],
            # bordercolor=[("active", "#1f1f1f"), ("!active", "#1f1f1f")],
            # highlightthickness=[("active", 0), ("!active", 0)],
            # highlightcolor=[("active", "#1f1f1f"), ("!active", "#1f1f1f")],
            # highlightbackground=[("active", "#1f1f1f"), ("!active", "#1f1f1f")],
            # relief=[("active", "RAISED"), ("!active", "RAISED")],
        )
        # Client frame
        self.client_frame = ttk.Frame(self.root, style="T.TFrame")
        self.client_frame.grid(row=0, column=1, padx=10, columnspan=2)
        # Client label
        self.client_label = ttk.Label(
            self.client_frame, style="T.TLabel", text="Enter Client ID & SECRET:"
        )
        self.client_label.grid(row=0, column=1, columnspan=2)
        # Client entry
        self.client_id = ttk.Entry(
            self.client_frame, font=("Comic Sans MS", 12, "bold"), style="T.TEntry"
        )
        self.client_id.grid(row=1, column=1, pady=5, padx=5, columnspan=2)
        self.client_id.insert(0, "Client ID")  # Prompt text

        self.client_secret = ttk.Entry(
            self.client_frame, font=("Comic Sans MS", 12, "bold"), style="T.TEntry"
        )
        self.client_secret.grid(row=2, column=1, pady=5, padx=5, columnspan=2)
        self.client_secret.insert(0, "Client Secret")
        # clear prompt text
        self.client_id.bind(
            "<FocusIn>", lambda event: self.clear_placeholder(self.client_id, "Client ID")
        )
        self.client_id.bind(
            "<FocusOut>", lambda event: self.set_placeholder(self.client_id, "Client ID")
        )

        self.client_secret.bind(
            "<FocusIn>", lambda event: self.clear_placeholder(self.client_secret, "Client Secret")
        )
        self.client_secret.bind(
            "<FocusOut>", lambda event: self.set_placeholder(self.client_secret, "Client Secret")
        )

        # Channel frame
        self.channel_frame = ttk.Frame(self.root, style="T.TFrame")
        self.channel_frame.grid(row=1, column=1, padx=10, columnspan=2)
        # channellabel
        self.channel_label = ttk.Label(
            self.channel_frame, style="T.TLabel", text=" Enter Channels:"
        )
        self.channel_label.grid(row=0, column=1, pady=5, padx=5, columnspan=2)
        # Channel button
        self.add_button = ttk.Button(
            self.channel_frame, style="C.TButton", text="ADD Channel", command=self.add_channel
        )
        self.remove_button = ttk.Button(
            self.channel_frame,
            style="C.TButton",
            text="DELETE Channel",
            command=self.remove_channel
        )
        self.add_button.grid(row=1, column=1, pady=5)
        self.remove_button.grid(row=1, column=2, pady=5)

        # Create a canvas for scrolling
        self.canvas = tk.Canvas(
            self.root,
            bg="#1f1f1f",
            height=150,
            width=250,
            highlightthickness=0,
            # scrollregion=(0, 0, 150, 250)
        )
        self.canvas.grid(row=2, column=1, pady=10, sticky="nsew")
        # Create a vertical scrollbar
        self.ch_scrollbar = ttk.Scrollbar(
            self.root, style="Vertical.TScrollbar", orient="vertical", command=self.on_scroll
        )
        self.ch_scrollbar.grid(row=2, column=2, pady=10, sticky="ns")
        # Configure the canvas
        self.canvas.configure(yscrollcommand=self.ch_scrollbar.set)
        # Channel entry frame
        self.channel_entries = []
        self.channel_entries_frame = ttk.Frame(self.canvas, style="T.TFrame")
        self.canvas.create_window((105, 0), window=self.channel_entries_frame, anchor="nw")
        # Make the frame scrollable
        self.channel_entries_frame.bind(
            "<Configure>",
            lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        # Start Record Button
        self.record_button = ttk.Button(
            self.root, style="R.TButton", text="Start Record", command=self.press_start_stop
        )
        self.record_button.grid(row=4, column=1, columnspan=2, pady=10)

        # Output Text
        self.output_text = tk.Text(
            self.root,
            bg="#2f2f2f",
            font=("Comic Sans MS", 14, "bold"),
            height=10,
            width=30,
            wrap="word",
            state=tk.DISABLED
        )
        self.output_text.grid(row=5, column=0, columnspan=2, pady=10, padx=5, sticky="nse")
        self.logger.add_textbox_handler(self.output_text, self.restore_window)

        self.tx_scrollbar = ttk.Scrollbar(
            self.root,
            style="Vertical.TScrollbar",
            orient="vertical",
            command=self.output_text.yview
        )
        self.tx_scrollbar.grid(row=5, column=2, pady=10, padx=10, sticky="nsw")
        self.output_text.configure(yscrollcommand=self.tx_scrollbar.set)

        self.root.grid_rowconfigure(3, weight=1)
        self.root.grid_columnconfigure(0, weight=0)
        self.root.grid_columnconfigure(1, weight=1)

    def clear_placeholder(self, entry, placeholder):
        """清除提示文字"""
        if entry.get() == placeholder:
            entry.delete(0, tk.END)

    def set_placeholder(self, entry, placeholder):
        """如果輸入框是空的，則設置提示文字"""
        if entry.get() == "":
            entry.insert(0, placeholder)

    def on_scroll(self, *args):
        if len(self.channel_entries) < 4:
            return
        self.canvas.yview(*args)

    def add_channel(self, channel=""):
        """按下ADD"""
        if self.channel_entries:
            # 使用 enumerate 將 entry 按順序排列到新的行位置
            [
                entry.grid(row=index + 1, column=0, pady=5, padx=5, columnspan=1)
                for index, entry in enumerate(self.channel_entries)
            ]

        _entry = ttk.Entry(
            self.channel_entries_frame, font=("Comic Sans MS", 12, "bold"), style="T.TEntry"
        )
        _entry.grid(row=len(self.channel_entries) + 1, column=0, pady=5, padx=5, columnspan=1)
        _entry.insert(0, channel)
        self.channel_entries.append(_entry)

    def remove_channel(self):
        """按下REMOVE"""
        if self.channel_entries:
            try:
                for index in range(len(self.channel_entries) - 1, -1, -1):
                    if self.channel_entries[index].get() == "":
                        entry_to_remove = self.channel_entries.pop(index)
                        entry_to_remove.destroy()
                        break  # 找到第一個符合條件的項目後跳出迴圈

            except Exception as e:
                self.logger.error(f"Channel To Remove Error:{e}")

    def press_start_stop(self):
        """按下開始OR停止"""
        if self.record_button["text"] == "Start Record":
            self.start_Record()
        else:
            self.stop_Record()

    def start_Record(self):
        try:
            client_id = self.client_id.get()
            client_secret = self.client_secret.get()
            channel_list = [entry.get() for entry in self.channel_entries if entry.get()]
            logger = self.logger
            token = self.token
            if not client_id or not client_secret or not channel_list:
                self.logger.error("Please make sure you have entered all required parameters")
                return
            else:
                self.client_id.config(state=tk.DISABLED)  # 讓所有按鈕和輸入框失效
                self.client_secret.config(state=tk.DISABLED)
                self.add_button.config(state=tk.DISABLED)
                self.remove_button.config(state=tk.DISABLED)
                for entry in self.channel_entries:
                    entry.config(state=tk.DISABLED)

                # 啟動實例和任務
                self.recorder = TwitchRecord(client_id, client_secret, channel_list, logger, token)
                self.record_task = asyncio.run_coroutine_threadsafe(
                    self.recorder.loop_check(), self.loop
                )
                self.record_button["text"] = "Stop  Record"
                self.record_button.configure(style="R1.TButton")

        except Exception as e:
            self.logger.exception(f"Record Error: {e}")

    def stop_Record(self):
        if self.record_task is not None:
            try:
                self.recorder.stop_check()
                asyncio.run_coroutine_threadsafe(self.recorder.close_process(), self.loop)

                self.client_id.config(state=tk.NORMAL)
                self.client_secret.config(state=tk.NORMAL)
                self.add_button.config(state=tk.NORMAL)
                self.remove_button.config(state=tk.NORMAL)
                if self.channel_entries:
                    [entry.config(state=tk.NORMAL) for entry in self.channel_entries]

                self.record_button["text"] = "Start Record"
                self.record_button.configure(style="R.TButton")

            except Exception as e:
                self.logger.error(f"Error while stopping recording task: {e}")

    def load_config(self):
        """從CONFIG中加載設置"""
        if os.path.exists(self.CONFIG_FILE):
            with open(self.CONFIG_FILE, "r") as f:
                config = json.load(f)
            client_id = config.get("client_id", "")
            client_secret = config.get("client_secret", "")
            channels = config.get("channels", [])

            # 載入配置時設定輸入框
            self.client_id.delete(0, tk.END)  # 清空輸入框
            if client_id:  # 如果讀取到的 client_id 不為空
                self.client_id.insert(0, client_id)
            else:  # 如果為空，保留提示文字
                self.client_id.insert(0, "Client ID")  # 提示文字

            self.client_secret.delete(0, tk.END)
            if client_secret:
                self.client_secret.insert(0, client_secret)
            else:
                self.client_secret.insert(0, "Client Secret")

            for channel in channels:
                self.add_channel(channel)

            if "token" in config:
                self.token = config["token"]

    def save_config(self):
        """將設置保存到CONFIG"""
        config = {
            "client_id": self.client_id.get(),
            "client_secret": self.client_secret.get(),
            "channels": [entry.get() for entry in self.channel_entries if entry.get()],
            "token": getattr(self.recorder, "_access_token", self.token)  # 如果recorder為空就使用原本token寫入
        }
        with open(self.CONFIG_FILE, "w") as f:
            json.dump(config, f)


if __name__ == "__main__":
    root = tk.Tk()
    app = TwitchRecorderApp(root)
    root.mainloop()
