import queue
import tkinter as tk


class SubtitleWindow:
    """
    常駐在螢幕底部的字幕視窗。

    五行顯示：
      1. 狀態列（灰色）：活躍/暫停/PTT + 佇列數
      2. 我原文（暗金）：自己說話的 STT 原文
      3. 我譯文（亮金 bold）：TTS 播放的翻譯結果
      4. 對方原文（暗白）：對方語音的 STT 原文
      5. 對方譯文（白色）：對方翻譯後的字幕

    show() / update_* 可從任意執行緒呼叫。
    run() 必須在主執行緒呼叫（Windows tkinter 限制）。
    """

    def __init__(self, font_size: int = 18, opacity: float = 0.85):
        self._q: queue.Queue = queue.Queue()
        self.font_size = font_size
        self.opacity = opacity
        self._root = None
        self._status_label = None
        self._send_orig_label = None
        self._send_label = None
        self._recv_orig_label = None
        self._recv_label = None

    # ── Thread-safe update API ────────────────────────────────────────────

    def update_status(self, text: str) -> None:
        self._q.put(("status", text))

    def update_send_original(self, text: str) -> None:
        self._q.put(("send_orig", text))

    def update_send(self, text: str) -> None:
        self._q.put(("send", text))

    def update_receive_original(self, text: str) -> None:
        self._q.put(("recv_orig", text))

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
            pady=2,
        )
        self._status_label.pack(fill="x")

        self._send_orig_label = tk.Label(
            self._root,
            text="",
            font=("Arial", self.font_size - 3),
            fg="#A08020",
            bg="#111111",
            wraplength=sw - 80,
            justify="left",
            anchor="w",
            padx=14,
            pady=1,
        )
        self._send_orig_label.pack(fill="x")

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
            pady=3,
        )
        self._send_label.pack(fill="x")

        self._recv_orig_label = tk.Label(
            self._root,
            text="",
            font=("Arial", self.font_size - 3),
            fg="#666666",
            bg="#111111",
            wraplength=sw - 80,
            justify="left",
            anchor="w",
            padx=14,
            pady=1,
        )
        self._recv_orig_label.pack(fill="x")

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
            pady=3,
        )
        self._recv_label.pack(fill="x")

        self._root.update_idletasks()
        w = self._root.winfo_width()
        h = self._root.winfo_height()
        sh = self._root.winfo_screenheight()
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
                elif cmd == "send_orig":
                    self._send_orig_label.config(text=data)
                elif cmd == "send":
                    self._send_label.config(text=data)
                elif cmd == "recv_orig":
                    self._recv_orig_label.config(text=data)
                elif cmd == "receive":
                    self._recv_label.config(text=data)
        except queue.Empty:
            pass
        self._root.after(80, self._poll)
