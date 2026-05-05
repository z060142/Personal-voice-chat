import datetime
import logging
import os
import queue
import threading

import numpy as np
import soundfile as sf

from audio_io import AudioCapture, play_audio, resolve_device
from stt import WhisperSTT
from translator import Translator
from tts_client import FishSpeechTTS
from vad import SileroVAD

log = logging.getLogger(__name__)

_QUEUE_MAXSIZE = 20


class SendPipeline:
    """
    發送管道：麥克風 → VAD/PTT → Whisper STT → OpenRouter 翻譯 → Fish Speech TTS → 虛擬麥克風

    支援：
    - VAD 模式（預設）：自動偵測語音結束
    - PTT 模式：按住指定按鍵才錄音
    - 暫停/繼續（F9 預設）
    - 字幕同時顯示原文與翻譯
    - debug.save_utterances：保存每句錄音與辨識文字
    """

    def __init__(
        self,
        cfg: dict,
        stt: WhisperSTT,
        translator: Translator,
        tts: FishSpeechTTS,
        subtitle=None,
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
        self._tts = tts
        self._subtitle = subtitle
        self._my_lang = cfg["my_language"]
        self._partner_lang = cfg["partner_language"]
        self._out_dev = resolve_device(audio.get("output_device"))
        self._sample_rate = audio["sample_rate"]

        debug_cfg = cfg.get("debug", {})
        self._debug_save = debug_cfg.get("save_utterances", False)
        self._debug_dir = debug_cfg.get("output_dir", "debug_audio")

        self._speech_q: queue.Queue[np.ndarray] = queue.Queue(maxsize=_QUEUE_MAXSIZE)
        self._tts_q: queue.Queue[str] = queue.Queue(maxsize=_QUEUE_MAXSIZE)
        self._playing = threading.Event()
        self._paused = threading.Event()
        self._ptt_mode = False
        self._ptt_active = threading.Event()
        self._ptt_label = "PTT"
        self._stop = threading.Event()

        self._capture = AudioCapture(
            on_chunk=self._on_chunk,
            device=resolve_device(audio.get("input_device")),
            samplerate=audio["sample_rate"],
            block_size=audio["block_size"],
        )

    # ── Public: hotkey callbacks ────────────────────────────────────────

    def toggle_pause(self):
        if self._paused.is_set():
            self._paused.clear()
            log.info("Send pipeline 繼續")
        else:
            self._paused.set()
            log.info("Send pipeline 暫停")
        self._push_status()

    def ptt_press(self):
        self._ptt_active.set()
        self._push_status()

    def ptt_release(self):
        self._ptt_active.clear()
        remaining = self._vad.force_flush()
        if remaining is not None:
            self._enqueue_speech(remaining)
        self._push_status()

    def set_ptt_mode(self, enabled: bool, key_label: str = "PTT"):
        self._ptt_mode = enabled
        self._ptt_label = key_label

    # ── Internal ─────────────────────────────────────────────────────

    def _should_record(self) -> bool:
        if self._stop.is_set() or self._paused.is_set() or self._playing.is_set():
            return False
        if self._ptt_mode and not self._ptt_active.is_set():
            return False
        return True

    def _enqueue_speech(self, audio: np.ndarray) -> None:
        try:
            self._speech_q.put_nowait(audio)
        except queue.Full:
            log.warning("send speech_q 已滿，捨棄此段錄音")

    def _on_chunk(self, chunk: np.ndarray) -> None:
        if not self._should_record():
            return
        result = self._vad.process_chunk(chunk)
        if result is not None:
            self._enqueue_speech(result)

    def _push_status(self):
        if not self._subtitle:
            return
        q = self._tts_q.qsize()
        if self._paused.is_set():
            s = f"⏸ 已暫停  |  佇列: {q}  [按 F9 繼續]"
        elif self._playing.is_set():
            s = f"🔊 播放中  |  佇列: {q}"
        elif self._ptt_mode:
            if self._ptt_active.is_set():
                s = f"🔴 錄音中 (PTT)  |  佇列: {q}"
            else:
                s = f"□ 按住 {self._ptt_label} 說話  |  佇列: {q}"
        else:
            s = f"● 活躍 (VAD)  |  佇列: {q}  [F9 暫停]"
        self._subtitle.update_status(s)

    def _save_debug(self, prefix: str, audio: np.ndarray, stt_text: str, translated: str) -> None:
        try:
            os.makedirs(self._debug_dir, exist_ok=True)
            ts = datetime.datetime.now().strftime("%H%M%S_%f")[:9]
            base = os.path.join(self._debug_dir, f"{prefix}_{ts}")
            sf.write(f"{base}.wav", audio, self._sample_rate)
            with open(f"{base}.txt", "w", encoding="utf-8") as f:
                f.write(f"STT: {stt_text}\nTranslated: {translated}\n")
        except Exception as e:
            log.warning("debug save 失敗: %s", e)

    def _stt_worker(self) -> None:
        while not self._stop.is_set():
            try:
                audio = self._speech_q.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                text, lang = self._stt.transcribe(audio, language=self._my_lang)
                if not text:
                    continue
                log.info("[STT %s] %s", lang, text)
                if self._subtitle:
                    self._subtitle.update_send_original(f"我原文: {text}")
                translated = self._translator.translate(text, lang, self._partner_lang)
                if translated:
                    log.info("[→%s] %s", self._partner_lang, translated)
                    if self._debug_save:
                        self._save_debug("send", audio, text, translated)
                    try:
                        self._tts_q.put_nowait(translated)
                    except queue.Full:
                        log.warning("send tts_q 已滿，捨棄此段翻譯")
                    self._push_status()
            except Exception as e:
                log.error("STT/translate error: %s", e)

    def _tts_worker(self) -> None:
        while not self._stop.is_set():
            try:
                text = self._tts_q.get(timeout=0.5)
            except queue.Empty:
                continue
            self._playing.set()
            if self._subtitle:
                self._subtitle.update_send(f"你: {text}")
            self._push_status()
            try:
                audio, sr = self._tts.synthesize(text)
                play_audio(audio, sr, device=self._out_dev)
            except Exception as e:
                log.error("TTS error: %s", e)
            finally:
                self._playing.clear()
                self._push_status()

    def start(self) -> None:
        self._stop.clear()
        threading.Thread(target=self._stt_worker, daemon=True, name="send-stt").start()
        threading.Thread(target=self._tts_worker, daemon=True, name="send-tts").start()
        self._capture.start()
        self._push_status()
        mode = "PTT" if self._ptt_mode else "VAD"
        log.info("Send pipeline [%s]: %s → %s", mode, self._my_lang, self._partner_lang)

    def stop(self) -> None:
        self._stop.set()
        self._capture.stop()
