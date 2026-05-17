<#
.SYNOPSIS
  BOSS直聘技能 Python 运行包装器
  自动设置 PYTHONIOENCODING=utf-8 解决 PowerShell 中文乱码问题

.DESCRIPTION
  用法：.\run.ps1 <python脚本路径> [参数...]
  示例：.\run.ps1 scripts\scrape_all.py --keyword 用户研究 --city 杭州 --pages 3
        .\run.ps1 scripts\push_daily.py --city 杭州 --keyword 用户研究
        .\run.ps1 scripts\generate_report.py --city 杭州 --keyword 用户研究

  不传参数时，列出可用脚本。
#>

# 自动定位到技能根目录
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

# 如果没有参数，显示帮助
if ($args.Count -eq 0) {
    Write-Host "📋 可用脚本：" -ForegroundColor Cyan
    Get-ChildItem scripts\*.py | ForEach-Object {
        Write-Host "  .\run.ps1 $($_.Name)  [参数...]" -ForegroundColor Yellow
    }
    Write-Host ""
    Write-Host "示例：" -ForegroundColor Cyan
    Write-Host "  .\run.ps1 scripts\scrape_all.py --keyword 用户研究 --city 杭州 --pages 3"
    Write-Host "  .\run.ps1 scripts\push_daily.py --city 杭州 --keyword 用户研究"
    Write-Host "  .\run.ps1 scripts\generate_report.py --city 杭州 --keyword 用户研究"
    exit 0
}

# 检查 .venv
$VenvPython = Join-Path $ScriptDir ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "❌ 未找到 .venv\Scripts\python.exe，请先运行 uv sync" -ForegroundColor Red
    exit 1
}

# 设置编码 + UTF8 模式 + 无缓冲
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$env:PYTHONUNBUFFERED = '1'

# 执行
$FullArgs = @($args[0])
if ($args.Count -gt 1) {
    $FullArgs += $args[1..($args.Count-1)]
}

Write-Host "▶ 运行: $($args[0])" -ForegroundColor Green
Write-Host "   CWD: $ScriptDir" -ForegroundColor DarkGray

& $VenvPython $FullArgs
$ExitCode = $LASTEXITCODE

if ($ExitCode -ne 0) {
    Write-Host "❌ 退出码: $ExitCode" -ForegroundColor Red
} else {
    Write-Host "✅ 完成" -ForegroundColor Green
}

exit $ExitCode
