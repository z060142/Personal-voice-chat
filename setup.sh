#!/usr/bin/env bash
# 一鍵安裝 personal-voice-chat 工具鏈（Linux / macOS）
# Windows 用戶請改用：powershell -ExecutionPolicy Bypass -File setup.ps1
# 用法：bash setup.sh
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[ OK ]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
die()   { echo -e "${RED}[ERR ]${NC}  $*" >&2; exit 1; }

# ── 1. 確認 uv ───────────────────────────────────────────────────────
if ! command -v uv &>/dev/null; then
    info "未偵測到 uv，正在安裝..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # shellcheck source=/dev/null
    source "$HOME/.local/bin/env" 2>/dev/null || export PATH="$HOME/.local/bin:$PATH"
fi
ok "uv $(uv --version | awk '{print $2}')"

# ── 2. 建立虛擬環境 ───────────────────────────────────────────────────
info "建立 .venv（Python 3.11）..."
uv venv --python 3.11 --seed
ok "虛擬環境已建立：.venv/"

# ── 3. 安裝所有 Python 依賴（含 CUDA torch）──────────────────────────
info "安裝 Python 依賴（torch + CUDA 121、faster-whisper、silero-vad 等）..."
info "首次安裝約需下載 2~4 GB，請耐心等候..."
uv sync
ok "Python 依賴安裝完成"

# ── 4. 確認 CUDA 可用（非致命）──────────────────────────────────────
info "確認 CUDA 環境..."
if uv run python -c "import torch; assert torch.cuda.is_available(), 'no cuda'" 2>/dev/null; then
    GPU=$(uv run python -c "import torch; print(torch.cuda.get_device_name(0))")
    ok "CUDA 可用：$GPU"
else
    warn "CUDA 不可用或 GPU 驅動未就緒，Whisper 將以 CPU 執行（速度較慢）"
    warn "確認已安裝 NVIDIA 驅動 >= 530 且 CUDA Toolkit >= 12.1"
fi

# ── 5. 提示：Fish Speech 伺服器 ──────────────────────────────────────
echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  Fish Speech TTS 伺服器（需手動安裝）${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"
echo "  Fish Speech 是獨立服務，需另行安裝："
echo "  https://github.com/fishaudio/fish-speech"
echo ""
echo "  建議版本：fish-speech v1.5+"
echo "  啟動後預設監聽 http://127.0.0.1:8080"
echo ""

# ── 6. 提示：首次設定步驟 ────────────────────────────────────────────
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  首次設定步驟${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"
echo "  1. 查詢音訊設備編號："
echo "       uv run python list_devices.py"
echo ""
echo "  2. 編輯 config.yaml，填入："
echo "       audio.input_device    # 真實麥克風"
echo "       audio.output_device   # 虛擬麥克風（如 VB-Audio CABLE Input）"
echo "       audio.loopback_device # 遊戲音效擷取（如 Stereo Mix）"
echo "       translation.openrouter_api_key"
echo "       tts.reference_audio   # 你的聲音樣本 WAV"
echo ""
echo "  3. 驗證設定："
echo "       uv run python main.py --check-config"
echo ""
echo "  4. 啟動翻譯器："
echo "       uv run python main.py"
echo "       uv run python main.py --send-only    # 只測試發送"
echo "       uv run python main.py --receive-only # 只測試接收"
echo ""
ok "安裝完成！請依上方步驟完成設定。"
