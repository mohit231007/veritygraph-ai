$ErrorActionPreference = "Stop"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is not installed or is not on PATH. Install Docker Desktop, then rerun this script."
}

docker compose version | Out-Null
Write-Host "Building and starting VerityGraph AI..."
docker compose up -d --build

Write-Host ""
Write-Host "VerityGraph AI is running:"
Write-Host "  App:     http://localhost:3000"
Write-Host "  API:     http://localhost:8000/api/v1/health"
Write-Host "  API docs:http://localhost:8000/docs"
Write-Host ""
Write-Host "Stop without deleting data: docker compose down"
Write-Host "Follow logs:                docker compose logs -f"
