import os
import tempfile
import pytest
from pathlib import Path

from dotenv import load_dotenv
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)

TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="bypass_aigc_test_"))
TEST_DB_PATH = TEST_DB_DIR / "test.db"

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ["SECRET_KEY"] = "test-secret-key-for-development-only"
os.environ["ADMIN_PASSWORD"] = "admin123"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["MAX_CONCURRENT_USERS"] = "5"
os.environ["MAX_CONCURRENT_PER_USER"] = "3"
os.environ["API_REQUEST_INTERVAL"] = "0"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.database import Base, engine, SessionLocal
from app.models.models import User
from app.utils.auth import hash_password


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    import shutil
    shutil.rmtree(TEST_DB_DIR, ignore_errors=True)


@pytest.fixture(scope="function")
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def clean_db(db):
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(text(f"DELETE FROM {table.name}"))
    db.commit()
    yield db


@pytest.fixture(scope="function")
def client(clean_db):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_token(client):
    resp = client.post("/api/admin/login", json={
        "username": "admin",
        "password": "admin123",
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.json()}"
    return resp.json()["access_token"]


@pytest.fixture
def test_user(client, admin_token):
    resp = client.post(
        "/api/admin/users/create",
        json=[{"username": "testuser", "password": "testpass", "display_name": "Test User"}],
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, f"User creation failed: {resp.json()}"
    return {"username": "testuser", "password": "testpass", "user_id": resp.json()["created"][0]["id"]}


@pytest.fixture
def user_token(client, test_user):
    resp = client.post("/api/auth/login", json={
        "username": test_user["username"],
        "password": test_user["password"],
    })
    assert resp.status_code == 200, f"User login failed: {resp.json()}"
    return resp.json()["access_token"]


@pytest.fixture
def second_user(client, admin_token):
    resp = client.post(
        "/api/admin/users/create",
        json=[{"username": "user2", "password": "testpass", "display_name": "User Two"}],
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    return {"username": "user2", "password": "testpass"}


@pytest.fixture
def second_user_token(client, second_user):
    resp = client.post("/api/auth/login", json={
        "username": second_user["username"],
        "password": second_user["password"],
    })
    assert resp.status_code == 200
    return resp.json()["access_token"]


# Must import app AFTER setting env vars
from app.main import app
