import logging
import queue
import threading

import numpy as np

from audio_io import AudioCapture, resolve_device
from stt import WhisperSTT
from subtitle import SubtitleWindow
from translator import Translator
from vad import SileroVAD

log = logging.getLogger(__name__)


class ReceivePipeline:
    """
    接收管道：遊戲/Discord 音頻（loopback）→ VAD → Whisper STT → OpenRouter 翻譯 → 螢幕字幕
    """

    def __init__(
        self,
        cfg: dict,
        stt: WhisperSTT,
        translator: Translator,
        subtitle: SubtitleWindow,
    ):
        audio = cfg["audio"]
        vad_cfg = cfg["vad"]

        self._vad = SileroVAD(
            threshold=vad_cfg["threshold"],
            sampling_rate=audio["sample_rate"],
            min_speech_ms=vad_cfg["min_speech_ms"],
            min_silence_ms=vad_cfg["min_silence_ms"],
            max_speech_ms=vad_cfg["max_speech_ms"],
        )
        self._stt = stt
        self._translator = translator
        self._subtitle = subtitle
        self._my_lang = cfg["my_language"]
        self._partner_lang = cfg["partner_language"]

        self._speech_q: queue.Queue[np.ndarray] = queue.Queue()
        self._stop = threading.Event()

        self._capture = AudioCapture(
            on_chunk=self._on_chunk,
            device=resolve_device(audio.get("loopback_device")),
            samplerate=audio["sample_rate"],
            block_size=audio["block_size"],
        )

    def _on_chunk(self, chunk: np.ndarray) -> None:
        result = self._vad.process_chunk(chunk)
        if result is not None:
            self._speech_q.put(result)

    def _worker(self) -> None:
        while not self._stop.is_set():
            try:
                audio = self._speech_q.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                text, lang = self._stt.transcribe(audio)
                if not text:
                    continue
                log.info("[RECV %s] %s", lang, text)
                translated = self._translator.translate(text, lang, self._my_lang)
                if translated:
                    log.info("[→%s] %s", self._my_lang, translated)
                    self._subtitle.show(f"[{lang.upper()}] {translated}")
            except Exception as e:
                log.error("Receive pipeline error: %s", e)

    def start(self) -> None:
        self._stop.clear()
        threading.Thread(target=self._worker, daemon=True, name="recv-worker").start()
        self._capture.start()
        log.info("Receive pipeline: loopback → %s subtitle", self._my_lang)

    def stop(self) -> None:
        self._stop.set()
        self._capture.stop()
