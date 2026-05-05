"""列出所有音頻設備及其編號，填入 config.yaml 使用。"""
from audio_io import list_devices

if __name__ == "__main__":
    list_devices()
    print("\n將設備編號填入 config.yaml 中對應欄位。")
