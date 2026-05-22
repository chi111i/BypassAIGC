# AI 学术写作助手 - Windows 构建脚本
# 用于在 Windows 上构建可执行文件

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "AI 学术写作助手 - Windows 构建脚本" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# 检查 Python
Write-Host ""
Write-Host "1. 检查 Python 环境..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host $pythonVersion -ForegroundColor Green
} catch {
    Write-Host "错误: 未找到 Python，请先安装 Python 3.9+（构建 exe 推荐 3.12+）" -ForegroundColor Red
    exit 1
}

# 检查 Node.js
Write-Host ""
Write-Host "2. 检查 Node.js 环境..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version 2>&1
    Write-Host $nodeVersion -ForegroundColor Green
} catch {
    Write-Host "错误: 未找到 Node.js，请先安装 Node.js 18+" -ForegroundColor Red
    exit 1
}

# 创建虚拟环境并安装依赖
Write-Host ""
Write-Host "3. 安装后端依赖..." -ForegroundColor Yellow
if (-not (Test-Path "venv")) {
    python -m venv venv
}
& .\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 构建前端
Write-Host ""
Write-Host "4. 构建前端..." -ForegroundColor Yellow
Set-Location frontend
npm install
npm run build
Set-Location ..

# 复制前端构建产物
Write-Host ""
Write-Host "5. 复制前端构建产物..." -ForegroundColor Yellow
if (Test-Path "static") {
    Remove-Item -Recurse -Force static
}
Copy-Item -Recurse frontend\dist static

# 使用 PyInstaller 打包
Write-Host ""
Write-Host "6. 使用 PyInstaller 打包..." -ForegroundColor Yellow
pyinstaller app.spec --clean

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "构建完成!" -ForegroundColor Green
Write-Host "可执行文件位置: dist\AI学术写作助手.exe" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "运行方式:" -ForegroundColor Yellow
Write-Host "1. 将 dist\AI学术写作助手.exe 复制到任意目录"
Write-Host "2. 首次运行会自动创建 .env 配置文件"
Write-Host "3. 编辑 .env 文件，填入 API Key 等配置"
Write-Host "4. 再次运行程序，将自动打开浏览器"
Write-Host ""
