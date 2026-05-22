#!/bin/bash
# AI 学术写作助手 - 构建脚本
# 用于在本地构建可执行文件

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "AI 学术写作助手 - 构建脚本"
echo "=========================================="

# 检查 Python
echo ""
echo "1. 检查 Python 环境..."
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 Python3，请先安装 Python 3.9+（构建 exe 推荐 3.12+）"
    exit 1
fi
python3 --version

# 检查 Node.js
echo ""
echo "2. 检查 Node.js 环境..."
if ! command -v node &> /dev/null; then
    echo "错误: 未找到 Node.js，请先安装 Node.js 18+"
    exit 1
fi
node --version

# 安装后端依赖
echo ""
echo "3. 安装后端依赖..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt

# 安装前端依赖并构建
echo ""
echo "4. 构建前端..."
cd frontend
npm install
npm run build
cd ..

# 复制前端构建产物到 static 目录
echo ""
echo "5. 复制前端构建产物..."
rm -rf static
cp -r frontend/dist static

# 使用 PyInstaller 打包
echo ""
echo "6. 使用 PyInstaller 打包..."
pyinstaller app.spec --clean

echo ""
echo "=========================================="
echo "构建完成!"
echo "可执行文件位置: dist/AI学术写作助手"
echo "=========================================="
echo ""
echo "运行方式:"
echo "1. 将 dist/AI学术写作助手 复制到任意目录"
echo "2. 首次运行会自动创建 .env 配置文件"
echo "3. 编辑 .env 文件，填入 API Key 等配置"
echo "4. 再次运行程序，将自动打开浏览器"
echo ""
