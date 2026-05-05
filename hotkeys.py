import logging

from pynput import keyboard

log = logging.getLogger(__name__)


def _parse_key(key_str: str):
    """Config 字串解析為 pynput 按鍵物件。"""
    s = key_str.lower().strip()
    if hasattr(keyboard.Key, s):
        return getattr(keyboard.Key, s)
    if len(s) == 1:
        return keyboard.KeyCode.from_char(s)
    log.warning("無法解析按鍵: %s", key_str)
    return None


class HotkeyManager:
    """
    全域快J捷鍵管理器。
    - pause_toggle: 按一下切換暫停/繼續
    - push_to_talk: 按住才錄音（PTT 模式）
    """

    def __init__(self, cfg: dict):
        hk = cfg.get("hotkeys", {})
        pause_str = hk.get("pause_toggle", "f9")
        ptt_str = hk.get("push_to_talk")

        self._pause_key = _parse_key(pause_str) if pause_str else None
        self._ptt_key = _parse_key(ptt_str) if ptt_str else None
        self._pause_label = pause_str.upper() if pause_str else ""
        self._ptt_label = ptt_str.upper() if ptt_str else ""

        self._on_pause: list = []
        self._on_ptt_press: list = []
        self._on_ptt_release: list = []
        self._listener = None

    @property
    def ptt_label(self) -> str:
        return self._ptt_label

    @property
    def ptt_enabled(self) -> bool:
        return self._ptt_key is not None

    def on_pause_toggle(self, fn):
        self._on_pause.append(fn)
        return self

    def on_ptt_press(self, fn):
        self._on_ptt_press.append(fn)
        return self

    def on_ptt_release(self, fn):
        self._on_ptt_release.append(fn)
        return self

    def _on_press(self, key):
        if self._pause_key and key == self._pause_key:
            for fn in self._on_pause:
                fn()
        if self._ptt_key and key == self._ptt_key:
            for fn in self._on_ptt_press:
                fn()

    def _on_release(self, key):
        if self._ptt_key and key == self._ptt_key:
            for fn in self._on_ptt_release:
                fn()

    def start(self):
        if not self._pause_key and not self._ptt_key:
            log.info("Hotkeys: 未設定")
            return
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()
        parts = []
        if self._pause_label:
            parts.append(f"暫停切換={self._pause_label}")
        if self._ptt_label:
            parts.append(f"PTT={self._ptt_label}")
        log.info("Hotkeys 啟動: %s", ", ".join(parts))

    def stop(self):
        if self._listener:
            self._listener.stop()
