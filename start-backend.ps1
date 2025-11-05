# 启动后端服务
Write-Host "`n启动后端服务..." -ForegroundColor Green

cd backend

# 检查虚拟环境
if (-not (Test-Path "venv")) {
    Write-Host "× 未找到虚拟环境!" -ForegroundColor Red
    Write-Host "请先运行: python -m venv venv" -ForegroundColor Yellow
    Write-Host "然后安装依赖: .\venv\Scripts\pip.exe install -r requirements.txt`n" -ForegroundColor Yellow
    pause
    exit 1
}

# 检查并初始化数据库
if (-not (Test-Path "ai_polish.db")) {
    Write-Host "首次运行，数据库将在服务启动时自动创建..." -ForegroundColor Cyan
}

# 启动后端
Write-Host "服务地址: http://localhost:8000" -ForegroundColor Cyan
Write-Host "API 文档: http://localhost:8000/docs`n" -ForegroundColor Cyan
.\venv\Scripts\python3.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
