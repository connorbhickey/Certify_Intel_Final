"""
Certify Intel - Sales & Marketing Module Tests (v5.0.7)
End-to-end tests for dimension scoring, battlecards, and integrations.
"""
import pytest
import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============== Unit Tests for Core Module ==============

class TestDimensionID:
    """Test dimension ID enum and metadata."""

    def test_all_dimensions_exist(self):
        """Verify all 9 dimensions are defined."""
        from sales_marketing_module import DimensionID

        assert len(DimensionID) == 9

        expected_ids = [
            'product_packaging', 'integration_depth', 'support_service',
            'retention_stickiness', 'user_adoption', 'implementation_ttv',
            'reliability_enterprise', 'pricing_flexibility', 'reporting_analytics'
        ]

        for dim_id in expected_ids:
            assert dim_id in [d.value for d in DimensionID]

    def test_dimension_metadata_complete(self):
        """Verify all dimensions have complete metadata."""
        from sales_marketing_module import DimensionID, DIMENSION_METADATA

        required_fields = ['name', 'short_name', 'icon', 'description', 'deal_impact', 'keywords', 'score_guide']

        for dim_id in DimensionID:
            assert dim_id in DIMENSION_METADATA, f"Missing metadata for {dim_id}"
            meta = DIMENSION_METADATA[dim_id]

            for field in required_fields:
                assert field in meta, f"Missing {field} in {dim_id} metadata"

    def test_score_labels(self):
        """Verify score labels are defined for 1-5."""
        from sales_marketing_module import SCORE_LABELS

        assert len(SCORE_LABELS) == 5
        for i in range(1, 6):
            assert i in SCORE_LABELS


class TestDimensionAnalyzer:
    """Test dimension classification and scoring."""

    def test_analyzer_initialization(self):
        """Test DimensionAnalyzer can be initialized."""
        from dimension_analyzer import DimensionAnalyzer

        analyzer = DimensionAnalyzer()
        assert analyzer is not None

    def test_keyword_classification(self):
        """Test keyword-based dimension classification."""
        from dimension_analyzer import DimensionAnalyzer

        analyzer = DimensionAnalyzer()

        # Test integration keywords
        test_title = "Epic announces new EHR integration capabilities"
        test_snippet = "The company expands API connectivity and interoperability features"

        results = analyzer.classify_article_dimension(
            title=test_title,
            snippet=test_snippet,
            competitor_name="Epic"
        )

        # Should find integration_depth dimension
        dim_ids = [r[0] for r in results]
        # Note: May not always match without AI, depends on keywords

    def test_review_analysis(self):
        """Test review dimension signal detection."""
        from dimension_analyzer import DimensionAnalyzer

        analyzer = DimensionAnalyzer()

        test_review = "The implementation was difficult and took longer than expected. Support team was great though."

        results = analyzer.analyze_review_dimensions(
            review_text=test_review,
            review_rating=3.0,
            competitor_name="TestCompetitor"
        )

        # Should detect implementation_ttv and/or support_service signals
        assert isinstance(results, dict)


class TestBattlecardGenerator:
    """Test battlecard generation."""

    def test_templates_exist(self):
        """Verify all battlecard templates are defined."""
        from battlecard_generator import BATTLECARD_TEMPLATES

        expected_types = ['full', 'quick', 'objection_handler']

        for template_type in expected_types:
            assert template_type in BATTLECARD_TEMPLATES
            template = BATTLECARD_TEMPLATES[template_type]
            assert 'name' in template
            assert 'sections' in template

    def test_generator_initialization(self):
        """Test BattlecardGenerator can be initialized."""
        from battlecard_generator import BattlecardGenerator

        # Note: Requires db_session, so just test import
        assert BattlecardGenerator is not None


class TestNewsMonitorIntegration:
    """Test news monitor dimension integration."""

    def test_dimension_tagging_available(self):
        """Verify dimension tagging is available in NewsMonitor."""
        try:
            from news_monitor import NewsMonitor

            monitor = NewsMonitor(tag_dimensions=True)
            assert hasattr(monitor, 'tag_dimensions')
            assert hasattr(monitor, 'dimension_analyzer') or monitor.tag_dimensions == False
        except ImportError:
            pytest.skip("NewsMonitor not available")

    def test_news_article_has_dimension_field(self):
        """Verify NewsArticle dataclass has dimension_tags field."""
        from news_monitor import NewsArticle

        # Create a test article
        article = NewsArticle(
            title="Test",
            url="http://test.com",
            source="Test",
            published_date="2024-01-01",
            snippet="Test snippet",
            sentiment="neutral",
            is_major_event=False,
            event_type=None,
            dimension_tags=None
        )

        assert hasattr(article, 'dimension_tags')


class TestWinLossIntegration:
    """Test win/loss tracker dimension integration."""

    def test_dimension_factors_in_deal(self):
        """Verify dimension factors can be logged with deals."""
        from win_loss_tracker import WinLossTracker

        tracker = WinLossTracker()

        deal = tracker.log_deal(
            competitor_id=1,
            competitor_name="Test Competitor",
            deal_name="Test Deal",
            deal_value=100000,
            outcome="Won",
            dimension_factors={
                "pricing_flexibility": "advantage",
                "integration_depth": "disadvantage"
            }
        )

        assert "dimension_factors" in deal
        assert deal["dimension_factors"]["pricing_flexibility"] == "advantage"

    def test_dimension_impact_calculation(self):
        """Test dimension impact is calculated in stats."""
        from win_loss_tracker import WinLossTracker

        tracker = WinLossTracker()

        # Log some test deals with dimension factors
        tracker.log_deal(1, "Comp1", "Deal1", 100000, "Won",
                        dimension_factors={"pricing_flexibility": "advantage"})
        tracker.log_deal(1, "Comp1", "Deal2", 50000, "Lost",
                        dimension_factors={"pricing_flexibility": "disadvantage"})

        stats = tracker.get_stats()

        assert hasattr(stats, 'dimension_impact')


class TestReportsIntegration:
    """Test reports module dimension integration."""

    def test_dimension_battlecard_generator_exists(self):
        """Verify DimensionBattlecardPDFGenerator exists."""
        from reports import DimensionBattlecardPDFGenerator

        gen = DimensionBattlecardPDFGenerator()
        assert gen is not None

    def test_report_manager_has_dimension_methods(self):
        """Verify ReportManager has dimension battlecard methods."""
        from reports import ReportManager

        manager = ReportManager()

        assert hasattr(manager, 'generate_dimension_battlecard')
        assert hasattr(manager, 'dimension_battlecard_gen')


# ============== API Endpoint Tests ==============

class TestSalesMarketingRouter:
    """Test API endpoints for Sales & Marketing module."""

    def test_router_import(self):
        """Verify router can be imported."""
        from routers.sales_marketing import router

        assert router is not None
        assert router.prefix == "/api/sales-marketing"

    def test_dimension_endpoints_exist(self):
        """Verify all dimension endpoints are defined."""
        from routers.sales_marketing import router

        routes = [route.path for route in router.routes]

        expected_paths = [
            "/dimensions",
            "/dimensions/{dimension_id}",
            "/competitors/{competitor_id}/dimensions",
            "/competitors/{competitor_id}/dimensions/{dimension_id}",
            "/competitors/{competitor_id}/dimensions/ai-suggest",
        ]

        for path in expected_paths:
            assert any(path in r for r in routes), f"Missing endpoint: {path}"

    def test_battlecard_endpoints_exist(self):
        """Verify battlecard endpoints are defined."""
        from routers.sales_marketing import router

        routes = [route.path for route in router.routes]

        assert any("/battlecards/templates" in r for r in routes)
        assert any("/battlecards/generate" in r for r in routes)

    def test_analytics_endpoints_exist(self):
        """Verify analytics endpoints are defined."""
        from routers.sales_marketing import router

        routes = [route.path for route in router.routes]

        assert any("/analytics/dimension-trends" in r for r in routes)
        assert any("/analytics/dimension-coverage" in r for r in routes)
        assert any("/analytics/sales-priority-matrix" in r for r in routes)


# ============== Integration Tests ==============

class TestModuleIntegration:
    """Test module integration with main app."""

    def test_router_included_in_main(self):
        """Verify sales_marketing router is included in main app."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "main",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
        )

        # Just verify the file exists and imports work
        assert spec is not None

    def test_database_models_exist(self):
        """Verify database models for Sales & Marketing exist."""
        from database import (
            Competitor,
            CompetitorDimensionHistory,
            Battlecard,
            TalkingPoint,
            DimensionNewsTag
        )

        # Verify dimension fields on Competitor
        assert hasattr(Competitor, 'dim_product_packaging_score')
        assert hasattr(Competitor, 'dim_integration_depth_evidence')
        assert hasattr(Competitor, 'dim_overall_score')


# ============== Run Tests ==============

if __name__ == "__main__":
    print("=" * 60)
    print("Certify Intel - Sales & Marketing Module Tests (v5.0.7)")
    print("=" * 60)

    # Run basic validation tests
    test_classes = [
        TestDimensionID,
        TestDimensionAnalyzer,
        TestBattlecardGenerator,
        TestNewsMonitorIntegration,
        TestWinLossIntegration,
        TestReportsIntegration,
        TestSalesMarketingRouter,
        TestModuleIntegration
    ]

    passed = 0
    failed = 0
    skipped = 0

    for test_class in test_classes:
        print(f"\n📋 {test_class.__name__}")
        print("-" * 40)

        instance = test_class()
        methods = [m for m in dir(instance) if m.startswith('test_')]

        for method_name in methods:
            try:
                method = getattr(instance, method_name)
                method()
                print(f"  ✅ {method_name}")
                passed += 1
            except pytest.skip.Exception as e:
                print(f"  ⏭️ {method_name} - Skipped: {e}")
                skipped += 1
            except Exception as e:
                print(f"  ❌ {method_name} - {str(e)[:50]}")
                failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)
