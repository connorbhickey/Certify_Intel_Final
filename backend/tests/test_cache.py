"""
Certify Intel - Cache Layer Tests
Tests for InMemoryCache TTL, cleanup, max entries, and the get_cache singleton.
Also tests TaskService for background AI task management.
"""
import pytest
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pytestmark = pytest.mark.timeout(10)


# ==============================================================================
# InMemoryCache Tests
# ==============================================================================

class TestInMemoryCache:
    """Tests for the in-memory cache backend."""

    def test_set_and_get(self):
        from cache import InMemoryCache
        cache = InMemoryCache()
        cache.set("key1", {"data": "value1"})
        assert cache.get("key1") == {"data": "value1"}

    def test_get_missing_key(self):
        from cache import InMemoryCache
        cache = InMemoryCache()
        assert cache.get("nonexistent") is None

    def test_ttl_expiry(self):
        from cache import InMemoryCache
        cache = InMemoryCache()
        cache.set("short_ttl", "value", ttl=1)
        assert cache.get("short_ttl") == "value"
        time.sleep(1.1)
        assert cache.get("short_ttl") is None

    def test_no_ttl_persists(self):
        from cache import InMemoryCache
        cache = InMemoryCache()
        cache.set("permanent", "value", ttl=0)
        assert cache.get("permanent") == "value"

    def test_delete(self):
        from cache import InMemoryCache
        cache = InMemoryCache()
        cache.set("to_delete", "value")
        cache.delete("to_delete")
        assert cache.get("to_delete") is None

    def test_delete_nonexistent(self):
        from cache import InMemoryCache
        cache = InMemoryCache()
        cache.delete("nonexistent")  # Should not raise

    def test_clear(self):
        from cache import InMemoryCache
        cache = InMemoryCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_max_entries_eviction(self):
        from cache import InMemoryCache
        cache = InMemoryCache(max_entries=5)
        for i in range(10):
            cache.set(f"key_{i}", f"val_{i}", ttl=60)
        # After cleanup, should be under max_entries
        # Some early keys should have been evicted
        remaining = [k for k in [f"key_{i}" for i in range(10)] if cache.get(k)]
        assert len(remaining) <= 5

    def test_keys_no_pattern(self):
        from cache import InMemoryCache
        cache = InMemoryCache()
        cache.set("alpha", 1)
        cache.set("beta", 2)
        keys = cache.keys()
        assert "alpha" in keys
        assert "beta" in keys

    def test_keys_with_prefix_pattern(self):
        from cache import InMemoryCache
        cache = InMemoryCache()
        cache.set("cache:comp:1", "data1")
        cache.set("cache:comp:2", "data2")
        cache.set("other:key", "data3")
        keys = cache.keys("cache:comp:*")
        assert len(keys) == 2
        assert "other:key" not in keys

    def test_stores_complex_types(self):
        from cache import InMemoryCache
        cache = InMemoryCache()
        data = {"list": [1, 2, 3], "nested": {"a": True}}
        cache.set("complex", data)
        assert cache.get("complex") == data

    def test_overwrite_existing_key(self):
        from cache import InMemoryCache
        cache = InMemoryCache()
        cache.set("key", "old")
        cache.set("key", "new")
        assert cache.get("key") == "new"


# ==============================================================================
# get_cache Singleton Tests
# ==============================================================================

class TestGetCache:
    """Tests for the cache singleton factory."""

    def test_default_is_in_memory(self):
        from cache import get_cache, reset_cache, InMemoryCache
        reset_cache()
        os.environ.pop("REDIS_ENABLED", None)
        cache = get_cache()
        assert isinstance(cache, InMemoryCache)
        reset_cache()

    def test_singleton_returns_same_instance(self):
        from cache import get_cache, reset_cache
        reset_cache()
        c1 = get_cache()
        c2 = get_cache()
        assert c1 is c2
        reset_cache()

    def test_redis_fallback_to_memory(self):
        """When REDIS_ENABLED=true but Redis is unavailable, falls back to InMemoryCache."""
        from cache import get_cache, reset_cache, InMemoryCache
        reset_cache()
        os.environ["REDIS_ENABLED"] = "true"
        os.environ["REDIS_URL"] = "redis://localhost:59999/0"  # invalid port
        cache = get_cache()
        assert isinstance(cache, InMemoryCache)
        os.environ.pop("REDIS_ENABLED", None)
        os.environ.pop("REDIS_URL", None)
        reset_cache()


# ==============================================================================
# TaskService Tests
# ==============================================================================

class TestTaskService:
    """Tests for the background AI task service."""

    def test_create_task(self):
        from services.task_service import TaskService
        svc = TaskService()
        task = svc.create("t1", user_id=1, page_context="dashboard", task_type="summary")
        assert task["status"] == "running"
        assert task["user_id"] == 1
        assert task["page_context"] == "dashboard"
        assert task["result"] is None

    def test_get_task(self):
        from services.task_service import TaskService
        svc = TaskService()
        svc.create("t1", user_id=1)
        assert svc.get("t1") is not None
        assert svc.get("nonexistent") is None

    def test_update_task(self):
        from services.task_service import TaskService
        svc = TaskService()
        svc.create("t1", user_id=1)
        svc.update("t1", status="completed", result={"data": "ok"})
        task = svc.get("t1")
        assert task["status"] == "completed"
        assert task["result"] == {"data": "ok"}

    def test_update_nonexistent_returns_none(self):
        from services.task_service import TaskService
        svc = TaskService()
        assert svc.update("bad_id", status="failed") is None

    def test_mark_completed_success(self):
        from services.task_service import TaskService
        svc = TaskService()
        svc.create("t1", user_id=1)
        svc.mark_completed("t1", result={"summary": "done"})
        task = svc.get("t1")
        assert task["status"] == "completed"
        assert task["completed_at"] is not None
        assert task["error"] is None

    def test_mark_completed_failure(self):
        from services.task_service import TaskService
        svc = TaskService()
        svc.create("t1", user_id=1)
        svc.mark_completed("t1", error="Something went wrong")
        task = svc.get("t1")
        assert task["status"] == "failed"
        assert task["error"] == "Something went wrong"

    def test_get_pending_for_user(self):
        from services.task_service import TaskService
        svc = TaskService()
        svc.create("t1", user_id=1, task_type="summary")
        svc.create("t2", user_id=1, task_type="analysis")
        svc.create("t3", user_id=2, task_type="other")
        svc.mark_completed("t2", result={"data": "ok"})

        pending = svc.get_pending_for_user(1)
        assert len(pending) == 2  # t1 (running) + t2 (completed, unread)
        task_ids = [p["task_id"] for p in pending]
        assert "t1" in task_ids
        assert "t2" in task_ids
        assert "t3" not in task_ids

    def test_prune_stale_tasks(self):
        from services.task_service import TaskService
        from datetime import datetime, timedelta
        svc = TaskService(prune_after_hours=0)  # immediate prune

        svc.create("t1", user_id=1)
        svc.mark_completed("t1", result="done")
        task = svc.get("t1")
        # Mark as read with a timestamp in the past
        task["read_at"] = (datetime.utcnow() - timedelta(seconds=5)).isoformat()

        svc.prune()
        assert svc.get("t1") is None

    def test_unread_tasks_not_pruned(self):
        from services.task_service import TaskService
        svc = TaskService(prune_after_hours=0)

        svc.create("t1", user_id=1)
        svc.mark_completed("t1", result="done")
        # Don't set read_at

        svc.prune()
        assert svc.get("t1") is not None

    def test_count(self):
        from services.task_service import TaskService
        svc = TaskService()
        assert svc.count() == 0
        svc.create("t1", user_id=1)
        svc.create("t2", user_id=1)
        assert svc.count() == 2

    def test_tasks_property_backward_compatible(self):
        """The .tasks property should give direct dict access for backward compat."""
        from services.task_service import TaskService
        svc = TaskService()
        svc.create("t1", user_id=1)
        # Direct dict mutation (how main.py currently works)
        svc.tasks["t1"]["status"] = "completed"
        assert svc.get("t1")["status"] == "completed"
