# Personal Voice Chat Translator

遊戲語音即時翻譯器：
- **發送**：你說話 → Whisper STT → OpenRouter LLM 翻譯 → Fish Speech TTS（你的音色）→ 虛擬麥克風 → Discord/遊戲
- **接收**：對方語音（loopback）→ Whisper STT → OpenRouter LLM 翻譯 → 螢幕字幕

## Feature Review

針對原始「遊戲語音 → STT → 翻譯 → TTS」需求的功能審查、風險與 roadmap，請見 [`FEATURE_REVIEW.md`](FEATURE_REVIEW.md)。

## 架構

```
麥克風
  └─ VAD (silero) ─ STT (Whisper large-v3) ─ 翻譯 (OpenRouter) ─ TTS (Fish Speech) ─ CABLE Input ─ Discord

遊戲音頻 (Stereo Mix / VoiceMeeter)
  └─ VAD (silero) ─ STT (Whisper large-v3) ─ 翻譯 (OpenRouter) ─ 字幕視窗
```

## 安裝

### 1. PyTorch（CUDA 版）

前往 https://pytorch.org 選擇你的 CUDA 版本，例如 CUDA 12.1：

```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### 2. 其他套件

```bash
pip install -r requirements.txt
```

### 3. Fish Speech 伺服器

1. 依照 [Fish Speech 官方文件](https://github.com/fishaudio/fish-speech) 安裝
2. 準備 10–30 秒的自己聲音 WAV 錄音，存為 `reference.wav`
3. 啟動 Fish Speech API 伺服器（預設監聽 8080 port）

### 4. 虛擬音頻設備（發送模式）

安裝 [VB-Audio Virtual Cable](https://vb-audio.com/Cable/)，重啟後出現 **CABLE Input / CABLE Output**。

在 Discord/遊戲中，將麥克風改為 **CABLE Output**，程式會把 TTS 輸出打到 CABLE Input。

### 5. OpenRouter API 金鑰

至 https://openrouter.ai 申請後，設置環境變數：

```bash
# Windows
set OPENROUTER_API_KEY=sk-or-xxxx

# 或寫入 config.yaml 的 translation.openrouter_api_key
```

## 設定

```bash
python list_devices.py   # 列出所有音頻設備及編號
```

編輯 `config.yaml`：

```yaml
audio:
  input_device: 1        # 你的真實麥克風編號
  output_device: 3       # CABLE Input 編號
  loopback_device: 5     # 捕捉遊戲聲音的設備（Stereo Mix 或 VoiceMeeter 輸出）

my_language: "zh"        # 你說的語言
partner_language: "en"   # 對方說的語言
```

### 接收模式音頻來源（loopback_device）

| 方法 | 說明 |
|------|------|
| **Stereo Mix** | 在 Windows 聲音設定 → 錄製 → 右鍵啟用 Stereo Mix |
| **VoiceMeeter** | 安裝 [VoiceMeeter Banana](https://vb-audio.com/Voicemeeter/banana.htm)，將遊戲音頻路由到虛擬輸出 |

## 使用

```bash
# 完整模式（發送 + 接收字幕）
python main.py

# 只發送（你說 → 翻譯 → TTS → 虛擬麥克風）
python main.py --send-only

# 只接收字幕
python main.py --receive-only

# 詳細 log
python main.py -v
```

## OpenRouter 推薦模型

| 模型 | 輸入費用 | 特色 |
|------|----------|------|
| `openai/gpt-4o` | $2.5/1M tokens | 最佳品質 |
| `openai/gpt-4o-mini` | $0.15/1M tokens | 性價比高 |
| `google/gemini-flash-1.5` | $0.075/1M tokens | 最便宜，品質夠用 |
| `anthropic/claude-3-haiku` | $0.25/1M tokens | 快速穩定 |

## 延遲預估（RTX GPU）

| 階段 | 時間 |
|------|------|
| VAD 偵測句尾 | ~700ms 靜音 |
| Whisper large-v3 | ~1–2s |
| OpenRouter 翻譯 | ~0.5–1s |
| Fish Speech TTS | ~1–3s |
| **總延遲** | **~3–7s** |

策略遊戲完全夠用。

## 語言代碼

`my_language` / `partner_language` 使用 ISO 639-1：
`zh` 中文、`en` 英文、`ja` 日文、`ko` 韓文、`de` 德文、`fr` 法文、`es` 西班牙文、`ru` 俄文
