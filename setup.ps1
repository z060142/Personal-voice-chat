# setup.ps1 — 一鍵安裝 personal-voice-chat 工具鏈（Windows）
# 用法（在專案目錄下）：
#   powershell -ExecutionPolicy Bypass -File setup.ps1
#
# 需求：Windows 10/11、NVIDIA GPU（CUDA 12.1+）、PowerShell 5.1+

$ErrorActionPreference = "Stop"

function Info($msg)  { Write-Host "[INFO]  $msg" -ForegroundColor Cyan }
function Ok($msg)    { Write-Host "[ OK ]  $msg" -ForegroundColor Green }
function Warn($msg)  { Write-Host "[WARN]  $msg" -ForegroundColor Yellow }
function Die($msg)   { Write-Host "[ERR ]  $msg" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "  personal-voice-chat  Setup" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. 確認 / 安裝 uv ──────────────────────────────────────────────
Info "檢查 uv..."
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Info "未偵測到 uv，正在安裝..."
    powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:PATH = "$env:USERPROFILE\.local\bin;$env:PATH"
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Die "uv 安裝後仍無法執行，請重新開啟 PowerShell 再試一次。"
    }
}
$uvVer = (uv --version) -replace "uv ", ""
Ok "uv $uvVer"

# ── 2. 確認 Python 3.11+ ────────────────────────────────────────────
Info "確認 Python 版本..."
try {
    uv python install 3.11 | Out-Null
} catch {}
Ok "Python 3.11 就緒"

# ── 3. 建立虛擬環境 ─────────────────────────────────────────────────
Info "建立 .venv..."
uv venv --python 3.11 --seed
Ok "虛擬環境已建立：.venv\"

# ── 4. 安裝所有 Python 依賴（含 CUDA torch）────────────────────────
Info "安裝 Python 依賴（首次約需下載 2~4 GB，請耐心等候）..."
Info "包含：torch（CUDA 121）、faster-whisper、silero-vad、sounddevice..."
uv sync
Ok "Python 依賴安裝完成"

# ── 5. 確認 CUDA 可用（非致命）─────────────────────────────────────
Info "確認 CUDA 環境..."
try {
    $gpuName = uv run python -c "import torch; assert torch.cuda.is_available(), 'no cuda'; print(torch.cuda.get_device_name(0))"
    Ok "CUDA 可用：$gpuName"
} catch {
    Warn "CUDA 不可用，Whisper 將以 CPU 執行（速度慢約 5~10 倍）"
    Warn "請確認：NVIDIA 驅動 >= 530、CUDA Toolkit >= 12.1"
}

# ── 6. 提示：Fish Speech 伺服器 ─────────────────────────────────────
Write-Host ""
Write-Host "=================================================" -ForegroundColor Yellow
Write-Host "  Fish Speech TTS 伺服器（需手動安裝）" -ForegroundColor Yellow
Write-Host "=================================================" -ForegroundColor Yellow
Write-Host "  Fish Speech 是獨立 TTS 服務，需另行安裝："
Write-Host "  https://github.com/fishaudio/fish-speech"
Write-Host ""
Write-Host "  建議版本：fish-speech v1.5+"
Write-Host "  啟動後預設監聽 http://127.0.0.1:8080"
Write-Host ""

# ── 7. 提示：Windows 音訊路由 ───────────────────────────────────────
Write-Host "=================================================" -ForegroundColor Yellow
Write-Host "  Windows 音訊路由建議" -ForegroundColor Yellow
Write-Host "=================================================" -ForegroundColor Yellow
Write-Host "  推薦安裝 VB-Audio Virtual Cable（免費）："
Write-Host "  https://vb-audio.com/Cable/"
Write-Host ""
Write-Host "  設備對應："
Write-Host "    input_device    = 你的真實麥克風"
Write-Host "    output_device   = CABLE Input（VB-Audio 虛擬麥克風輸出端）"
Write-Host "    loopback_device = 遊戲/Discord 聲音的擷取來源"
Write-Host "                      （Stereo Mix、或 VoiceMeeter Output）"
Write-Host ""

# ── 8. 首次設定步驟 ─────────────────────────────────────────────────
Write-Host "=================================================" -ForegroundColor Yellow
Write-Host "  首次設定步驟" -ForegroundColor Yellow
Write-Host "=================================================" -ForegroundColor Yellow
Write-Host "  1. 查詢音訊設備編號："
Write-Host "       uv run python list_devices.py"
Write-Host ""
Write-Host "  2. 編輯 config.yaml，填入設備編號、API key、reference audio 路徑"
Write-Host ""
Write-Host "  3. 驗證設定："
Write-Host "       uv run python main.py --check-config"
Write-Host ""
Write-Host "  4. 測試發送（只跑發送管道）："
Write-Host "       uv run python main.py --send-only"
Write-Host ""
Write-Host "  5. 正式啟動："
Write-Host "       uv run python main.py"
Write-Host ""

Ok "安裝完成！請依上方步驟完成設定。"
