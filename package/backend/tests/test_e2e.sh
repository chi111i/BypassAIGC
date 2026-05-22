#!/bin/bash
# E2E 浏览器测试 — 用 playwright-cli 打真实 UI
# 用法: bash test_e2e.sh

set -e

PORT=19800
BASE="http://localhost:$PORT"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_FILE="/tmp/e2e_test.log"
PCLI="playwright-cli"

echo "=========================================="
echo " E2E Browser Test — 启动服务器..."
echo "=========================================="

# 启动 uvicorn
cd "$PROJECT_DIR"
python -m uvicorn app.main:app --host 127.0.0.1 --port $PORT --log-level error &
SERVER_PID=$!
echo "服务器 PID: $SERVER_PID"

# 等待服务器就绪
for i in $(seq 1 20); do
    if curl -s "$BASE/api/health/models" > /dev/null 2>&1; then
        echo "服务器就绪!"
        break
    fi
    sleep 1
done

cleanup() {
    echo "清理..."
    $PCLI close 2>/dev/null || true
    kill $SERVER_PID 2>/dev/null || true
    wait $SERVER_PID 2>/dev/null || true
    echo "完成"
}
trap cleanup EXIT

echo ""
echo "========== 1. 打开浏览器 =========="
$PCLI open --browser=chromium
sleep 1

echo ""
echo "========== 2. 访问登录页 =========="
$PCLI goto "$BASE"
sleep 1
$PCLI snapshot --filename=e2e-login.yaml
echo "--- 登录页 ---"
cat .playwright-cli/e2e-login.yaml | head -20

echo ""
echo "========== 3. 登录 =========="
# 输入用户名和密码
$PCLI fill e1 "admin"
$PCLI fill e2 "admin123"
$PCLI snapshot --filename=e2e-login-filled.yaml
$PCLI click e3
sleep 2
$PCLI snapshot --filename=e2e-logged-in.yaml
echo "--- 登录后 ---"
cat .playwright-cli/e2e-logged-in.yaml | grep -E "url|title|text" | head -10

echo ""
echo "========== 4. 进入管理员面板 =========="
$PCLI goto "$BASE/admin"
sleep 2
$PCLI snapshot --filename=e2e-admin.yaml
echo "--- 管理员面板 ---"
cat .playwright-cli/e2e-admin.yaml | grep -E "url|title|text" | head -10

echo ""
echo "========== 5. 设置并发 =========="
# 设置单用户并发=1
# 管理员面板中有个配置区, 直接通过 API 设置
curl -s -X POST "$BASE/api/admin/config" \
    -H "Content-Type: application/json" \
    -d '{"MAX_CONCURRENT_USERS":"5","MAX_CONCURRENT_PER_USER":"1"}' \
    -H "Authorization: Bearer $(curl -s -X POST "$BASE/api/admin/login" -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin123"}' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')"
echo "配置已更新: per_user=1"

echo ""
echo "========== 6. 返回工作台 =========="
$PCLI goto "$BASE/workspace"
sleep 2
$PCLI snapshot --filename=e2e-workspace.yaml
echo "--- 工作台 ---"
cat .playwright-cli/e2e-workspace.yaml | grep -E "url|title|text" | head -15

echo ""
echo "========== 7. 提交第一个任务 =========="
# 在文本框中输入内容
$PCLI snapshot --filename=e2e-before-submit.yaml
# 尝试找到文本输入框并填写
# 根据 snapshot 中的 ref 来定位

# 通过 API 提交来验证并发控制
TOKEN=$(curl -s -X POST "$BASE/api/auth/login" -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin123"}' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

echo ""
echo "========== 8. 并发测试: 提交 6 个任务 =========="
for i in 1 2 3 4 5 6; do
    RESP=$(curl -s -X POST "$BASE/api/optimization/start" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"original_text\":\"测试文本第$i篇。这是一个关于人工智能的研究论文摘要。\",\"processing_mode\":\"paper_polish\"}")
    SESSION_ID=$(echo "$RESP" | python -c "import sys,json;print(json.load(sys.stdin).get('session_id','?'))" 2>/dev/null || echo "?")
    echo "  任务 $i: session=$SESSION_ID"
done

echo ""
echo "========== 9. 验证并发状态 =========="
sleep 2
python -c "
import sys
sys.path.insert(0, '$PROJECT_DIR')
from app.services.concurrency import concurrency_manager
print(f'  活跃会话: {concurrency_manager.get_active_count()}')
print(f'  排队队列: {len(concurrency_manager.queue)}')
print(f'  每用户计数: {concurrency_manager.active_per_user}')
"

echo ""
echo "========== 10. 截图 =========="
$PCLI screenshot --filename=e2e-final.png
echo "截图已保存: .playwright-cli/e2e-final.png"

echo ""
echo "=========================================="
echo " E2E 测试完成!"
echo "=========================================="
