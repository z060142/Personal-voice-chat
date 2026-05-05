import queue
import tkinter as tk


class SubtitleWindow:
    """
    常駐在螢幕底部的字幕視窗。
    show() 可從任意執行緒呼叫；run() 必須在主執行緒執行（Windows tkinter 限制）。
    """

    def __init__(self, font_size: int = 20, opacity: float = 0.85):
        self._q: queue.Queue = queue.Queue()
        self.font_size = font_size
        self.opacity = opacity
        self._root = None
        self._label = None

    def show(self, text: str) -> None:
        """執行緒安全的文字更新。"""
        self._q.put(("text", text))

    def stop(self) -> None:
        self._q.put(("quit", None))

    def run(self) -> None:
        """在主執行緒執行 tkinter mainloop，關閉視窗或呼叫 stop() 才會返回。"""
        self._root = tk.Tk()
        self._root.title("Voice Translate")
        self._root.attributes("-topmost", True)
        self._root.attributes("-alpha", self.opacity)
        self._root.overrideredirect(True)  # 無標題欄
        self._root.configure(bg="black")

        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()

        self._label = tk.Label(
            self._root,
            text="",
            font=("Arial", self.font_size, "bold"),
            fg="white",
            bg="black",
            wraplength=sw - 120,
            justify="center",
            padx=20,
            pady=10,
        )
        self._label.pack()

        self._root.update_idletasks()
        w, h = self._root.winfo_width(), self._root.winfo_height()
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
                self._label.config(text=data)
        except queue.Empty:
            pass
        self._root.after(80, self._poll)
