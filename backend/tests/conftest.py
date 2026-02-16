"""
Certify Intel - Test Configuration and Fixtures
TECH-003: Test Infrastructure for improved test coverage

This module provides pytest fixtures for testing the Certify Intel application.
"""
import os
import sys
import pytest
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Generator

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test environment
os.environ['TESTING'] = 'true'
os.environ['DATABASE_URL'] = 'sqlite:///./test_certify_intel.db'
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-pytest-do-not-use-in-prod')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient


# ==============================================================================
# Database Fixtures
# ==============================================================================

# Create a shared test engine and session factory at module level
TEST_DATABASE_URL = "sqlite:///./test_certify_intel.db"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session")
def engine():
    """Create a test database engine."""
    from database import Base
    Base.metadata.create_all(bind=test_engine)
    yield test_engine
    # Cleanup after all tests
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def db_session(engine) -> Generator:
    """Create a new database session for each test."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def override_get_db():
    """Dependency override for FastAPI's get_db."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_admin_user_in_db():
    """Seed the default admin user into the test database.

    Uses PBKDF2-HMAC-SHA256 hashing (same as extended_features.AuthManager.hash_password)
    so that the /token endpoint can authenticate successfully.
    """
    from database import User

    session = TestingSessionLocal()
    try:
        existing = session.query(User).filter(User.email == "[YOUR-ADMIN-EMAIL]").first()
        if existing:
            return  # Already seeded

        # Hash password using PBKDF2 (matches AuthManager.hash_password)
        password = "[YOUR-ADMIN-PASSWORD]"
        salt = secrets.token_bytes(32)
        pw_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000).hex()
        hashed_password = f"{salt.hex()}${pw_hash}"

        admin = User(
            email="[YOUR-ADMIN-EMAIL]",
            hashed_password=hashed_password,
            full_name="Admin User",
            role="admin",
            is_active=True,
        )
        session.add(admin)
        session.commit()
    finally:
        session.close()


@pytest.fixture(scope="module")
def test_client(engine) -> Generator:
    """Create a test client for the FastAPI application with database override."""
    from main import app, get_db
    from database import Base

    # Ensure tables exist
    Base.metadata.create_all(bind=test_engine)

    # Seed admin user so _login() succeeds in E2E tests
    _seed_admin_user_in_db()

    # Override the database dependency
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    # Clean up the override
    app.dependency_overrides.clear()


# ==============================================================================
# Sample Data Fixtures
# ==============================================================================

@pytest.fixture
def sample_competitor(db_session):
    """Create a sample competitor for testing (function-scoped, rolled back after test)."""
    from database import Competitor
    import uuid

    # Use unique name with UUID to avoid UNIQUE constraint violations
    unique_suffix = str(uuid.uuid4())[:8]

    # Use fields that actually exist in the Competitor model
    competitor = Competitor(
        name=f"Test Competitor {unique_suffix}",
        website=f"https://testcompetitor-{unique_suffix}.com",
        headquarters="San Francisco, CA",
        employee_count="500",  # String type in actual schema
        year_founded="2015",  # String type, field is year_founded not founded_year
        pricing_model="Subscription",
        key_features="Feature A, Feature B, Feature C",
        target_segments="Healthcare",  # Field is target_segments not target_market
        threat_level="Medium",
        status="Active",  # Use status instead of is_active
        notes="A test competitor for unit testing"  # Use notes instead of description
    )
    db_session.add(competitor)
    db_session.commit()
    db_session.refresh(competitor)
    return competitor


@pytest.fixture(scope="module")
def api_test_competitor(engine):
    """Create a persistent competitor for API tests (module-scoped, committed to DB)."""
    from database import Competitor, Base
    import uuid

    # Ensure all tables exist (handles race conditions with test_client startup)
    Base.metadata.create_all(bind=test_engine)

    session = TestingSessionLocal()
    unique_suffix = str(uuid.uuid4())[:8]

    competitor = Competitor(
        name=f"API Test Competitor {unique_suffix}",
        website=f"https://api-test-{unique_suffix}.com",
        headquarters="New York, NY",
        employee_count="1000",
        year_founded="2010",
        pricing_model="Enterprise",
        key_features="Feature X, Feature Y",
        target_segments="Healthcare IT",
        threat_level="High",
        status="Active",
        notes="A test competitor for API testing"
    )
    session.add(competitor)
    session.commit()
    session.refresh(competitor)
    competitor_id = competitor.id
    competitor_name = competitor.name
    session.close()

    # Return a dict with the data since the session is closed
    yield {"id": competitor_id, "name": competitor_name}

    # Cleanup: delete the competitor after tests
    cleanup_session = TestingSessionLocal()
    try:
        comp = cleanup_session.query(Competitor).filter_by(id=competitor_id).first()
        if comp:
            cleanup_session.delete(comp)
            cleanup_session.commit()
    finally:
        cleanup_session.close()


@pytest.fixture
def sample_user(db_session):
    """Create a sample user for testing."""
    from database import User
    import hashlib
    import uuid

    # Use unique email with UUID to avoid UNIQUE constraint violations
    unique_suffix = str(uuid.uuid4())[:8]

    secret_key = os.getenv('SECRET_KEY', 'test-secret-key')
    password_hash = hashlib.sha256(f'{secret_key}testpassword123'.encode()).hexdigest()

    # Use fields that actually exist in the User model
    user = User(
        email=f"test-{unique_suffix}@certifyhealth.com",
        hashed_password=password_hash,
        full_name="Test User",  # Field is full_name not name
        role="admin",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_client, sample_user):
    """Get authentication headers for API requests."""
    response = test_client.post(
        "/token",
        data={
            "username": "test@certifyhealth.com",
            "password": "testpassword123"
        }
    )
    if response.status_code == 200:
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}
    return {}


@pytest.fixture
def sample_product(db_session, sample_competitor):
    """Create a sample product for testing."""
    from database import CompetitorProduct

    # Use fields that actually exist in the CompetitorProduct model
    product = CompetitorProduct(
        competitor_id=sample_competitor.id,
        product_name="Test Product",  # Field is product_name not name
        description="A test product",
        product_category="EHR",  # Field is product_category not category
        target_segment="Mid-Market"
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


@pytest.fixture
def sample_change_history(db_session, sample_competitor):
    """Create sample change history records."""
    from database import DataChangeHistory

    changes = []
    for i in range(5):
        change = DataChangeHistory(
            competitor_id=sample_competitor.id,
            competitor_name=sample_competitor.name,
            field_name=f"test_field_{i}",
            old_value=f"old_value_{i}",
            new_value=f"new_value_{i}",
            changed_by="test@certifyhealth.com",
            change_reason="Test change",
            changed_at=datetime.utcnow() - timedelta(days=i)
        )
        db_session.add(change)
        changes.append(change)

    db_session.commit()
    return changes


# ==============================================================================
# Mock Fixtures
# ==============================================================================

@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    return {
        "choices": [{
            "message": {
                "content": "This is a mock AI response for testing purposes."
            }
        }],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150
        }
    }


@pytest.fixture
def mock_gemini_response():
    """Mock Gemini API response."""
    return {
        "candidates": [{
            "content": {
                "parts": [{
                    "text": "This is a mock Gemini response for testing."
                }]
            }
        }]
    }


# ==============================================================================
# Utility Functions
# ==============================================================================

def assert_valid_response(response, expected_status=200):
    """Assert that an API response is valid."""
    assert response.status_code == expected_status, f"Expected {expected_status}, got {response.status_code}: {response.text}"
    return response.json()


def create_test_competitor_data():
    """Generate test competitor data."""
    return {
        "name": f"Test Competitor {datetime.now().timestamp()}",
        "website": "https://testcompetitor.com",
        "description": "Test description",
        "headquarters": "Test City, TS",
        "employee_count": 100,
        "pricing_model": "Subscription",
        "target_market": "Healthcare"
    }
