import logging
import queue
import threading

import numpy as np

from audio_io import AudioCapture, play_audio, resolve_device
from stt import WhisperSTT
from translator import Translator
from tts_client import FishSpeechTTS
from vad import SileroVAD

log = logging.getLogger(__name__)


class SendPipeline:
    """
    發送管道：麥克風 → VAD → Whisper STT → OpenRouter 翻譯 → Fish Speech TTS → 虛擬麥克風
    TTS 播放期間暫停麥克風擷取，避免捕捉到自己的 TTS 輸出。
    """

    def __init__(self, cfg: dict, stt: WhisperSTT, translator: Translator, tts: FishSpeechTTS):
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
        self._my_lang = cfg["my_language"]
        self._partner_lang = cfg["partner_language"]
        self._out_dev = resolve_device(audio.get("output_device"))

        self._speech_q: queue.Queue[np.ndarray] = queue.Queue()
        self._tts_q: queue.Queue[str] = queue.Queue()
        self._playing = threading.Event()
        self._stop = threading.Event()

        self._capture = AudioCapture(
            on_chunk=self._on_chunk,
            device=resolve_device(audio.get("input_device")),
            samplerate=audio["sample_rate"],
            block_size=audio["block_size"],
        )

    def _on_chunk(self, chunk: np.ndarray) -> None:
        if self._playing.is_set():
            return
        result = self._vad.process_chunk(chunk)
        if result is not None:
            self._speech_q.put(result)

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
                translated = self._translator.translate(text, lang, self._partner_lang)
                if translated:
                    log.info("[→%s] %s", self._partner_lang, translated)
                    self._tts_q.put(translated)
            except Exception as e:
                log.error("STT/translate error: %s", e)

    def _tts_worker(self) -> None:
        while not self._stop.is_set():
            try:
                text = self._tts_q.get(timeout=0.5)
            except queue.Empty:
                continue
            self._playing.set()
            try:
                audio, sr = self._tts.synthesize(text)
                play_audio(audio, sr, device=self._out_dev)
            except Exception as e:
                log.error("TTS error: %s", e)
            finally:
                self._playing.clear()

    def start(self) -> None:
        self._stop.clear()
        threading.Thread(target=self._stt_worker, daemon=True, name="send-stt").start()
        threading.Thread(target=self._tts_worker, daemon=True, name="send-tts").start()
        self._capture.start()
        log.info("Send pipeline: %s → %s", self._my_lang, self._partner_lang)

    def stop(self) -> None:
        self._stop.set()
        self._capture.stop()
