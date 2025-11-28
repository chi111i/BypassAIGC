# ========================================
# AI 学术写作助手 - 统一启动脚本 (Windows)
# ========================================

# 确保使用PowerShell 7+或兼容模式，避免Terminal-Icons模块问题
# 使用 -NoProfile 避免加载可能不兼容的配置文件

param(
    [Parameter(Mandatory=$false)]
    [int]$Option
)

# 颜色函数
function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

# 显示菜单
function Show-Menu {
    Clear-Host
    Write-ColorOutput "`n========================================" "Cyan"
    Write-ColorOutput "   AI 学术写作助手 - 统一管理脚本" "Cyan"
    Write-ColorOutput "========================================`n" "Cyan"
    
    Write-ColorOutput "请选择要执行的操作:`n" "Yellow"
    
    Write-ColorOutput "  1. 环境安装配置" "White"
    Write-ColorOutput "     (首次使用或需要重新配置时选择)" "DarkGray"
    
    Write-ColorOutput "`n  2. 启动所有服务" "White"
    Write-ColorOutput "     (同时启动前端和后端服务)" "DarkGray"
    
    Write-ColorOutput "`n  3. 仅启动后端服务" "White"
    Write-ColorOutput "     (启动 FastAPI 后端 - 端口 8000)" "DarkGray"
    
    Write-ColorOutput "`n  4. 仅启动前端服务" "White"
    Write-ColorOutput "     (启动 React 前端 - 端口 3000)" "DarkGray"
    
    Write-ColorOutput "`n  5. 停止所有服务" "White"
    Write-ColorOutput "     (停止所有正在运行的前后端服务)" "DarkGray"
    
    Write-ColorOutput "`n  6. 验证安装" "White"
    Write-ColorOutput "     (检查环境配置和依赖安装情况)" "DarkGray"
    
    Write-ColorOutput "`n  7. 验证数据库" "White"
    Write-ColorOutput "     (检查数据库配置和连接状态)" "DarkGray"
    
    Write-ColorOutput "`n  0. 退出" "White"
    
    Write-ColorOutput "`n========================================" "Cyan"
    Write-ColorOutput "输入选项编号: " "Yellow" -NoNewline
}

# 1. 环境安装配置
function Setup-Environment {
    Write-ColorOutput "`n========================================" "Cyan"
    Write-ColorOutput "开始环境配置..." "Cyan"
    Write-ColorOutput "========================================`n" "Cyan"
    
    # 检查 Python
    Write-ColorOutput "[1/5] 检查 Python..." "Yellow"
    try {
        $pythonVersion = python --version 2>&1
        if ($pythonVersion -match "python (\d+)\.(\d+)") {
            $major = [int]$matches[1]
            $minor = [int]$matches[2]
            if ($major -ge 3 -and $minor -ge 10) {
                Write-ColorOutput "✓ $pythonVersion" "Green"
            } else {
                Write-ColorOutput "× python 版本需要 3.10 或更高，当前: $pythonVersion" "Red"
                Write-ColorOutput "请从 https://www.python.org/downloads/ 下载安装" "Yellow"
                pause
                return
            }
        }
    } catch {
        Write-ColorOutput "× python 未安装" "Red"
        Write-ColorOutput "请从 https://www.python.org/downloads/ 下载安装" "Yellow"
        pause
        return
    }
    
    # 检查 Node.js
    Write-ColorOutput "`n[2/5] 检查 Node.js..." "Yellow"
    try {
        $nodeVersion = node --version 2>&1
        if ($nodeVersion -match "v(\d+)") {
            $major = [int]$matches[1]
            if ($major -ge 16) {
                Write-ColorOutput "✓ Node.js $nodeVersion" "Green"
            } else {
                Write-ColorOutput "× Node.js 版本需要 16 或更高，当前: $nodeVersion" "Red"
                Write-ColorOutput "请从 https://nodejs.org/ 下载安装" "Yellow"
                pause
                return
            }
        }
    } catch {
        Write-ColorOutput "× Node.js 未安装" "Red"
        Write-ColorOutput "请从 https://nodejs.org/ 下载安装" "Yellow"
        pause
        return
    }
    
    # 创建后端虚拟环境
    Write-ColorOutput "`n[3/5] 配置后端环境..." "Yellow"
    if (-not (Test-Path "backend\venv")) {
        Write-ColorOutput "创建 python 虚拟环境..." "Cyan"
        python -m venv backend\venv
        if ($LASTEXITCODE -ne 0) {
            Write-ColorOutput "× 创建虚拟环境失败" "Red"
            pause
            return
        }
    } else {
        Write-ColorOutput "虚拟环境已存在" "Cyan"
    }
    
    Write-ColorOutput "安装后端依赖..." "Cyan"
    & backend\venv\Scripts\pip.exe install -r backend\requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-ColorOutput "× 安装后端依赖失败" "Red"
        pause
        return
    }
    Write-ColorOutput "✓ 后端环境配置完成" "Green"
    
    # 安装前端依赖
    Write-ColorOutput "`n[4/5] 配置前端环境..." "Yellow"
    Push-Location frontend
    if (-not (Test-Path "node_modules")) {
        Write-ColorOutput "安装前端依赖（这可能需要几分钟）..." "Cyan"
        npm install
        if ($LASTEXITCODE -ne 0) {
            Pop-Location
            Write-ColorOutput "× 安装前端依赖失败" "Red"
            pause
            return
        }
    } else {
        Write-ColorOutput "前端依赖已安装" "Cyan"
    }
    Pop-Location
    Write-ColorOutput "✓ 前端环境配置完成" "Green"
    
    # 生成配置文件
    Write-ColorOutput "`n[5/5] 配置文件..." "Yellow"
    if (-not (Test-Path "backend\.env")) {
        Write-ColorOutput "生成默认配置文件..." "Cyan"
        $envContent = @"
# 数据库配置
DATABASE_URL=sqlite:///./ai_polish.db

# Redis 配置
REDIS_URL=redis://localhost:6379/0

# OpenAI API 配置
OPENAI_API_KEY=your-api-key-here
OPENAI_BASE_URL=http://IP:PORT/v1

# 第一阶段模型配置 (论文润色) - 推荐使用 gemini-2.5-pro
POLISH_MODEL=gemini-2.5-pro
POLISH_API_KEY=your-api-key-here
POLISH_BASE_URL=http://IP:PORT/v1

# 第二阶段模型配置 (原创性增强) - 推荐使用 gemini-2.5-pro
ENHANCE_MODEL=gemini-2.5-pro
ENHANCE_API_KEY=your-api-key-here
ENHANCE_BASE_URL=http://IP:PORT/v1

# 感情文章润色模型配置 - 推荐使用 gemini-2.5-pro
EMOTION_MODEL=gemini-2.5-pro
EMOTION_API_KEY=your-api-key-here
EMOTION_BASE_URL=http://IP:PORT/v1

# 并发配置
MAX_CONCURRENT_USERS=5

# 会话压缩配置
HISTORY_COMPRESSION_THRESHOLD=2000
COMPRESSION_MODEL=gemini-2.5-pro
COMPRESSION_API_KEY=your-api-key-here
COMPRESSION_BASE_URL=http://IP:PORT/v1

# JWT 密钥（请修改为随机字符串）
SECRET_KEY=your-secret-key-change-this-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# 管理员账户（生产环境请修改密码）
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
DEFAULT_USAGE_LIMIT=1
SEGMENT_SKIP_THRESHOLD=15
"@
        Set-Content -Path "backend\.env" -Value $envContent
        Write-ColorOutput "✓ 配置文件已生成: backend\.env" "Green"
        Write-ColorOutput "⚠ 请编辑 backend\.env 填入您的 API 密钥" "Yellow"
    } else {
        Write-ColorOutput "✓ 配置文件已存在: backend\.env" "Green"
    }
    
    Write-ColorOutput "`n========================================" "Green"
    Write-ColorOutput "✓ 环境配置完成!" "Green"
    Write-ColorOutput "========================================" "Green"
    Write-ColorOutput "`n下一步:" "Yellow"
    Write-ColorOutput "1. 编辑 backend\.env 填入 API 密钥" "White"
    Write-ColorOutput "2. 选择选项 2 启动所有服务" "White"
    Write-ColorOutput "`n按任意键返回菜单..." "DarkGray"
    pause
}

# 2. 启动所有服务
function Start-AllServices {
    Write-ColorOutput "`n========================================" "Cyan"
    Write-ColorOutput "启动所有服务..." "Cyan"
    Write-ColorOutput "========================================`n" "Cyan"
    
    # 检查环境
    if (-not (Test-Path "backend\venv")) {
        Write-ColorOutput "× 后端虚拟环境不存在" "Red"
        Write-ColorOutput "请先选择选项 1 进行环境配置`n" "Yellow"
        pause
        return
    }
    
    if (-not (Test-Path "frontend\node_modules")) {
        Write-ColorOutput "× 前端依赖未安装" "Red"
        Write-ColorOutput "请先选择选项 1 进行环境配置`n" "Yellow"
        pause
        return
    }
    
    # 检测可用的 PowerShell 版本
    $pwshPath = $null
    if (Get-Command pwsh -ErrorAction SilentlyContinue) {
        $pwshPath = "pwsh"
        Write-ColorOutput "检测到 PowerShell 7+，将使用新版本启动服务" "Cyan"
    } elseif (Test-Path "$env:ProgramFiles\PowerShell\7\pwsh.exe") {
        $pwshPath = "$env:ProgramFiles\PowerShell\7\pwsh.exe"
        Write-ColorOutput "检测到 PowerShell 7，将使用新版本启动服务" "Cyan"
    } else {
        $pwshPath = "powershell"
        Write-ColorOutput "使用 Windows PowerShell 5.1 启动服务" "Yellow"
        Write-ColorOutput "建议安装 PowerShell 7+ 以获得更好的兼容性: https://aka.ms/powershell" "DarkGray"
    }
    
    Write-ColorOutput "[1/2] 启动后端服务..." "Green"
    Start-Process $pwshPath -ArgumentList "-NoProfile", "-NoExit", "-Command", "cd '$PWD\backend'; .\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
    
    Write-ColorOutput "等待后端启动..." "Cyan"
    Start-Sleep -Seconds 3
    
    Write-ColorOutput "[2/2] 启动前端服务..." "Green"
    Start-Process $pwshPath -ArgumentList "-NoProfile", "-NoExit", "-Command", "cd '$PWD\frontend'; npm run dev"
    
    Write-ColorOutput "`n========================================" "Green"
    Write-ColorOutput "✓ 系统启动完成!" "Green"
    Write-ColorOutput "========================================" "Green"
    Write-ColorOutput "访问地址:" "Cyan"
    Write-ColorOutput "  前端: http://localhost:3000" "Yellow"
    Write-ColorOutput "  后端: http://localhost:8000" "Yellow"
    Write-ColorOutput "  管理: http://localhost:3000/admin" "Yellow"
    Write-ColorOutput "  文档: http://localhost:8000/docs" "Yellow"
    Write-ColorOutput "========================================`n" "Green"
    Write-ColorOutput "提示: 服务已在新窗口中启动" "DarkGray"
    Write-ColorOutput "按任意键返回菜单..." "DarkGray"
    pause
}

# 3. 启动后端服务
function Start-Backend {
    Write-ColorOutput "`n========================================" "Cyan"
    Write-ColorOutput "启动后端服务..." "Cyan"
    Write-ColorOutput "========================================`n" "Cyan"
    
    if (-not (Test-Path "backend\venv")) {
        Write-ColorOutput "× 虚拟环境不存在" "Red"
        Write-ColorOutput "请先选择选项 1 进行环境配置`n" "Yellow"
        pause
        return
    }
    
    if (-not (Test-Path "backend\.env")) {
        Write-ColorOutput "× 配置文件不存在" "Red"
        Write-ColorOutput "请先选择选项 1 进行环境配置`n" "Yellow"
        pause
        return
    }
    
    Write-ColorOutput "服务地址: http://localhost:8000" "Cyan"
    Write-ColorOutput "API 文档: http://localhost:8000/docs" "Cyan"
    Write-ColorOutput "按 Ctrl+C 停止服务`n" "Yellow"
    
    Push-Location backend
    & .\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    Pop-Location
}

# 4. 启动前端服务
function Start-Frontend {
    Write-ColorOutput "`n========================================" "Cyan"
    Write-ColorOutput "启动前端服务..." "Cyan"
    Write-ColorOutput "========================================`n" "Cyan"
    
    if (-not (Test-Path "frontend\node_modules")) {
        Write-ColorOutput "× 前端依赖未安装" "Red"
        Write-ColorOutput "请先选择选项 1 进行环境配置`n" "Yellow"
        pause
        return
    }
    
    Write-ColorOutput "服务地址: http://localhost:3000" "Cyan"
    Write-ColorOutput "按 Ctrl+C 停止服务`n" "Yellow"
    
    Push-Location frontend
    npm run dev
    Pop-Location
}

# 5. 停止所有服务
function Stop-AllServices {
    Write-ColorOutput "`n========================================" "Cyan"
    Write-ColorOutput "停止所有服务..." "Cyan"
    Write-ColorOutput "========================================`n" "Cyan"
    
    $stopped = $false
    
    # 停止后端 (端口 8000)
    $backendProcesses = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | 
                       Select-Object -ExpandProperty OwningProcess -Unique
    
    if ($backendProcesses) {
        foreach ($pid in $backendProcesses) {
            try {
                $process = Get-Process -Id $pid -ErrorAction Stop
                Stop-Process -Id $pid -Force
                Write-ColorOutput "✓ 已停止后端服务 (PID: $pid)" "Green"
                $stopped = $true
            } catch {
                Write-ColorOutput "× 无法停止进程 $pid" "Red"
            }
        }
    }
    
    # 停止前端 (端口 3000)
    $frontendProcesses = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue | 
                        Select-Object -ExpandProperty OwningProcess -Unique
    
    if ($frontendProcesses) {
        foreach ($pid in $frontendProcesses) {
            try {
                $process = Get-Process -Id $pid -ErrorAction Stop
                Stop-Process -Id $pid -Force
                Write-ColorOutput "✓ 已停止前端服务 (PID: $pid)" "Green"
                $stopped = $true
            } catch {
                Write-ColorOutput "× 无法停止进程 $pid" "Red"
            }
        }
    }
    
    if (-not $stopped) {
        Write-ColorOutput "⚠ 未发现运行中的服务" "Yellow"
    } else {
        Write-ColorOutput "`n✓ 所有服务已停止" "Green"
    }
    
    Write-ColorOutput "`n按任意键返回菜单..." "DarkGray"
    pause
}

# 6. 验证安装
function Verify-Installation {
    Write-ColorOutput "`n========================================" "Cyan"
    Write-ColorOutput "验证安装状态..." "Cyan"
    Write-ColorOutput "========================================`n" "Cyan"
    
    $allOk = $true
    
    # 检查 Python
    Write-ColorOutput "[1/7] 检查 Python..." "Yellow"
    try {
        $pythonVersion = python --version 2>&1
        Write-ColorOutput "✓ $pythonVersion" "Green"
    } catch {
        Write-ColorOutput "× python 未安装" "Red"
        $allOk = $false
    }
    
    # 检查 Node.js
    Write-ColorOutput "[2/7] 检查 Node.js..." "Yellow"
    try {
        $nodeVersion = node --version 2>&1
        Write-ColorOutput "✓ Node.js $nodeVersion" "Green"
    } catch {
        Write-ColorOutput "× Node.js 未安装" "Red"
        $allOk = $false
    }
    
    # 检查后端虚拟环境
    Write-ColorOutput "[3/7] 检查后端虚拟环境..." "Yellow"
    if (Test-Path "backend\venv") {
        Write-ColorOutput "✓ 虚拟环境存在" "Green"
    } else {
        Write-ColorOutput "× 虚拟环境不存在" "Red"
        $allOk = $false
    }
    
    # 检查前端依赖
    Write-ColorOutput "[4/7] 检查前端依赖..." "Yellow"
    if (Test-Path "frontend\node_modules") {
        Write-ColorOutput "✓ 前端依赖已安装" "Green"
    } else {
        Write-ColorOutput "× 前端依赖未安装" "Red"
        $allOk = $false
    }
    
    # 检查配置文件
    Write-ColorOutput "[5/7] 检查配置文件..." "Yellow"
    if (Test-Path "backend\.env") {
        Write-ColorOutput "✓ 配置文件存在" "Green"
        
        # 检查必要的配置项
        $envContent = Get-Content "backend\.env" -Raw
        if ($envContent -match "OPENAI_API_KEY=your-api-key-here") {
            Write-ColorOutput "⚠ 警告: API 密钥未配置" "Yellow"
        }
    } else {
        Write-ColorOutput "× 配置文件不存在" "Red"
        $allOk = $false
    }
    
    # 检查端口占用
    Write-ColorOutput "[6/7] 检查端口占用..." "Yellow"
    $port8000 = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    $port3000 = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue
    
    if ($port8000) {
        Write-ColorOutput "⚠ 端口 8000 已被占用" "Yellow"
    } else {
        Write-ColorOutput "✓ 端口 8000 可用" "Green"
    }
    
    if ($port3000) {
        Write-ColorOutput "⚠ 端口 3000 已被占用" "Yellow"
    } else {
        Write-ColorOutput "✓ 端口 3000 可用" "Green"
    }
    
    # 检查数据库
    Write-ColorOutput "[7/7] 检查数据库..." "Yellow"
    if (Test-Path "backend\ai_polish.db") {
        Write-ColorOutput "✓ 数据库文件存在" "Green"
    } else {
        Write-ColorOutput "⚠ 数据库未初始化（首次启动时会自动创建）" "Yellow"
    }
    
    # 总结
    Write-ColorOutput "`n========================================" "Cyan"
    if ($allOk) {
        Write-ColorOutput "✓ 所有检查通过!" "Green"
    } else {
        Write-ColorOutput "⚠ 部分检查未通过" "Yellow"
        Write-ColorOutput "建议选择选项 1 重新配置环境" "Yellow"
    }
    Write-ColorOutput "========================================`n" "Cyan"
    
    Write-ColorOutput "按任意键返回菜单..." "DarkGray"
    pause
}

# 7. 验证数据库
function Verify-Database {
    Write-ColorOutput "`n========================================" "Cyan"
    Write-ColorOutput "验证数据库..." "Cyan"
    Write-ColorOutput "========================================`n" "Cyan"
    
    if (-not (Test-Path "backend\venv")) {
        Write-ColorOutput "× 虚拟环境不存在" "Red"
        Write-ColorOutput "请先选择选项 1 进行环境配置`n" "Yellow"
        pause
        return
    }
    
    Write-ColorOutput "运行数据库验证脚本..." "Cyan"
    Push-Location backend
    & .\venv\Scripts\python.exe init_db.py
    $exitCode = $LASTEXITCODE
    Pop-Location
    
    if ($exitCode -eq 0) {
        Write-ColorOutput "`n✓ 数据库验证成功" "Green"
    } else {
        Write-ColorOutput "`n× 数据库验证失败" "Red"
    }
    
    Write-ColorOutput "`n按任意键返回菜单..." "DarkGray"
    pause
}

# 主程序
function Main {
    # 如果提供了命令行参数，直接执行对应功能
    if ($Option -gt 0) {
        switch ($Option) {
            1 { Setup-Environment }
            2 { Start-AllServices }
            3 { Start-Backend }
            4 { Start-Frontend }
            5 { Stop-AllServices }
            6 { Verify-Installation }
            7 { Verify-Database }
            default {
                Write-ColorOutput "无效的选项: $Option" "Red"
            }
        }
        return
    }
    
    # 交互式菜单
    while ($true) {
        Show-Menu
        $choice = Read-Host
        
        switch ($choice) {
            "1" { Setup-Environment }
            "2" { Start-AllServices }
            "3" { Start-Backend }
            "4" { Start-Frontend }
            "5" { Stop-AllServices }
            "6" { Verify-Installation }
            "7" { Verify-Database }
            "0" { 
                Write-ColorOutput "`n再见!`n" "Cyan"
                exit 0
            }
            default {
                Write-ColorOutput "`n无效的选项，请重新选择" "Red"
                Start-Sleep -Seconds 2
            }
        }
    }
}

# 运行主程序
Main
