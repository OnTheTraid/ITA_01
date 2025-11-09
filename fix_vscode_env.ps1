@'
# --- Автоматическая очистка и настройка VS Code для окружения ITA_01 ---

$projectDir = "D:\ITA"
$vscodeSettingsDir = Join-Path $projectDir ".vscode"
$vscodeSettingsFile = Join-Path $vscodeSettingsDir "settings.json"
$pythonPath = "D:\\ITA\\ITA_01\\Scripts\\python.exe"
$activatePath = "D:\\ITA\\ITA_01\\Scripts\\Activate.ps1"

# Создаём папку .vscode если её нет
if (-Not (Test-Path $vscodeSettingsDir)) {
    New-Item -ItemType Directory -Force -Path $vscodeSettingsDir | Out-Null
}

# Удаляем старый settings.json, если там мусор
if (Test-Path $vscodeSettingsFile) {
    Remove-Item $vscodeSettingsFile -Force
    Write-Host "🧹 Старый settings.json удалён."
}

# Новые чистые настройки VS Code
$settings = @{
    "python.defaultInterpreterPath" = $pythonPath
    "terminal.integrated.shellArgs.windows" = @("-ExecutionPolicy", "Bypass")
    "terminal.integrated.profiles.windows" = @{
        "PowerShell" = @{
            "source" = "PowerShell"
            "args" = @(
                "-NoExit",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                "& '$activatePath'"
            )
        }
    }
    "terminal.integrated.defaultProfile.windows" = "PowerShell"
}

# Сохраняем в JSON
$settings | ConvertTo-Json -Depth 6 | Out-File -Encoding UTF8 $vscodeSettingsFile -Force

Write-Host ""
Write-Host "✅ VS Code полностью перенастроен!"
Write-Host "🔹 Окружение: $pythonPath"
Write-Host "🔹 Активация: автоматическая при запуске VS Code"
Write-Host ""
Write-Host "💡 Теперь перезапусти VS Code — терминал откроется с (ITA_01)."
'@ | Out-File -Encoding ASCII D:\ITA\fix_vscode_env.ps1
