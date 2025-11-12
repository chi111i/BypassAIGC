# 构建 Windows 可执行文件 (Building Windows Executable)

本文档说明如何将后端应用打包为 Windows 可执行文件 (.exe)。

## 自动构建 (Automated Build via GitHub Actions)

每次推送到 `main` 或 `master` 分支，或创建版本标签时，GitHub Actions 会自动构建 Windows 可执行文件。

### 触发自动构建：

1. **推送代码到主分支**：
   ```bash
   git push origin main
   ```

2. **创建版本标签**（会自动创建 GitHub Release）：
   ```bash
   git tag -a v1.0.0 -m "Release version 1.0.0"
   git push origin v1.0.0
   ```

3. **手动触发**：
   - 访问 GitHub Actions 页面
   - 选择 "Build Windows Executable" workflow
   - 点击 "Run workflow"

构建完成后，可执行文件将作为 artifact 上传，可以从 Actions 页面下载。

## 本地构建 (Local Build)

### Windows 系统

1. 确保已安装 Python 3.11 或更高版本
2. 进入 backend 目录：
   ```cmd
   cd backend
   ```
3. 运行构建脚本：
   ```cmd
   build.bat
   ```
4. 可执行文件将生成在 `dist` 目录下

### Linux/macOS 系统

1. 确保已安装 Python 3.11 或更高版本
2. 进入 backend 目录：
   ```bash
   cd backend
   ```
3. 运行构建脚本：
   ```bash
   chmod +x build.sh
   ./build.sh
   ```
4. 可执行文件将生成在 `dist` 目录下

### 手动构建步骤

如果构建脚本无法运行，可以手动执行以下步骤：

```bash
cd backend

# 安装依赖
pip install -r requirements.txt
pip install -r requirements-build.txt

# 构建可执行文件
pyinstaller build.spec
```

## 运行可执行文件

构建完成后：

1. 在 `backend/dist` 目录下找到 `BypassAIGC-Backend.exe`
2. 确保在同一目录或父目录有 `.env` 配置文件
3. 双击运行或通过命令行运行：
   ```cmd
   BypassAIGC-Backend.exe
   ```
4. 服务将在 `http://localhost:8000` 启动

## 配置文件

可执行文件需要 `.env` 配置文件才能正常运行。请确保：

1. 在可执行文件所在目录或上级目录创建 `.env` 文件
2. 可以复制 `backend/.env.example` 文件并重命名为 `.env`
3. 参考 `.env.example` 中的说明填写必要的配置项
4. 详细配置说明请参考主 README.md

## 注意事项

1. **首次运行**：首次运行可执行文件时，Windows 可能会显示安全警告，选择"仍要运行"即可
2. **防病毒软件**：某些防病毒软件可能会误报，需要添加到白名单
3. **数据库**：默认使用 SQLite 数据库，数据库文件会在当前目录创建
4. **依赖项**：所有 Python 依赖项已打包进可执行文件，无需额外安装

## 文件说明

- `build.spec` - PyInstaller 配置文件
- `build.bat` - Windows 构建脚本
- `build.sh` - Unix/Linux 构建脚本
- `requirements-build.txt` - 构建所需的额外依赖

## 故障排除

### 构建失败

如果构建失败，请检查：
1. Python 版本是否为 3.11 或更高
2. 所有依赖项是否正确安装
3. 查看构建日志中的错误信息

### 运行失败

如果可执行文件无法运行：
1. 检查 `.env` 配置文件是否存在且配置正确
2. 查看控制台输出的错误信息
3. 确保没有其他服务占用 8000 端口

## 技术细节

- **打包工具**：PyInstaller 6.0+
- **Python 版本**：3.11
- **打包模式**：单文件模式（所有依赖打包进一个 exe）
- **控制台模式**：启用（可以看到运行日志）

## 更新日志

- 初始版本：支持将 FastAPI 后端打包为 Windows 可执行文件
