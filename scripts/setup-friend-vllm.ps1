# Friend's GPU PC — vLLM setup helper (Windows + WSL2)
# Transfer this file via UltraViewer file transfer, then run in PowerShell.
# See docs/runbooks/friend-pc-vllm-setup.md for the full walkthrough.

Write-Host "=== Step 1: Check NVIDIA GPU ===" -ForegroundColor Cyan
nvidia-smi
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: nvidia-smi failed. This PC needs an NVIDIA GPU." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Step 2: Check WSL ===" -ForegroundColor Cyan
wsl --status 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "WSL not installed. Run as Administrator:" -ForegroundColor Yellow
    Write-Host "  wsl --install -d Ubuntu"
    Write-Host "Then reboot and run this script again."
    exit 1
}

Write-Host ""
Write-Host "=== Step 3: Install vLLM inside Ubuntu (takes 10-20 min) ===" -ForegroundColor Cyan
$installScript = @'
set -e
sudo apt update
sudo apt install -y python3.12-venv python3-pip git curl
python3.12 -m venv ~/vllm-env
source ~/vllm-env/bin/activate
pip install --upgrade pip
pip install vllm huggingface_hub
echo "INSTALL_OK"
'@
wsl bash -lc $installScript

Write-Host ""
Write-Host "=== Step 4: Next steps (manual) ===" -ForegroundColor Green
Write-Host "1. Open Ubuntu terminal"
Write-Host "2. Run:  source ~/vllm-env/bin/activate"
Write-Host "3. Run:  huggingface-cli login"
Write-Host "4. Run the vllm serve command from docs/runbooks/friend-pc-vllm-setup.md"
Write-Host ""
Write-Host "=== Friend's LAN IP (give this to your dev machine) ===" -ForegroundColor Cyan
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch 'Loopback' } | Select-Object IPAddress, InterfaceAlias
