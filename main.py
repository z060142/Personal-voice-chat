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


def check_config(cfg: dict) -> None:
    """檢查設備、reference audio、API key、Fish Speech server 連線。"""
    import httpx
    import sounddevice as sd

    errors = []
    warnings = []

    # API key
    tc = cfg["translation"]
    key = tc.get("openrouter_api_key") or os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        errors.append(
            "translation.openrouter_api_key 未設定，也未設定 OPENROUTER_API_KEY 環境變數"
        )
    else:
        print("  [OK] OpenRouter API key 已設定")

    # Reference audio
    fc = cfg["tts"]
    ref = fc.get("reference_audio", "")
    if not ref or not os.path.exists(ref):
        errors.append(f"tts.reference_audio 找不到檔案: {ref!r}")
    else:
        print(f"  [OK] reference_audio: {ref}")

    # Audio devices
    try:
        devices = sd.query_devices()
        audio = cfg["audio"]
        for key_name, label in [
            ("input_device", "input_device（麥克風）"),
            ("output_device", "output_device（虛擬麥克風）"),
            ("loopback_device", "loopback_device（遊戲音效擷取）"),
        ]:
            dev_id = audio.get(key_name)
            if dev_id is None:
                warnings.append(f"audio.{key_name} 未設定（null）")
            elif isinstance(dev_id, int) and dev_id >= len(devices):
                errors.append(f"audio.{key_name}={dev_id} 超出設備清單範圍（共 {len(devices)} 個）")
            else:
                name = devices[dev_id]["name"] if isinstance(dev_id, int) else dev_id
                print(f"  [OK] {label}: {dev_id} ({name})")
    except Exception as e:
        warnings.append(f"無法查詢音訊設備：{e}")

    # Fish Speech server
    url = fc.get("fish_speech_url", "http://127.0.0.1:8080")
    try:
        with httpx.Client(timeout=3.0) as client:
            r = client.get(url)
        print(f"  [OK] Fish Speech server: {url} (HTTP {r.status_code})")
    except Exception as e:
        warnings.append(f"Fish Speech server 無法連線 ({url})：{e}")

    print()
    if warnings:
        for w in warnings:
            print(f"  [WARN] {w}")
    if errors:
        print()
        for e in errors:
            print(f"  [ERROR] {e}")
        raise SystemExit(1)
    if not errors and not warnings:
        print("所有設定檢查通過！")
    else:
        print("設定可用（有警告，請確認上述項目）。")


def build_services(cfg: dict):
    from stt import WhisperSTT
    from translator import Translator
    from tts_client import FishSpeechTTS

    sc = cfg["stt"]
    stt = WhisperSTT(sc["model"], sc["device"], sc["compute_type"])

    tc = cfg["translation"]
    key = tc.get("openrouter_api_key") or os.getenv("OPENROUTER_API_KEY", "")
    try:
        translator = Translator(
            api_key=key,
            model=tc["model"],
            game_context=tc.get("game_context", ""),
        )
    except ValueError as e:
        raise SystemExit(f"設定錯誤：{e}") from e

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
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="檢查設備、API key、Fish Speech server 後退出",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)
    cfg = load_config(args.config)

    if args.check_config:
        print("正在檢查設定...\n")
        check_config(cfg)
        return

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
            tts_playing = send_pipe._playing if send_pipe else None
            pipelines.append(ReceivePipeline(cfg, stt, translator, subtitle, tts_playing=tts_playing))

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
