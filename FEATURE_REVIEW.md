# Feature Review：遊戲語音翻譯方案

本文件依據原始需求「聊天語音 → STT → 翻譯」與「我口說 → 翻譯 → TTS → 發送語音」，針對目前專案實作做功能審查。

## 1. 需求符合度總結

| 原始需求 | 目前狀態 | 評估 |
| --- | --- | --- |
| 接收外國網友語音並轉字幕 | 已覆蓋 | `ReceivePipeline` 會從 loopback 裝置擷取語音，經 VAD、Whisper STT、翻譯後更新字幕。 |
| 自己口說後翻譯成對方語言 | 已覆蓋 | `SendPipeline` 會擷取麥克風音訊，經 VAD/PTT、Whisper STT、翻譯後送進 TTS。 |
| TTS 後以語音送進 Discord / 遊戲 | 已覆蓋 | TTS 產生音訊後會播放到設定的輸出裝置，README 建議使用 VB-Audio Virtual Cable。 |
| 可自訂音色 | 已覆蓋但依賴外部服務 | `FishSpeechTTS` 以 reference audio 做音色複製；品質與 API schema 取決於本機 Fish Speech server。 |
| 不追求低延遲，戰略遊戲可接受 | 基本符合 | README 的架構與 VAD silence 設定偏向句子級翻譯，適合策略遊戲而非 FPS callout。 |
| 願意付 API 費用 | 已覆蓋 | 翻譯走 OpenRouter / OpenAI-compatible API；STT/TTS 主要走本機算力。 |

結論：目前架構方向正確，已是一個可驗證 MVP。最大的風險不在核心流程，而在音訊路由、裝置設定、TTS server API 相容性、回音/串音，以及錯誤復原與可觀測性。

## 2. 目前架構亮點

### 2.1 發送與接收管道分離清楚

專案把「我說話 → 翻譯 → TTS → 虛擬麥克風」與「對方語音 → 翻譯 → 字幕」拆成 `SendPipeline` 與 `ReceivePipeline`，日後要單獨調整任一路徑很方便。

### 2.2 符合遊戲情境的互動控制

發送端同時支援 VAD 與 PTT：

- VAD 模式適合免按鍵聊天。
- PTT 模式可避免遊戲背景聲、鍵盤聲或自言自語被送出去。
- 暫停快捷鍵可快速避免誤送。

### 2.3 自訂音色方案合理

使用 Fish Speech reference audio 走本機 TTS，符合「願意負擔本機 STT/TTS 開銷、想自訂音色」的需求。相比純雲端 TTS，這個方向也比較容易微調音色與避免每次合成都付費。

### 2.4 共享 STT 模型節省 VRAM

`WhisperSTT` 用同一個 Whisper model 給 send / receive 共用，並用 lock 保護並行 transcribe。這可降低 GPU 記憶體壓力，對單機使用很實際。

## 3. 主要風險與改善建議

### 3.1 高優先級：音訊路由需要更明確的驗證流程

目前 README 有說明使用 VB-Audio Virtual Cable / Stereo Mix / VoiceMeeter，但新使用者最常卡在「Discord 到底要選 CABLE Input 還是 CABLE Output」、「遊戲聲音是否被 loopback 錄到」、「TTS 是否又被接收管道收進去」這些問題。

建議新增一個 setup checklist：

1. `python list_devices.py` 確認三個裝置：真實麥克風、虛擬麥克風輸出、loopback。
2. 用 `--send-only` 驗證自己說話是否會變成 TTS 並進入 Discord 麥克風。
3. 用 `--receive-only` 驗證對方語音是否只出現在字幕，不會收進自己的 TTS。
4. 若使用 VoiceMeeter，明確分離「遊戲/Discord 輸出」與「TTS 虛擬麥克風輸出」。

### 3.2 高優先級：TTS 播放期間只暫停發送端錄音，仍可能污染接收端

`SendPipeline` 會在 TTS 播放時暫停自己的麥克風錄音，避免把自己的 TTS 再送進發送管道。但如果 loopback 裝置同時收得到 TTS 播放音，`ReceivePipeline` 仍可能把自己的 TTS 當成對方語音辨識並翻譯到字幕。

建議：

- 在文件中要求 TTS output device 不要進入 loopback capture mix。
- 或新增全域 playback state，讓 `ReceivePipeline` 在 TTS 播放時短暫忽略音訊。
- 更好的做法是讓 send / receive audio devices 明確分到不同 virtual bus。

### 3.3 高優先級：OpenRouter API key 缺失時錯誤訊息不夠友善

目前 `Translator` 在沒有 API key 時會讀環境變數。如果 config 與環境變數都沒有設定，會丟出 KeyError 或初始化錯誤。對 MVP 來說可接受，但第一次設定時會不直覺。

建議在 `build_services` 或 `Translator.__init__` 明確檢查 key，並提示：

- 設定 `OPENROUTER_API_KEY`
- 或填入 `config.yaml` 的 `translation.openrouter_api_key`

### 3.4 中優先級：Fish Speech HTTP API schema 需鎖版本或提供相容層

`FishSpeechTTS` 目前假設 `/v1/tts` 接受 `references`、`format`、`streaming` 欄位且回傳 WAV bytes。若 Fish Speech server 版本不同，可能會因 schema 改動失敗。

建議：

- README 標註測試過的 Fish Speech 版本 / commit。
- `tts_client.py` 增加 health check 或在錯誤時輸出 response body。
- config 允許切換 endpoint path 或 payload mode。

### 3.5 中優先級：缺少錄音片段與翻譯結果的 debug 落盤選項

語音翻譯系統的問題很常發生在音訊輸入品質：音量太低、噪音太多、設備選錯、取樣率不符。現在 log 有 STT 與翻譯文字，但沒有保存原始 utterance。

建議加入 debug config：

```yaml
debug:
  save_utterances: false
  output_dir: "debug_audio"
```

啟用時保存 send / receive 的 WAV、STT text、translated text，方便排查錯誤。

### 3.6 中優先級：字幕 UI 可以增加原文顯示

目前字幕只顯示翻譯結果。遊戲語音中常有專有名詞或 map / unit 名稱，STT 可能聽錯。若字幕 UI 顯示原文與譯文，除錯與實戰理解都會更好。

建議格式：

- 對方原文：`[en] push left now`
- 對方譯文：`對方：現在推左邊`
- 自己原文：`我原文：...`
- 自己送出：`你：...`

### 3.7 低優先級：翻譯模型與費用資訊容易過期

README 目前包含模型建議與價格。這類資訊會隨 OpenRouter 與模型供應商調整而變動。

建議改成：

- 文件保留「推薦類型」：高品質 / 低成本 / 低延遲。
- 實際價格連到 OpenRouter 模型頁，由使用者確認最新費率。
- config 預設使用性價比模型，避免初次使用者成本過高。

## 4. 建議的下一步 Roadmap

### Phase 1：讓 MVP 更容易跑起來

- 增加 API key 缺失的友善錯誤。
- README 新增音訊路由 checklist。
- TTS error log 顯示 HTTP response body。
- 增加 `--dry-run-config` 或 `python main.py --check-config`，檢查設備、reference audio、API key、Fish Speech server。

### Phase 2：提升實戰穩定度

- 加入 debug utterance 保存。
- 加入 send / receive queue size 上限，避免網路或 TTS 卡住時累積太多舊句子。
- 在 TTS 播放期間讓 receive 端可選擇暫停辨識。
- 字幕同時顯示原文與譯文。

### Phase 3：體驗優化

- 新增簡易 tray / GUI 設定頁。
- 支援多個常用語言 preset。
- 支援不同 TTS backend：Fish Speech、本機 XTTS、雲端 TTS。
- 支援每個遊戲配置不同 prompt，例如 RTS、MMO、MOBA 的術語不同。

## 5. Review 判定

目前功能已符合原始需求，適合進入「裝置設定與端到端測試」階段。建議先不要急著大改核心 STT / 翻譯 / TTS，而是優先補上設定驗證、音訊路由文件、錯誤訊息與 debug tooling。這些改善會比更換模型更能提升可用性。
