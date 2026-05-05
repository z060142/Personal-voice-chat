import threading

import numpy as np
from faster_whisper import WhisperModel


class WhisperSTT:
    def __init__(self, model_size="large-v3", device="cuda", compute_type="float16"):
        print(f"載入 Whisper {model_size} ({device}/{compute_type})...")
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        self._lock = threading.Lock()  # send/receive 共用同一個模型，需要 lock
        print("Whisper 就緒。")

    def transcribe(self, audio: np.ndarray, language: str = None) -> tuple[str, str]:
        """回傳 (辨識文字, 偵測到的語言代碼)。"""
        with self._lock:
            segments, info = self.model.transcribe(
                audio,
                beam_size=5,
                language=language or None,
                vad_filter=False,
            )
            text = " ".join(s.text.strip() for s in segments)
        return text.strip(), info.language
