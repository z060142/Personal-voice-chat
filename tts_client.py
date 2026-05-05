import base64
import io

import httpx
import numpy as np
import soundfile as sf


class FishSpeechTTS:
    """
    Fish Speech HTTP API 客戶端。
    需要先啟動 Fish Speech 伺服器（預設 http://127.0.0.1:8080）。
    reference_audio 為你的聲音樣本 WAV 檔，用於音色複製。
    """

    def __init__(self, server_url: str, reference_audio: str, reference_text: str = ""):
        self.url = server_url.rstrip("/") + "/v1/tts"
        self._ref_b64 = self._encode(reference_audio)
        self._ref_text = reference_text

    @staticmethod
    def _encode(path: str) -> str:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()

    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        """回傳 (float32 音頻陣列, 取樣率)。"""
        payload = {
            "text": text,
            "references": [{"audio": self._ref_b64, "text": self._ref_text}],
            "format": "wav",
            "streaming": False,
        }
        with httpx.Client(timeout=30.0) as client:
            r = client.post(self.url, json=payload)
            if not r.is_success:
                body_preview = r.text[:500] if r.text else "(empty)"
                raise RuntimeError(
                    f"Fish Speech server 回傳錯誤 {r.status_code}：{body_preview}"
                )
        audio, sr = sf.read(io.BytesIO(r.content))
        if audio.ndim > 1:
            audio = audio.mean(axis=1)  # 轉單聲道
        return audio.astype(np.float32), sr
