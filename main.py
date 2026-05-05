import argparse
import logging
import os
import time

import yaml


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_services(cfg: dict):
    from stt import WhisperSTT
    from translator import Translator
    from tts_client import FishSpeechTTS

    sc = cfg["stt"]
    stt = WhisperSTT(sc["model"], sc["device"], sc["compute_type"])

    tc = cfg["translation"]
    key = tc.get("openrouter_api_key") or os.getenv("OPENROUTER_API_KEY", "")
    translator = Translator(api_key=key, model=tc["model"])

    fc = cfg["tts"]
    tts = FishSpeechTTS(
        server_url=fc["fish_speech_url"],
        reference_audio=fc["reference_audio"],
        reference_text=fc.get("reference_text", ""),
    )
    return stt, translator, tts


def main() -> None:
    parser = argparse.ArgumentParser(description="遊戲語音即時翻譯")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--send-only", action="store_true", help="只啟動發送管道")
    parser.add_argument("--receive-only", action="store_true", help="只啟動接收字幕")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)
    cfg = load_config(args.config)

    stt, translator, tts = build_services(cfg)

    pipelines = []
    subtitle = None

    if not args.receive_only:
        from send_pipeline import SendPipeline
        pipelines.append(SendPipeline(cfg, stt, translator, tts))

    if not args.send_only:
        loopback = cfg["audio"].get("loopback_device")
        if loopback is None:
            logging.warning("config.yaml 未設定 loopback_device，跳過接收字幕管道。")
        else:
            from subtitle import SubtitleWindow
            from receive_pipeline import ReceivePipeline
            subtitle = SubtitleWindow()
            pipelines.append(ReceivePipeline(cfg, stt, translator, subtitle))

    for p in pipelines:
        p.start()

    print("\n語音翻譯器執行中，按 Ctrl+C 停止。\n")

    try:
        if subtitle:
            subtitle.run()  # 主執行緒跑 tkinter mainloop（Windows 需要）
        else:
            while True:
                time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        print("\n正在關閉...")
        for p in pipelines:
            p.stop()
        if subtitle:
            subtitle.stop()


if __name__ == "__main__":
    main()
