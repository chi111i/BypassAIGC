"""
Integration tests requiring real API credentials.

Usage:
    BYPASS_AIGC_API_KEY=sk-xxx BYPASS_AIGC_BASE_URL=https://your-proxy/v1 \\
    BYPASS_AIGC_MODEL=gemini-2.5-pro python -m pytest tests/test_integration.py -v -s

Skip in CI with: -k "not integration"
"""
import os
import pytest
import time

pytestmark = pytest.mark.integration

API_KEY = os.environ.get("BYPASS_AIGC_API_KEY")
BASE_URL = os.environ.get("BYPASS_AIGC_BASE_URL", "https://api.openai.com/v1")
MODEL = os.environ.get("BYPASS_AIGC_MODEL", "gpt-4o-mini")

requires_api = pytest.mark.skipif(
    not API_KEY,
    reason="Set BYPASS_AIGC_API_KEY to run integration tests",
)

API_CONFIG_PAYLOAD = {
    "POLISH_API_KEY": API_KEY,
    "POLISH_BASE_URL": BASE_URL,
    "POLISH_MODEL": MODEL,
    "ENHANCE_API_KEY": API_KEY,
    "ENHANCE_BASE_URL": BASE_URL,
    "ENHANCE_MODEL": MODEL,
}


def create_user(client, admin_token, username, password, display_name=""):
    resp = client.post(
        "/api/admin/users/create",
        json=[{"username": username, "password": password, "display_name": display_name}],
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    return resp.json()["created"][0]


def login(client, username, password):
    resp = client.post("/api/auth/login", json={
        "username": username, "password": password,
    })
    assert resp.status_code == 200
    return resp.json()["access_token"]


def submit_task(client, token, text, mode="paper_polish"):
    resp = client.post(
        "/api/optimization/start",
        json={"original_text": text, "processing_mode": mode},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    return resp.json()["session_id"]


def wait_for_completion(client, token, session_id, timeout=120):
    deadline = time.time() + timeout
    last_progress = -1
    while time.time() < deadline:
        time.sleep(2)
        prog = client.get(
            f"/api/optimization/sessions/{session_id}/progress",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = prog.json()
        status = data["status"]
        pct = data.get("progress", 0)
        stage = data.get("current_stage", "?")
        pos = data.get("current_position", 0)
        total = data.get("total_segments", 0)
        if pct != last_progress:
            print(f"  [{session_id[:8]}] {status} stage={stage} {pos}/{total} {pct:.0f}%", flush=True)
            last_progress = pct
        if status == "completed":
            return True
        if status == "failed":
            print(f"  [{session_id[:8]}] FAILED: {data.get('error_message', 'unknown')[:200]}", flush=True)
            return False
    print(f"  [{session_id[:8]}] TIMEOUT after {timeout}s", flush=True)
    return False


def get_session_detail(client, token, session_id):
    return client.get(
        f"/api/optimization/sessions/{session_id}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()


TEXTS = {
    "ai_ethics": (
        "人工智能伦理问题日益受到学术界和产业界的广泛关注。"
        "如何在技术创新的同时确保公平性、透明度和可解释性，"
        "已成为AI治理的核心议题。"
    ),
    "nlp_progress": (
        "近年来，基于Transformer架构的预训练语言模型在自然语言处理领域取得了突破性进展。"
        "BERT、GPT等模型的出现大幅提升了机器翻译、文本摘要、情感分析等任务的性能。"
    ),
    "cv_application": (
        "计算机视觉技术在医疗影像诊断中展现出巨大的应用潜力。"
        "深度学习模型能够从CT、MRI等医学图像中自动识别异常区域，"
        "辅助医生进行更精准的疾病筛查和诊断。"
    ),
    "quantum_computing": (
        "量子计算是当前信息技术领域最前沿的研究方向之一。"
        "与经典计算机相比，量子计算机利用量子叠加和纠缠等特性，"
        "有望在密码学、材料科学和药物研发等领域带来革命性突破。"
    ),
    "climate_modeling": (
        "气候变化模型是预测全球变暖趋势的重要工具。"
        "通过整合大气、海洋、陆地等多圈层数据，"
        "科学家能够模拟不同碳排放情景下的温度变化和海平面上升幅度。"
    ),
    "robotics": (
        "具身智能是人工智能与机器人技术融合的新范式。"
        "通过在物理世界中感知、学习和行动，"
        "智能机器人正在工业制造、物流仓储和家庭服务等场景中发挥越来越重要的作用。"
    ),
}


class TestBasicPolish:
    """基础润色功能测试"""

    @pytest.fixture(autouse=True)
    def configure(self, client, admin_token):
        client.post(
            "/api/admin/config",
            json=API_CONFIG_PAYLOAD,
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    @pytest.mark.timeout(90)
    def test_polish_single_text(self, client, admin_token):
        """润色单段文本"""
        create_user(client, admin_token, "polish_user", "pass123", "润色测试")
        token = login(client, "polish_user", "pass123")
        sid = submit_task(client, token, TEXTS["ai_ethics"], "paper_polish")
        assert wait_for_completion(client, token, sid, timeout=60)
        detail = get_session_detail(client, token, sid)
        assert detail["status"] == "completed"
        assert len(detail["segments"]) > 0
        for seg in detail["segments"]:
            assert seg["polished_text"] is not None
            assert len(seg["polished_text"]) > 0

    @pytest.mark.timeout(180)
    def test_polish_and_enhance(self, client, admin_token):
        """润色+增强两阶段处理"""
        create_user(client, admin_token, "pe_user", "pass123", "两阶段测试")
        token = login(client, "pe_user", "pass123")
        sid = submit_task(client, token, TEXTS["nlp_progress"], "paper_polish_enhance")
        assert wait_for_completion(client, token, sid, timeout=120)
        detail = get_session_detail(client, token, sid)
        assert detail["status"] == "completed"
        for seg in detail["segments"]:
            assert seg["polished_text"] is not None
            assert seg["enhanced_text"] is not None
            assert seg["polished_text"] != seg["enhanced_text"], (
                f"增强结果应与润色结果不同: {seg['polished_text'][:30]} vs {seg['enhanced_text'][:30]}"
            )

    @pytest.mark.timeout(90)
    def test_paper_enhance_only(self, client, admin_token):
        """仅增强模式（跳过润色）"""
        create_user(client, admin_token, "enh_only", "pass123", "仅增强")
        token = login(client, "enh_only", "pass123")
        sid = submit_task(client, token, TEXTS["cv_application"], "paper_enhance")
        assert wait_for_completion(client, token, sid, timeout=60)
        detail = get_session_detail(client, token, sid)
        assert detail["status"] == "completed"
        for seg in detail["segments"]:
            assert seg["enhanced_text"] is not None
            assert len(seg["enhanced_text"]) > 0

    @pytest.mark.timeout(90)
    def test_emotion_polish(self, client, admin_token):
        """感情文章润色模式"""
        create_user(client, admin_token, "emotion_user", "pass123", "感情润色")
        token = login(client, "emotion_user", "pass123")
        sid = submit_task(client, token, "春天的阳光洒在窗台上，温暖而柔和。", "emotion_polish")
        assert wait_for_completion(client, token, sid, timeout=60)
        detail = get_session_detail(client, token, sid)
        assert detail["status"] == "completed"
        assert len(detail["segments"]) > 0


class TestParallelSameUser:
    """同一用户并行多任务测试"""

    @pytest.fixture(autouse=True)
    def configure(self, client, admin_token):
        client.post(
            "/api/admin/config",
            json=API_CONFIG_PAYLOAD,
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    @pytest.mark.timeout(360)
    def test_three_parallel_tasks(self, client, admin_token):
        """同一用户同时提交3个不同文本"""
        create_user(client, admin_token, "busy_user", "pass123", "多任务用户")
        token = login(client, "busy_user", "pass123")

        texts = [
            (TEXTS["ai_ethics"], "paper_polish"),
            (TEXTS["nlp_progress"], "paper_polish_enhance"),
            (TEXTS["cv_application"], "paper_enhance"),
        ]
        sids = []
        for text, mode in texts:
            sids.append(submit_task(client, token, text, mode))

        assert len(sids) == 3

        results = []
        for sid in sids:
            ok = wait_for_completion(client, token, sid, timeout=300)
            detail = get_session_detail(client, token, sid)
            results.append({"session_id": sid, "success": ok, "status": detail["status"]})

        failed = [r for r in results if not r["success"]]
        assert len(failed) == 0, f"Some tasks failed: {failed}"

        my_sessions = client.get(
            "/api/optimization/sessions",
            headers={"Authorization": f"Bearer {token}"},
        ).json()
        assert len(my_sessions) == 3

    @pytest.mark.timeout(360)
    def test_mixed_modes_parallel(self, client, admin_token):
        """同一用户同时使用不同处理模式"""
        create_user(client, admin_token, "mixed_user", "pass123", "混合模式")
        token = login(client, "mixed_user", "pass123")

        sid1 = submit_task(client, token, TEXTS["quantum_computing"], "paper_polish")
        sid2 = submit_task(client, token, TEXTS["climate_modeling"], "paper_polish_enhance")

        assert wait_for_completion(client, token, sid1, timeout=300)
        assert wait_for_completion(client, token, sid2, timeout=300)

        d1 = get_session_detail(client, token, sid1)
        d2 = get_session_detail(client, token, sid2)
        assert d1["status"] == "completed"
        assert d2["status"] == "completed"


class TestParallelMultiUser:
    """多用户并行测试"""

    @pytest.fixture(autouse=True)
    def configure(self, client, admin_token):
        client.post(
            "/api/admin/config",
            json=API_CONFIG_PAYLOAD,
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    @pytest.mark.timeout(360)
    def test_two_users_concurrent(self, client, admin_token):
        """两个用户同时各自提交任务"""
        create_user(client, admin_token, "alice", "pass123", "Alice")
        create_user(client, admin_token, "bob", "pass123", "Bob")
        token_a = login(client, "alice", "pass123")
        token_b = login(client, "bob", "pass123")

        sid_a = submit_task(client, token_a, TEXTS["robotics"], "paper_polish")
        sid_b = submit_task(client, token_b, TEXTS["ai_ethics"], "paper_polish")

        assert wait_for_completion(client, token_a, sid_a, timeout=300)
        assert wait_for_completion(client, token_b, sid_b, timeout=300)

        d_a = get_session_detail(client, token_a, sid_a)
        d_b = get_session_detail(client, token_b, sid_b)
        assert d_a["status"] == "completed"
        assert d_b["status"] == "completed"

    def test_data_isolation_with_tasks(self, client, admin_token):
        """多用户任务级数据隔离"""
        create_user(client, admin_token, "user_x", "pass123", "User X")
        create_user(client, admin_token, "user_y", "pass123", "User Y")
        token_x = login(client, "user_x", "pass123")
        token_y = login(client, "user_y", "pass123")

        submit_task(client, token_x, TEXTS["ai_ethics"], "paper_polish")
        submit_task(client, token_y, TEXTS["nlp_progress"], "paper_polish")
        time.sleep(3)

        sessions_x = client.get(
            "/api/optimization/sessions",
            headers={"Authorization": f"Bearer {token_x}"},
        ).json()
        sessions_y = client.get(
            "/api/optimization/sessions",
            headers={"Authorization": f"Bearer {token_y}"},
        ).json()

        assert len(sessions_x) == 1
        assert len(sessions_y) == 1
        assert sessions_x[0]["session_id"] != sessions_y[0]["session_id"]

    def test_cross_user_access_denied(self, client, admin_token):
        """用户不能访问其他用户的会话"""
        create_user(client, admin_token, "owner", "pass123", "Owner")
        create_user(client, admin_token, "intruder", "pass123", "Intruder")
        token_o = login(client, "owner", "pass123")
        token_i = login(client, "intruder", "pass123")

        sid = submit_task(client, token_o, TEXTS["robotics"], "paper_polish")
        resp = client.get(
            f"/api/optimization/sessions/{sid}",
            headers={"Authorization": f"Bearer {token_i}"},
        )
        assert resp.status_code == 404


class TestQuality:
    """输出质量验证"""

    @pytest.fixture(autouse=True)
    def configure(self, client, admin_token):
        client.post(
            "/api/admin/config",
            json=API_CONFIG_PAYLOAD,
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    def test_polish_preserves_meaning(self, client, admin_token):
        """润色后保留原文核心信息"""
        create_user(client, admin_token, "quality1", "pass123", "质量测试")
        token = login(client, "quality1", "pass123")
        sid = submit_task(client, token, TEXTS["cv_application"], "paper_polish")
        assert wait_for_completion(client, token, sid, timeout=60)
        detail = get_session_detail(client, token, sid)
        polished = detail["segments"][0]["polished_text"]
        for keyword in ["计算机视觉", "医疗影像", "CT", "MRI", "深度学习"]:
            assert keyword in polished, f"关键词 '{keyword}' 在润色后丢失"

    def test_enhance_different_from_polish(self, client, admin_token):
        """增强结果应与润色结果在结构上不同"""
        create_user(client, admin_token, "quality2", "pass123", "增强质量")
        token = login(client, "quality2", "pass123")
        sid = submit_task(client, token, TEXTS["quantum_computing"], "paper_polish_enhance")
        assert wait_for_completion(client, token, sid, timeout=120)
        detail = get_session_detail(client, token, sid)
        seg = detail["segments"][0]
        assert seg["polished_text"] != seg["enhanced_text"], (
            f"增强应与润色不同\n润色: {seg['polished_text'][:50]}\n增强: {seg['enhanced_text'][:50]}"
        )
        assert len(seg["enhanced_text"]) >= len(seg["polished_text"]) * 0.5
