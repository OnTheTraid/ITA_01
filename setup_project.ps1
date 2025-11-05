# setup_project.ps1
# Скрипт автоматической настройки проекта для всех разработчиков

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   ITA Trading Agent - Project Setup   " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Проверка Python версии
Write-Host "Checking Python version..." -ForegroundColor Yellow
$pythonVersion = python --version
Write-Host $pythonVersion -ForegroundColor Green

if ($pythonVersion -notmatch "3.11") {
    Write-Host "WARNING: Expected Python 3.11.x, but found: $pythonVersion" -ForegroundColor Red
    $continue = Read-Host "Continue anyway? (y/n)"
    if ($continue -ne "y") { exit }
}

# Проверка виртуального окружения
Write-Host "`nChecking virtual environment..." -ForegroundColor Yellow
if (Test-Path ".\venv\Scripts\python.exe") {
    Write-Host "Virtual environment found!" -ForegroundColor Green
} else {
    Write-Host "ERROR: venv not found at .\venv\Scripts\python.exe" -ForegroundColor Red
    Write-Host "Please create it first: python -m venv venv" -ForegroundColor Yellow
    exit
}

# Активация venv
Write-Host "`nActivating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

# Обновление pip
Write-Host "`nUpgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

# Установка зависимостей
Write-Host "`nInstalling dependencies from requirements.txt..." -ForegroundColor Yellow
if (-not (Test-Path "requirements.txt")) {
    Write-Host "ERROR: requirements.txt not found!" -ForegroundColor Red
    exit
}

pip install -r requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host "`nERROR: Failed to install dependencies!" -ForegroundColor Red
    exit
}

# Проверка Prefect
Write-Host "`nVerifying Prefect installation..." -ForegroundColor Yellow
$prefectVersion = prefect version
Write-Host $prefectVersion -ForegroundColor Green

# Проверка .env файла
Write-Host "`nChecking .env file..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Write-Host "WARNING: .env file not found!" -ForegroundColor Red
    if (Test-Path ".env.example") {
        Write-Host "Creating .env from .env.example..." -ForegroundColor Yellow
        Copy-Item ".env.example" ".env"
        Write-Host "✅ .env created. Please edit it with your credentials!" -ForegroundColor Yellow
    } else {
        Write-Host "ERROR: .env.example not found! Cannot create .env" -ForegroundColor Red
    }
} else {
    Write-Host ".env file exists!" -ForegroundColor Green
}

# Настройка Prefect
Write-Host "`nConfiguring Prefect..." -ForegroundColor Yellow
prefect config set PREFECT_API_URL="http://127.0.0.1:4200/api"
prefect config set PREFECT_HOME=".prefect"
Write-Host "Prefect configured!" -ForegroundColor Green

# Финальная проверка
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "   Setup Complete! Final Check:         " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n✅ Python version:" -ForegroundColor Green
python --version

Write-Host "`n✅ Prefect version:" -ForegroundColor Green
prefect version | Select-String "Version"

Write-Host "`n✅ Key packages installed:" -ForegroundColor Green
pip list | Select-String "prefect|langchain|chromadb|MetaTrader5|openai"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Edit .env file with your credentials (if not done yet)" -ForegroundColor White
Write-Host "2. Start Prefect server: prefect server start" -ForegroundColor White
Write-Host "3. Open Prefect UI: http://localhost:4200" -ForegroundColor White
Write-Host "4. Run your first flow from /flows directory" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan