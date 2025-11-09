# ========================================
#  ITA Trading Agent - Project Setup
#  Версия 1.3 (GPT-5 инженерная сборка)
# ========================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   ITA Trading Agent - Project Setup   " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ------------------------------------------------------------
# 1. Проверка Python версии
# ------------------------------------------------------------
Write-Host "Checking Python version..." -ForegroundColor Yellow
$pythonVersion = python --version
Write-Host $pythonVersion -ForegroundColor Green

if ($pythonVersion -notmatch "3.11") {
    Write-Host "WARNING: Expected Python 3.11.x, but found: $pythonVersion" -ForegroundColor Red
    $continue = Read-Host "Continue anyway? (y/n)"
    if ($continue -ne "y") { exit }
}

# ------------------------------------------------------------
# 2. Проверка виртуального окружения
# ------------------------------------------------------------
Write-Host "`nChecking virtual environment..." -ForegroundColor Yellow
if (Test-Path ".\venv\Scripts\python.exe") {
    Write-Host "Virtual environment found!" -ForegroundColor Green
} else {
    Write-Host "ERROR: venv not found at .\venv\Scripts\python.exe" -ForegroundColor Red
    Write-Host "Please create it first: python -m venv venv" -ForegroundColor Yellow
    exit
}

# ------------------------------------------------------------
# 3. Активация venv и проверка пути
# ------------------------------------------------------------
Write-Host "`nActivating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

$pythonPath = (Get-Command python).Source
if ($pythonPath -notmatch "ITA_01\\venv\\Scripts\\python.exe") {
    Write-Host "ERROR: Virtual environment points to wrong path!" -ForegroundColor Red
    Write-Host "Please recreate venv: python -m venv venv" -ForegroundColor Yellow
    exit
}

# ------------------------------------------------------------
# 4. Обновление pip
# ------------------------------------------------------------
Write-Host "`nUpgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

# ------------------------------------------------------------
# 5. Проверка структуры проекта
# ------------------------------------------------------------
Write-Host "`nChecking project folder structure..." -ForegroundColor Yellow
$folders = @(
    "data/archive/raw",
    "data/cache",
    "logs/coredata",
    "src/02_CoreData"
)
foreach ($f in $folders) {
    if (-not (Test-Path $f)) {
        New-Item -ItemType Directory -Force -Path $f | Out-Null
        Write-Host "Created folder: $f" -ForegroundColor DarkGray
    }
}
Write-Host "✅ Folder structure verified." -ForegroundColor Green

# ------------------------------------------------------------
# 6. Проверка config.yaml
# ------------------------------------------------------------
if (-not (Test-Path "config.yaml")) {
    @"
coredata:
  mt5:
    use_env_credentials: true
    timezone: "UTC"

  storage:
    archive_path: "data/archive/raw"
    cache_path: "data/cache"

logging:
  level: "INFO"
  path: "logs/coredata/mt5_connector.log"
"@ | Out-File "config.yaml" -Encoding utf8
    Write-Host "✅ config.yaml created with default structure." -ForegroundColor Green
} else {
    Write-Host "config.yaml already exists." -ForegroundColor Green
}

# ------------------------------------------------------------
# 7. Проверка .env и .env.example
# ------------------------------------------------------------
Write-Host "`nChecking .env file..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Write-Host ".env file not found!" -ForegroundColor Red
    if (Test-Path ".env.example") {
        Write-Host "Creating .env from .env.example..." -ForegroundColor Yellow
        Copy-Item ".env.example" ".env"
        Write-Host "✅ .env created. Please edit it with your credentials!" -ForegroundColor Yellow
    } else {
        @"
# Example .env for ITA CoreData / MT5 Connector
MT5_LOGIN=12345678
MT5_PASSWORD=your_password_here
MT5_SERVER=MetaQuotes-Demo
MT5_PATH="C:\Program Files\MetaTrader 5\terminal64.exe"
"@ | Out-File ".env.example" -Encoding utf8
        Copy-Item ".env.example" ".env"
        Write-Host "✅ .env.example and .env created with default fields." -ForegroundColor Green
    }
} else {
    Write-Host ".env file exists!" -ForegroundColor Green
}

# ------------------------------------------------------------
# 8. Установка зависимостей
# ------------------------------------------------------------
Write-Host "`nInstalling dependencies from requirements.txt..." -ForegroundColor Yellow
if (-not (Test-Path "requirements.txt")) {
    Write-Host "ERROR: requirements.txt not found! Please add your project dependencies." -ForegroundColor Red
    exit
}

pip install -r requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host "`nERROR: Failed to install dependencies!" -ForegroundColor Red
    exit
}

# ------------------------------------------------------------
# 9. Проверка Prefect
# ------------------------------------------------------------
Write-Host "`nVerifying Prefect installation..." -ForegroundColor Yellow
if (-not (Get-Command prefect -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Prefect..." -ForegroundColor Yellow
    pip install prefect==2.19.9
}
$prefectVersion = prefect version
Write-Host $prefectVersion -ForegroundColor Green

# ------------------------------------------------------------
# 10. Настройка Prefect API и HOME
# ------------------------------------------------------------
Write-Host "`nConfiguring Prefect..." -ForegroundColor Yellow
# 1️⃣ Создание и установка PREFECT_HOME
$prefectHome = "D:\ITA\ITA_01\.prefect"
if (-not (Test-Path $prefectHome)) {
    New-Item -ItemType Directory -Force -Path $prefectHome | Out-Null
    Write-Host "Created Prefect directory: $prefectHome" -ForegroundColor Green
}

# Устанавливаем переменную окружения PREFECT_HOME (глобально для пользователя)
Write-Host "Setting PREFECT_HOME system variable..." -ForegroundColor Yellow
setx PREFECT_HOME $prefectHome | Out-Null

# Добавляем переменную в текущую PowerShell-сессию
$env:PREFECT_HOME = $prefectHome
Write-Host "PREFECT_HOME set to: $env:PREFECT_HOME" -ForegroundColor Green

# 2️⃣ Настраиваем Prefect API URL
prefect config set PREFECT_API_URL="http://127.0.0.1:4200/api"
Write-Host "Prefect API configured!" -ForegroundColor Green

# 3️⃣ Создание папки для ChromaDB (векторная память)
$chromaPath = "D:\ITA\ITA_01\.chromadb"
if (-not (Test-Path $chromaPath)) {
    New-Item -ItemType Directory -Force -Path $chromaPath | Out-Null
    Write-Host "Created ChromaDB directory: $chromaPath" -ForegroundColor Green
}
Write-Host "✅ Prefect configured!" -ForegroundColor Green

# ==============================================
# 🔒 Lock dependencies for consistent versions
# ==============================================
Write-Host "`nLocking and verifying package versions..." -ForegroundColor Yellow

$lockFile = "requirements.lock"
$reqFile = "requirements.txt"

# Проверка, есть ли lock-файл
if (-not (Test-Path $lockFile)) {
    Write-Host "Lock file not found. Creating new requirements.lock..." -ForegroundColor Yellow
    pip freeze > $lockFile
    Write-Host "✅ Lock file created and saved as requirements.lock" -ForegroundColor Green
} else {
    Write-Host "Comparing installed packages with requirements.lock..." -ForegroundColor Yellow
    $installed = pip freeze
    $locked = Get-Content $lockFile
    $differences = Compare-Object -ReferenceObject $locked -DifferenceObject $installed

    if ($differences) {
        Write-Host "⚠️  Version mismatch detected!" -ForegroundColor Red
        $differences | ForEach-Object { Write-Host $_ -ForegroundColor Red }

        $choice = Read-Host "Do you want to re-sync environment to match lock file? (y/n)"
        if ($choice -eq "y") {
            Write-Host "Reinstalling from lock file..." -ForegroundColor Yellow
            pip install -r $lockFile
            Write-Host "✅ Environment synced with lock file" -ForegroundColor Green
        } else {
            Write-Host "Skipping re-sync. Be aware of potential version drift." -ForegroundColor Yellow
        }
    } else {
        Write-Host "✅ All packages match requirements.lock" -ForegroundColor Green
    }
}

# ------------------------------------------------------------
# 11. Финальная проверка
# ------------------------------------------------------------
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "   Setup Complete! Final Check:         " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n✅ Python version:" -ForegroundColor Green
python --version

Write-Host "`n✅ Prefect version:" -ForegroundColor Green
prefect version | Select-String "Version"

Write-Host "`n✅ Key packages installed:" -ForegroundColor Green
pip list | Select-String "prefect|MetaTrader5|loguru|pandas|PyYAML"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Edit .env file with your credentials (if not done yet)" -ForegroundColor White
Write-Host "2. Start Prefect server: prefect server start" -ForegroundColor White
Write-Host "3. Open Prefect UI: http://localhost:4200" -ForegroundColor White
Write-Host "4. Run your first flow from /flows directory" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
