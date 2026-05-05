import numpy as np
import torch
from silero_vad import load_silero_vad


class SileroVAD:
    """流式 VAD：逐 512-sample chunk 偵測語音，utterance 結束時回傳完整音訊。"""

    CHUNK_SIZE = 512  # 32ms @ 16000Hz

    def __init__(
        self,
        threshold: float = 0.5,
        sampling_rate: int = 16000,
        min_speech_ms: int = 300,
        min_silence_ms: int = 700,
        max_speech_ms: int = 30000,
    ):
        self.model = load_silero_vad()
        self.sr = sampling_rate
        self.threshold = threshold
        self.min_speech = int(sampling_rate * min_speech_ms / 1000)
        self.min_silence = int(sampling_rate * min_silence_ms / 1000)
        self.max_speech = int(sampling_rate * max_speech_ms / 1000)
        self._reset()

    def _reset(self):
        self.model.reset_states()
        self._buf: list[np.ndarray] = []
        self._in_speech = False
        self._silence = 0
        self._total = 0

    def process_chunk(self, chunk: np.ndarray) -> np.ndarray | None:
        """傳入 512-sample float32 陣列，utterance 結束時回傳語音陣列，否則回傳 None。"""
        prob = self.model(torch.from_numpy(chunk).float(), self.sr).item()
        is_speech = prob >= self.threshold

        if is_speech:
            self._in_speech = True
            self._silence = 0
            self._buf.append(chunk)
            self._total += len(chunk)
        elif self._in_speech:
            self._buf.append(chunk)
            self._silence += len(chunk)
            self._total += len(chunk)
            if self._silence >= self.min_silence or self._total >= self.max_speech:
                return self._flush()

        return None

    def _flush(self) -> np.ndarray | None:
        result = np.concatenate(self._buf) if self._total >= self.min_speech else None
        self._reset()
        return result

    def force_flush(self) -> np.ndarray | None:
        """強制輸出目前緩衝（程式結束前用）。"""
        if self._in_speech and self._buf:
            return self._flush()
        return None
