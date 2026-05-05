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
    translator = Translator(
        api_key=key,
        model=tc["model"],
        game_context=tc.get("game_context", ""),
    )

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
    parser.add_argument("--send-only", action="store_true")
    parser.add_argument("--receive-only", action="store_true")
    parser.add_argument("--no-ui", action="store_true", help="停用字幕視窗")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)
    cfg = load_config(args.config)

    no_ui = args.no_ui or cfg.get("ui", {}).get("no_ui", False)

    stt, translator, tts = build_services(cfg)

    from hotkeys import HotkeyManager
    hotkeys = HotkeyManager(cfg)

    ui_cfg = cfg.get("ui", {})
    subtitle = None
    if not no_ui:
        from subtitle import SubtitleWindow
        subtitle = SubtitleWindow(
            font_size=ui_cfg.get("font_size", 18),
            opacity=ui_cfg.get("opacity", 0.85),
        )

    pipelines = []
    send_pipe = None

    if not args.receive_only:
        from send_pipeline import SendPipeline
        send_pipe = SendPipeline(cfg, stt, translator, tts, subtitle=subtitle)

        if hotkeys.ptt_enabled:
            send_pipe.set_ptt_mode(True, key_label=hotkeys.ptt_label)

        hotkeys.on_pause_toggle(send_pipe.toggle_pause)
        hotkeys.on_ptt_press(send_pipe.ptt_press)
        hotkeys.on_ptt_release(send_pipe.ptt_release)

        pipelines.append(send_pipe)

    if not args.send_only:
        loopback = cfg["audio"].get("loopback_device")
        if loopback is None:
            logging.warning("config.yaml 未設定 loopback_device，跳過接收字幕管道。")
        elif subtitle is None:
            logging.warning("接收管道需要字幕視窗，但 --no-ui 已啟用，跳過。")
        else:
            from receive_pipeline import ReceivePipeline
            pipelines.append(ReceivePipeline(cfg, stt, translator, subtitle))

    hotkeys.start()
    for p in pipelines:
        p.start()

    print("\n語音翻譯器執行中，按 Ctrl+C 停止。\n")

    try:
        if subtitle:
            subtitle.run()  # blocks main thread (tkinter on Windows)
        else:
            while True:
                time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        print("\n正在關閉...")
        hotkeys.stop()
        for p in pipelines:
            p.stop()
        if subtitle:
            subtitle.stop()


if __name__ == "__main__":
    main()
