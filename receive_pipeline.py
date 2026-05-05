import datetime
import logging
import os
import queue
import threading

import numpy as np
import soundfile as sf

from audio_io import AudioCapture, resolve_device
from stt import WhisperSTT
from subtitle import SubtitleWindow
from translator import Translator
from vad import SileroVAD

log = logging.getLogger(__name__)

_QUEUE_MAXSIZE = 20


class ReceivePipeline:
    """
    接收管道：遊戲/Discord 音頻（loopback）→ VAD → Whisper STT → OpenRouter 翻譯 → 字幕

    支援：
    - tts_playing：TTS 播放期間暫停辨識，避免把自己的 TTS 當成對方語音
    - 字幕同時顯示對方原文與翻譯
    - debug.save_utterances：保存每句錄音與辨識文字
    """

    def __init__(
        self,
        cfg: dict,
        stt: WhisperSTT,
        translator: Translator,
        subtitle: SubtitleWindow,
        tts_playing: threading.Event = None,
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
        self._tts_playing = tts_playing
        self._sample_rate = audio["sample_rate"]

        debug_cfg = cfg.get("debug", {})
        self._debug_save = debug_cfg.get("save_utterances", False)
        self._debug_dir = debug_cfg.get("output_dir", "debug_audio")

        self._speech_q: queue.Queue[np.ndarray] = queue.Queue(maxsize=_QUEUE_MAXSIZE)
        self._stop = threading.Event()

        self._capture = AudioCapture(
            on_chunk=self._on_chunk,
            device=resolve_device(audio.get("loopback_device")),
            samplerate=audio["sample_rate"],
            block_size=audio["block_size"],
        )

    def _on_chunk(self, chunk: np.ndarray) -> None:
        if self._tts_playing and self._tts_playing.is_set():
            return
        result = self._vad.process_chunk(chunk)
        if result is not None:
            try:
                self._speech_q.put_nowait(result)
            except queue.Full:
                log.warning("recv speech_q 已滿，捨棄此段錄音")

    def _save_debug(self, audio: np.ndarray, stt_text: str, translated: str) -> None:
        try:
            os.makedirs(self._debug_dir, exist_ok=True)
            ts = datetime.datetime.now().strftime("%H%M%S_%f")[:9]
            base = os.path.join(self._debug_dir, f"recv_{ts}")
            sf.write(f"{base}.wav", audio, self._sample_rate)
            with open(f"{base}.txt", "w", encoding="utf-8") as f:
                f.write(f"STT: {stt_text}\nTranslated: {translated}\n")
        except Exception as e:
            log.warning("debug save 失敗: %s", e)

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
                self._subtitle.update_receive_original(f"[{lang}] {text}")
                translated = self._translator.translate(text, lang, self._my_lang)
                if translated:
                    log.info("[→%s] %s", self._my_lang, translated)
                    if self._debug_save:
                        self._save_debug(audio, text, translated)
                    self._subtitle.update_receive(f"對方: {translated}")
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
