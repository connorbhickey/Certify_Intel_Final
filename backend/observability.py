"""
Certify Intel v7.0 - Langfuse Observability Module
===================================================

AI observability integration for tracing, cost tracking, and debugging.

Features:
- Request tracing with full context
- Cost tracking per user/agent/model
- Performance metrics (latency p50/p95/p99)
- Error tracking and debugging
- Prompt management and versioning

Setup:
    1. Start Langfuse: docker-compose up -d
    2. Access dashboard: http://localhost:3000
    3. Create API keys in Settings
    4. Set environment variables:
       - LANGFUSE_PUBLIC_KEY
       - LANGFUSE_SECRET_KEY
       - LANGFUSE_HOST (default: http://localhost:3000)
       - ENABLE_LANGFUSE=true

Usage:
    from observability import trace_agent_request, get_langfuse

    # Decorator for automatic tracing
    @trace_agent_request("dashboard")
    async def process_dashboard_query(query: str) -> str:
        ...

    # Manual tracing
    langfuse = get_langfuse()
    trace = langfuse.trace(name="custom_operation")
"""

import os
import logging
import functools
import time
from typing import Optional, Dict, Any, Callable
from contextlib import asynccontextmanager
from datetime import datetime

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

LANGFUSE_ENABLED = os.getenv("ENABLE_LANGFUSE", "false").lower() == "true"
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")


# =============================================================================
# LANGFUSE CLIENT
# =============================================================================

_langfuse_client = None


class LangfuseHTTPClient:
    """Lightweight Langfuse HTTP client for Python 3.14+ compatibility.

    The official langfuse SDK uses pydantic.v1 which is broken on Python 3.14.
    This client sends traces/scores via the Langfuse REST API directly.
    """

    def __init__(self, public_key: str, secret_key: str, host: str):
        import requests as _requests
        self._session = _requests.Session()
        self._session.auth = (public_key, secret_key)
        self._host = host.rstrip("/")
        self._batch = []

    def _event(self, event_type: str, body: dict):
        """Add a batch event with required top-level id and timestamp."""
        import uuid
        self._batch.append({
            "id": str(uuid.uuid4()),
            "type": event_type,
            "timestamp": datetime.now(tz=__import__('datetime').timezone.utc).isoformat(),
            "body": body,
        })

    def trace(self, name: str, user_id=None, session_id=None,
              input=None, output=None, metadata=None, level=None):
        """Create a trace event."""
        import uuid
        trace_id = str(uuid.uuid4())
        body = {
            "id": trace_id,
            "name": name,
            "timestamp": datetime.now(tz=__import__('datetime').timezone.utc).isoformat(),
        }
        if user_id:
            body["userId"] = str(user_id)
        if session_id:
            body["sessionId"] = str(session_id)
        if input:
            body["input"] = input
        if output:
            body["output"] = output
        if metadata:
            body["metadata"] = metadata
        self._event("trace-create", body)
        return _TraceHandle(trace_id, self)

    def score(self, name: str, value: float, comment: str = "",
              data_type: str = "NUMERIC", trace_id: str = None):
        """Log a score event."""
        import uuid
        body = {
            "id": str(uuid.uuid4()),
            "name": name,
            "value": value,
            "dataType": data_type,
            "timestamp": datetime.now(tz=__import__('datetime').timezone.utc).isoformat(),
        }
        if comment:
            body["comment"] = comment
        if trace_id:
            body["traceId"] = trace_id
        self._event("score-create", body)

    def flush(self):
        """Send all batched events to Langfuse."""
        if not self._batch:
            return
        try:
            resp = self._session.post(
                f"{self._host}/api/public/ingestion",
                json={"batch": self._batch},
                timeout=5
            )
            if resp.status_code not in (200, 207):
                logger.warning(f"Langfuse ingestion returned {resp.status_code}: {resp.text[:200]}")
            self._batch.clear()
        except Exception as e:
            logger.warning(f"Langfuse flush failed: {e}")
            self._batch.clear()

    def shutdown(self):
        """Flush remaining events and close session."""
        self.flush()
        self._session.close()

    def get_prompt(self, name, version=None):
        """Fetch a prompt from Langfuse prompt management."""
        try:
            url = f"{self._host}/api/public/v2/prompts/{name}"
            if version:
                url += f"?version={version}"
            resp = self._session.get(url, timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                return type("Prompt", (), {"prompt": data.get("prompt", "")})()
        except Exception as e:
            logger.warning(f"Langfuse get_prompt failed: {e}")
        return None


class _TraceHandle:
    """Handle for updating a trace after creation."""

    def __init__(self, trace_id: str, client: LangfuseHTTPClient):
        self._id = trace_id
        self._client = client

    @property
    def id(self):
        return self._id

    def update(self, output=None, level=None, metadata=None, **kwargs):
        body = {"id": self._id}
        if output:
            body["output"] = output
        if metadata:
            body["metadata"] = metadata
        self._client._event("trace-create", body)

    def generation(self, name=None, model=None, input=None, **kwargs):
        return _GenerationHandle(self._id, name, model, input, self._client)

    def span(self, **kwargs):
        return self


class _GenerationHandle:
    """Handle for LLM generation spans."""

    def __init__(self, trace_id, name, model, input_data, client):
        import uuid
        self._id = str(uuid.uuid4())
        self._trace_id = trace_id
        self._client = client
        body = {
            "id": self._id,
            "traceId": trace_id,
            "type": "GENERATION",
            "name": name or "llm_call",
            "model": model,
            "startTime": datetime.now(tz=__import__('datetime').timezone.utc).isoformat(),
        }
        if input_data:
            body["input"] = str(input_data)[:500]
        client._event("generation-create", body)

    def end(self, output=None, usage=None, metadata=None,
            level=None, status_message=None, **kwargs):
        body = {
            "id": self._id,
            "traceId": self._trace_id,
            "endTime": datetime.now(tz=__import__('datetime').timezone.utc).isoformat(),
        }
        if output:
            body["output"] = str(output)[:500]
        if usage:
            body["usage"] = usage
        if metadata:
            body["metadata"] = metadata
        if level:
            body["level"] = level
        if status_message:
            body["statusMessage"] = status_message
        self._client._event("generation-update", body)


def get_langfuse():
    """
    Get or create Langfuse client.

    Tries official SDK first, falls back to lightweight HTTP client
    for Python 3.14+ compatibility.
    Returns None if Langfuse is disabled or not configured.
    """
    global _langfuse_client

    if not LANGFUSE_ENABLED:
        return None

    if not LANGFUSE_PUBLIC_KEY or not LANGFUSE_SECRET_KEY:
        logger.warning("Langfuse enabled but API keys not set")
        return None

    if _langfuse_client is None:
        # Try official SDK first
        try:
            from langfuse import Langfuse

            _langfuse_client = Langfuse(
                public_key=LANGFUSE_PUBLIC_KEY,
                secret_key=LANGFUSE_SECRET_KEY,
                host=LANGFUSE_HOST,
                flush_at=10,
                flush_interval=5,
                timeout=2
            )
            logger.info(f"Langfuse SDK client initialized (host: {LANGFUSE_HOST})")

        except Exception as sdk_err:
            # Fallback to lightweight HTTP client (Python 3.14 compat)
            logger.info(f"Langfuse SDK unavailable ({type(sdk_err).__name__}), using HTTP client")
            try:
                _langfuse_client = LangfuseHTTPClient(
                    public_key=LANGFUSE_PUBLIC_KEY,
                    secret_key=LANGFUSE_SECRET_KEY,
                    host=LANGFUSE_HOST,
                )
                logger.info(f"Langfuse HTTP client initialized (host: {LANGFUSE_HOST})")
            except Exception as e:
                logger.error(f"Failed to initialize Langfuse: {e}")
                return None

    return _langfuse_client


def shutdown_langfuse():
    """Flush and shutdown Langfuse client."""
    global _langfuse_client

    if _langfuse_client:
        try:
            _langfuse_client.flush()
            _langfuse_client.shutdown()
            logger.info("Langfuse client shut down")
        except Exception as e:
            logger.error(f"Error shutting down Langfuse: {e}")
        finally:
            _langfuse_client = None


# =============================================================================
# TRACING DECORATORS
# =============================================================================

def trace_agent_request(agent_type: str):
    """
    Decorator to trace agent requests with Langfuse.

    Captures:
    - Input query
    - Output response
    - Latency
    - Errors
    - Model used
    - Cost

    Usage:
        @trace_agent_request("dashboard")
        async def process_query(query: str, user_id: str) -> dict:
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            langfuse = get_langfuse()

            # If Langfuse disabled, just run the function
            if langfuse is None:
                return await func(*args, **kwargs)

            # Extract metadata from kwargs
            user_id = kwargs.get("user_id")
            session_id = kwargs.get("session_id")
            query = kwargs.get("query") or kwargs.get("user_input") or (args[0] if args else "")

            # Start trace
            trace = langfuse.trace(
                name=f"{agent_type}_request",
                user_id=user_id,
                session_id=session_id,
                input={"query": str(query)[:1000]},  # Truncate for logging
                metadata={"agent_type": agent_type}
            )

            start_time = time.time()
            error_occurred = None

            try:
                # Run the actual function
                result = await func(*args, **kwargs)

                # Extract output for logging
                if isinstance(result, dict):
                    output = {
                        "response": str(result.get("response", result.get("text", "")))[:1000],
                        "model": result.get("model", "unknown"),
                        "cost_usd": result.get("cost_usd", 0)
                    }
                else:
                    output = {"response": str(result)[:1000]}

                trace.update(
                    output=output,
                    level="DEFAULT"
                )

                return result

            except Exception as e:
                error_occurred = str(e)
                trace.update(
                    output={"error": error_occurred},
                    level="ERROR"
                )
                raise

            finally:
                # Log timing
                latency_ms = int((time.time() - start_time) * 1000)
                trace.update(
                    metadata={
                        "agent_type": agent_type,
                        "latency_ms": latency_ms,
                        "error": error_occurred
                    }
                )

        return wrapper
    return decorator


def trace_llm_call(model: str, task_type: str):
    """
    Decorator to trace individual LLM calls.

    Usage:
        @trace_llm_call("gemini-3-flash-preview", "summarization")
        async def summarize(text: str) -> str:
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            langfuse = get_langfuse()

            if langfuse is None:
                return await func(*args, **kwargs)

            # Get parent trace if available
            parent_trace = kwargs.pop("_langfuse_trace", None)

            # Create generation span
            generation = None
            if parent_trace:
                generation = parent_trace.generation(
                    name=f"llm_{task_type}",
                    model=model,
                    input=str(args[0])[:500] if args else "no input"
                )

            start_time = time.time()

            try:
                result = await func(*args, **kwargs)

                if generation:
                    # Extract token counts and cost
                    if isinstance(result, dict):
                        generation.end(
                            output=str(result.get("response", result))[:500],
                            usage={
                                "input": result.get("tokens_input", 0),
                                "output": result.get("tokens_output", 0),
                                "total": result.get("tokens_input", 0) + result.get("tokens_output", 0)
                            },
                            metadata={
                                "cost_usd": result.get("cost_usd", 0),
                                "latency_ms": int((time.time() - start_time) * 1000)
                            }
                        )
                    else:
                        generation.end(output=str(result)[:500])

                return result

            except Exception as e:
                if generation:
                    generation.end(
                        level="ERROR",
                        status_message=str(e)
                    )
                raise

        return wrapper
    return decorator


# =============================================================================
# CONTEXT MANAGERS
# =============================================================================

@asynccontextmanager
async def trace_operation(
    name: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Async context manager for tracing operations.

    Usage:
        async with trace_operation("vector_search", user_id="user123") as trace:
            results = await vector_store.search(query)
            trace.update(output={"result_count": len(results)})
    """
    langfuse = get_langfuse()

    if langfuse is None:
        # Provide a no-op trace object
        class NoOpTrace:
            def update(self, **kwargs): pass
            def span(self, **kwargs): return self
            def end(self, **kwargs): pass

        yield NoOpTrace()
        return

    trace = langfuse.trace(
        name=name,
        user_id=user_id,
        session_id=session_id,
        metadata=metadata or {}
    )

    start_time = time.time()

    try:
        yield trace
        trace.update(
            level="DEFAULT",
            metadata={
                **(metadata or {}),
                "latency_ms": int((time.time() - start_time) * 1000)
            }
        )
    except Exception as e:
        trace.update(
            level="ERROR",
            output={"error": str(e)},
            metadata={
                **(metadata or {}),
                "latency_ms": int((time.time() - start_time) * 1000)
            }
        )
        raise


# =============================================================================
# COST TRACKING
# =============================================================================

def log_ai_cost(
    model: str,
    agent_type: str,
    task_type: str,
    tokens_input: int,
    tokens_output: int,
    cost_usd: float,
    latency_ms: int,
    user_id: Optional[str] = None
):
    """
    Log AI cost to Langfuse for dashboard visualization.

    This creates a score event that appears in the Langfuse analytics.
    """
    langfuse = get_langfuse()

    if langfuse is None:
        return

    try:
        # Log as a score for cost tracking
        langfuse.score(
            name="ai_cost",
            value=cost_usd,
            comment=f"{model} - {task_type}",
            data_type="NUMERIC"
        )

        # Log latency as separate score
        langfuse.score(
            name="latency_ms",
            value=latency_ms,
            comment=f"{model} - {task_type}",
            data_type="NUMERIC"
        )

    except Exception as e:
        logger.warning(f"Failed to log AI cost to Langfuse: {e}")


# =============================================================================
# PROMPT MANAGEMENT
# =============================================================================

def get_prompt(
    name: str,
    version: Optional[int] = None,
    fallback: str = ""
) -> str:
    """
    Get prompt from Langfuse prompt management.

    Enables A/B testing and prompt versioning.

    Usage:
        prompt = get_prompt("dashboard_summary", version=2)
    """
    langfuse = get_langfuse()

    if langfuse is None:
        return fallback

    try:
        prompt = langfuse.get_prompt(name, version=version)
        return prompt.prompt if prompt else fallback
    except Exception as e:
        logger.warning(f"Failed to get prompt '{name}' from Langfuse: {e}")
        return fallback


# =============================================================================
# HEALTH CHECK
# =============================================================================

async def check_langfuse_health() -> Dict[str, Any]:
    """
    Check Langfuse connectivity and health.

    Returns status dict with connection info.
    """
    result = {
        "enabled": LANGFUSE_ENABLED,
        "host": LANGFUSE_HOST,
        "connected": False,
        "error": None
    }

    if not LANGFUSE_ENABLED:
        result["error"] = "Langfuse disabled via ENABLE_LANGFUSE"
        return result

    if not LANGFUSE_PUBLIC_KEY or not LANGFUSE_SECRET_KEY:
        result["error"] = "API keys not configured"
        return result

    try:
        langfuse = get_langfuse()
        if langfuse:
            # Try to flush to verify connection
            langfuse.flush()
            result["connected"] = True
    except Exception as e:
        result["error"] = str(e)

    return result


# =============================================================================
# CLI FOR TESTING
# =============================================================================

if __name__ == "__main__":
    import asyncio

    async def test():
        print("Langfuse Observability Test")
        print("=" * 60)

        # Check health
        health = await check_langfuse_health()
        print(f"\nConfiguration:")
        print(f"  Enabled: {health['enabled']}")
        print(f"  Host: {health['host']}")
        print(f"  Connected: {health['connected']}")
        if health['error']:
            print(f"  Error: {health['error']}")

        if not health['connected']:
            print("\nTo enable Langfuse:")
            print("  1. Start Langfuse: docker-compose up -d")
            print("  2. Access: http://localhost:3000")
            print("  3. Create API keys in Settings")
            print("  4. Set environment variables:")
            print("     - ENABLE_LANGFUSE=true")
            print("     - LANGFUSE_PUBLIC_KEY=pk-lf-...")
            print("     - LANGFUSE_SECRET_KEY=sk-lf-...")
            return

        # Test tracing
        print("\nTesting tracing...")

        @trace_agent_request("test_agent")
        async def test_function(query: str, user_id: str = None) -> dict:
            await asyncio.sleep(0.1)  # Simulate work
            return {"response": "Test response", "cost_usd": 0.001}

        result = await test_function("Test query", user_id="test_user")
        print(f"  Result: {result}")

        # Test context manager
        async with trace_operation("test_operation", user_id="test_user") as trace:
            await asyncio.sleep(0.05)
            trace.update(output={"status": "success"})
            print("  Context manager trace created")

        # Flush
        langfuse = get_langfuse()
        if langfuse:
            langfuse.flush()
            print("\nTraces flushed to Langfuse")
            print(f"View at: {LANGFUSE_HOST}")

    asyncio.run(test())
