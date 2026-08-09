$ErrorActionPreference = "Stop"

if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    throw "cloudflared is not installed or is not on PATH. Install cloudflared, start VerityGraph locally, then rerun this script."
}

try {
    Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:3000" -TimeoutSec 3 | Out-Null
} catch {
    throw "VerityGraph is not reachable at http://localhost:3000. Run .\scripts\start-local.ps1 first."
}

Write-Host "Opening a temporary Cloudflare Quick Tunnel to the local VerityGraph frontend."
Write-Host "The public URL will be printed below. Keep this terminal open while sharing it."
cloudflared tunnel --url http://localhost:3000
