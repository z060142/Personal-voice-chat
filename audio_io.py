import numpy as np
import sounddevice as sd


def list_devices() -> None:
    devices = sd.query_devices()
    print("\n音頻設備列表:")
    print("=" * 65)
    for i, d in enumerate(devices):
        tags = []
        if d["max_input_channels"] > 0:
            tags.append("IN")
        if d["max_output_channels"] > 0:
            tags.append("OUT")
        print(f"[{i:2d}] [{'/'.join(tags):6s}] {d['name']}")
    print("=" * 65)


def resolve_device(name_or_index) -> int | None:
    if name_or_index is None:
        return None
    if isinstance(name_or_index, int):
        return name_or_index
    for i, d in enumerate(sd.query_devices()):
        if name_or_index.lower() in d["name"].lower():
            return i
    raise ValueError(f"找不到音頻設備: {name_or_index}")


class AudioCapture:
    def __init__(self, on_chunk, device=None, samplerate=16000, block_size=512):
        self.on_chunk = on_chunk
        self._stream = sd.InputStream(
            device=device,
            samplerate=samplerate,
            channels=1,
            dtype="float32",
            blocksize=block_size,
            callback=self._cb,
        )

    def _cb(self, indata, frames, time, status):
        if self.on_chunk:
            self.on_chunk(indata[:, 0].copy())

    def start(self):
        self._stream.start()

    def stop(self):
        self._stream.stop()
        self._stream.close()


def play_audio(audio: np.ndarray, samplerate: int, device=None) -> None:
    sd.play(audio, samplerate=samplerate, device=device)
    sd.wait()
