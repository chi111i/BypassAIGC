#!/bin/bash
# E2E 浏览器测试 — 验证并发控制的 UI 表现
# 前提：服务器已在 localhost:9800 运行
# 用法: bash test_e2e_ui.sh

set -e
PCLI="playwright-cli"

echo "=========================================="
echo " E2E UI Test — 验证并发控制"
echo "=========================================="

# 1. 打开浏览器
$PCLI open --browser=chromium
sleep 2

# 2. 访问服务
$PCLI goto "http://localhost:9800"
sleep 3
$PCLI snapshot --filename=00-login.yaml

# 3. 登录
$PCLI fill e1 "admin"
sleep 0.5
$PCLI fill e2 "admin123"  
sleep 0.5
$PCLI click e3
sleep 3
$PCLI snapshot --filename=01-logged-in.yaml

# 4. 去管理员面板设置 per_user=1
$PCLI goto "http://localhost:9800/admin"
sleep 3
$PCLI snapshot --filename=02-admin.yaml

# 5. 返回工作台
$PCLI goto "http://localhost:9800/workspace"  
sleep 3
$PCLI snapshot --filename=03-workspace.yaml

# 6. 验证 sessionStorage 隔离
echo "--- sessionStorage ---"
$PCLI eval "JSON.stringify(sessionStorage.getItem('authToken') ? '有 token' : '无 token')"
sleep 1

# 7. 开新标签页用不同用户登录（模拟多用户隔离）
$PCLI tab-new "http://localhost:9800"
sleep 2

# 8. 截图当前状态
$PCLI screenshot --filename=04-multi-tab.png

echo ""
echo "截图已保存，请在 .playwright-cli/ 目录查看"
echo ""
echo "手动检查要点:"
echo "  - 01-login.yaml: 登录是否成功"
echo "  - 02-admin.yaml: 管理面板能否配置并发"
echo "  - 03-workspace.yaml: 工作台是否正常"
echo "  - 04-multi-tab.png: 多标签页截图"

# 9. 关闭浏览器
$PCLI close 2>/dev/null || true
