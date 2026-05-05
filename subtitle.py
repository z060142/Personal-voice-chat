import queue
import tkinter as tk


class SubtitleWindow:
    """
    常駐在螢幕底部的字幕視窗。

    三行顯示：
      1. 狀態列（灰色）：活躍/暫停/PTT + 佇列數
      2. 發送列（金黃）：TTS 目前播放的內容
      3. 接收列（白色）：對方語音的翻譯結果

    show() / update_* 可從任意執行緒呼叫。
    run() 必須在主執行緒呼叫（Windows tkinter 限制）。
    """

    def __init__(self, font_size: int = 18, opacity: float = 0.85):
        self._q: queue.Queue = queue.Queue()
        self.font_size = font_size
        self.opacity = opacity
        self._root = None
        self._status_label = None
        self._send_label = None
        self._recv_label = None

    # ── Thread-safe update API ────────────────────────────────────────────

    def update_status(self, text: str) -> None:
        self._q.put(("status", text))

    def update_send(self, text: str) -> None:
        self._q.put(("send", text))

    def update_receive(self, text: str) -> None:
        self._q.put(("receive", text))

    def stop(self) -> None:
        self._q.put(("quit", None))

    # ── Main-thread tkinter ─────────────────────────────────────────────

    def run(self) -> None:
        """Blocks the calling thread. Must be called from the main thread."""
        self._root = tk.Tk()
        self._root.title("Voice Translate")
        self._root.attributes("-topmost", True)
        self._root.attributes("-alpha", self.opacity)
        self._root.overrideredirect(True)
        self._root.configure(bg="#111111")

        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()

        self._status_label = tk.Label(
            self._root,
            text="初始化中...",
            font=("Consolas", self.font_size - 4),
            fg="#888888",
            bg="#111111",
            wraplength=sw - 80,
            justify="left",
            anchor="w",
            padx=14,
            pady=3,
        )
        self._status_label.pack(fill="x")

        self._send_label = tk.Label(
            self._root,
            text="",
            font=("Arial", self.font_size, "bold"),
            fg="#FFD700",
            bg="#111111",
            wraplength=sw - 80,
            justify="left",
            anchor="w",
            padx=14,
            pady=4,
        )
        self._send_label.pack(fill="x")

        self._recv_label = tk.Label(
            self._root,
            text="",
            font=("Arial", self.font_size),
            fg="#FFFFFF",
            bg="#111111",
            wraplength=sw - 80,
            justify="left",
            anchor="w",
            padx=14,
            pady=4,
        )
        self._recv_label.pack(fill="x")

        self._root.update_idletasks()
        w = self._root.winfo_width()
        h = self._root.winfo_height()
        self._root.geometry(f"+{(sw - w) // 2}+{sh - h - 80}")

        self._root.after(80, self._poll)
        self._root.mainloop()

    def _poll(self) -> None:
        try:
            while True:
                cmd, data = self._q.get_nowait()
                if cmd == "quit":
                    self._root.quit()
                    return
                elif cmd == "status":
                    self._status_label.config(text=data)
                elif cmd == "send":
                    self._send_label.config(text=data)
                elif cmd == "receive":
                    self._recv_label.config(text=data)
        except queue.Empty:
            pass
        self._root.after(80, self._poll)
