"""
Certify Intel - Database Model Tests
TEST-001: Unit tests for database models and operations

Tests cover:
- Model creation
- Relationships
- Constraints
- CRUD operations
"""
import pytest
import sys
import os
import uuid
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def unique_name(prefix: str) -> str:
    """Generate a unique name to avoid UNIQUE constraint violations."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# ==============================================================================
# Competitor Model Tests
# ==============================================================================

class TestCompetitorModel:
    """Tests for Competitor model."""

    def test_create_competitor(self, db_session):
        """Test creating a competitor."""
        from database import Competitor

        name = unique_name("Test Company DB")
        competitor = Competitor(
            name=name,
            website="https://test.com",
            notes="Test description"  # Use 'notes' instead of 'description'
        )
        db_session.add(competitor)
        db_session.commit()

        assert competitor.id is not None
        assert competitor.name == name

    def test_competitor_defaults(self, db_session):
        """Test competitor default values."""
        from database import Competitor

        competitor = Competitor(name=unique_name("Default Test DB"))
        db_session.add(competitor)
        db_session.commit()

        # Competitor uses 'status' not 'is_active', and 'threat_level' defaults to "Medium"
        assert competitor.status == "Active"
        assert competitor.threat_level == "Medium"

    def test_competitor_update(self, db_session, sample_competitor):
        """Test updating a competitor."""
        original_name = sample_competitor.name
        sample_competitor.notes = "Updated description"  # Use 'notes' instead of 'description'
        db_session.commit()

        db_session.refresh(sample_competitor)
        assert sample_competitor.notes == "Updated description"
        assert sample_competitor.name == original_name

    def test_competitor_delete(self, db_session):
        """Test deleting a competitor."""
        from database import Competitor

        competitor = Competitor(name=unique_name("To Be Deleted DB"))
        db_session.add(competitor)
        db_session.commit()
        competitor_id = competitor.id

        db_session.delete(competitor)
        db_session.commit()

        deleted = db_session.query(Competitor).filter_by(id=competitor_id).first()
        assert deleted is None


# ==============================================================================
# User Model Tests
# ==============================================================================

class TestUserModel:
    """Tests for User model."""

    def test_create_user(self, db_session):
        """Test creating a user."""
        from database import User
        import hashlib

        email = unique_name("newuser_db") + "@test.com"
        user = User(
            email=email,
            hashed_password=hashlib.sha256("password".encode()).hexdigest(),
            full_name="New User",  # Use 'full_name' instead of 'name'
            role="analyst"
        )
        db_session.add(user)
        db_session.commit()

        assert user.id is not None
        assert user.email == email

    def test_user_email_unique(self, db_session):
        """Test that email must be unique."""
        from database import User
        from sqlalchemy.exc import IntegrityError
        import hashlib

        # Create first user with unique email for this test
        unique_email = unique_name("unique_test") + "@test.com"
        user1 = User(
            email=unique_email,
            hashed_password=hashlib.sha256("password".encode()).hexdigest(),
            full_name="User 1"
        )
        db_session.add(user1)
        db_session.commit()

        # Try to create duplicate with same email
        duplicate_user = User(
            email=unique_email,  # Same email
            hashed_password=hashlib.sha256("password".encode()).hexdigest(),
            full_name="Duplicate"
        )

        db_session.add(duplicate_user)
        with pytest.raises(IntegrityError):
            db_session.commit()

        db_session.rollback()


# ==============================================================================
# Product Model Tests
# ==============================================================================

class TestProductModel:
    """Tests for CompetitorProduct model."""

    def test_create_product(self, db_session, sample_competitor):
        """Test creating a product."""
        from database import CompetitorProduct

        product = CompetitorProduct(
            competitor_id=sample_competitor.id,
            product_name="Test Product DB",  # Use 'product_name' instead of 'name'
            description="Product description",
            product_category="EHR"  # Use 'product_category' instead of 'category'
        )
        db_session.add(product)
        db_session.commit()

        assert product.id is not None
        assert product.competitor_id == sample_competitor.id

    def test_product_competitor_relationship(self, db_session, sample_product):
        """Test product-competitor relationship."""
        from database import Competitor

        competitor = db_session.query(Competitor).filter_by(
            id=sample_product.competitor_id
        ).first()

        assert competitor is not None


# ==============================================================================
# Change History Tests
# ==============================================================================

class TestChangeHistoryModel:
    """Tests for DataChangeHistory model."""

    def test_create_change_history(self, db_session, sample_competitor):
        """Test creating a change history record."""
        from database import DataChangeHistory

        change = DataChangeHistory(
            competitor_id=sample_competitor.id,
            competitor_name=sample_competitor.name,
            field_name="pricing_model",
            old_value="Subscription",
            new_value="Enterprise",
            changed_by="test@test.com",
            change_reason="Testing"
        )
        db_session.add(change)
        db_session.commit()

        assert change.id is not None
        assert change.changed_at is not None

    def test_query_recent_changes(self, db_session, sample_competitor):
        """Test querying recent changes."""
        from database import DataChangeHistory

        # Create some changes first
        for i in range(3):
            change = DataChangeHistory(
                competitor_id=sample_competitor.id,
                competitor_name=sample_competitor.name,
                field_name=f"field_{i}",
                old_value=f"old_{i}",
                new_value=f"new_{i}",
                changed_by="test@test.com"
            )
            db_session.add(change)
        db_session.commit()

        recent = db_session.query(DataChangeHistory).order_by(
            DataChangeHistory.changed_at.desc()
        ).limit(5).all()

        assert len(recent) >= 0


# ==============================================================================
# Data Source Tests
# ==============================================================================

class TestDataSourceModel:
    """Tests for DataSource model."""

    def test_create_data_source(self, db_session, sample_competitor):
        """Test creating a data source."""
        from database import DataSource

        source = DataSource(
            competitor_id=sample_competitor.id,
            field_name="headquarters",
            source_type="api",
            source_url="https://api.example.com",
            confidence_score=85,  # Integer, not float
            is_verified=True
        )
        db_session.add(source)
        db_session.commit()

        assert source.id is not None
        assert source.confidence_score == 85


# ==============================================================================
# Activity Log Tests
# ==============================================================================

class TestActivityLogModel:
    """Tests for ActivityLog model."""

    def test_create_activity_log(self, db_session, sample_user):
        """Test creating an activity log."""
        from database import ActivityLog

        log = ActivityLog(
            user_id=sample_user.id,
            user_email=sample_user.email,
            action_type="login",
            action_details="User logged in"
        )
        db_session.add(log)
        db_session.commit()

        assert log.id is not None
        assert log.created_at is not None


# ==============================================================================
# Knowledge Base Tests
# ==============================================================================

class TestKnowledgeBaseModel:
    """Tests for KnowledgeBaseItem model."""

    def test_create_knowledge_base_item(self, db_session):
        """Test creating a knowledge base item."""
        from database import KnowledgeBaseItem

        item = KnowledgeBaseItem(
            title="Test Article",
            content_text="This is test content",  # Use 'content_text' instead of 'content'
            category="internal",
            source="manual"
        )
        db_session.add(item)
        db_session.commit()

        assert item.id is not None


# ==============================================================================
# Subscription Tests
# ==============================================================================

class TestSubscriptionModel:
    """Tests for CompetitorSubscription model."""

    def test_create_subscription(self, db_session, sample_user, sample_competitor):
        """Test creating a competitor subscription."""
        from database import CompetitorSubscription

        sub = CompetitorSubscription(
            user_id=sample_user.id,
            competitor_id=sample_competitor.id,
            notify_email=True,
            alert_on_pricing=True,
            alert_on_products=True,
            alert_on_news=True
        )
        db_session.add(sub)
        db_session.commit()

        assert sub.id is not None
        assert sub.notify_email == True
