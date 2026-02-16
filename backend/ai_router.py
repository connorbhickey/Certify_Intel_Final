"""
Certify Intel v7.0 - AI Router with Cost Tracking
==================================================

Multi-model AI routing for cost optimization and quality control.

Features:
- Task-based model selection (98% cost savings vs single premium model)
- Daily budget enforcement ($50 default limit)
- Cost tracking per request
- Automatic fallback on errors
- Langfuse integration for observability

Model Strategy (2026 Pricing):
- Gemini 3 Flash: Chat, RAG, summarization, bulk, classification ($0.50/$3.00 per 1M tokens)
- Gemini 3 Pro: Grounded search, deep research, complex analysis ($2.00/$12.00 per 1M tokens)
- Claude Opus 4.5: ALL complex tasks — analysis, battlecards, strategy, reasoning ($15.00/$75.00 per 1M tokens)
- Claude Sonnet 4.5: Fallback only ($3.00/$15.00 per 1M tokens)
- Fallback chain: Claude Opus → GPT-4o → Gemini

Expected Savings:
- Original plan (all premium): ~$16.80/day
- Optimized routing: ~$0.41/day
- Savings: 98% ($98.34 over 6-day development)
"""

import os
import json
import logging
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# MODEL CONFIGURATION
# =============================================================================

class TaskType(str, Enum):
    """Task types for model routing."""
    BULK_EXTRACTION = "bulk_extraction"      # Large-scale data extraction
    CLASSIFICATION = "classification"         # Category/sentiment/type classification
    CHAT = "chat"                             # Interactive conversation
    SUMMARIZATION = "summarization"           # Text summarization
    RAG = "rag"                               # Retrieval-augmented generation
    ANALYSIS = "analysis"                     # Detailed analysis
    BATTLECARD = "battlecard"                 # Sales battlecard generation
    STRATEGY = "strategy"                     # Strategic recommendations
    COMPLEX_REASONING = "complex_reasoning"   # Multi-step reasoning
    DISCOVERY = "discovery"                   # Competitor discovery qualification & analysis


@dataclass
class ModelConfig:
    """Configuration for an AI model."""
    name: str                           # Model identifier
    provider: str                       # openai, anthropic, google, deepseek
    input_cost_per_1m: float           # Cost per 1M input tokens
    output_cost_per_1m: float          # Cost per 1M output tokens
    context_window: int                 # Maximum context size
    best_for: List[TaskType]           # Task types this model excels at
    max_output_tokens: int = 4096      # Default max output
    supports_streaming: bool = True
    supports_tools: bool = True
    api_model_id: Optional[str] = None  # Actual API model ID if different


# Model registry with 2026 pricing
MODELS: Dict[str, ModelConfig] = {
    # Ultra-cheap: Bulk extraction, classification
    "deepseek-v3.2": ModelConfig(
        name="deepseek-v3.2",
        provider="deepseek",
        input_cost_per_1m=0.27,
        output_cost_per_1m=1.10,
        context_window=64_000,
        best_for=[TaskType.BULK_EXTRACTION, TaskType.CLASSIFICATION],
        api_model_id="deepseek-chat"
    ),

    # Cheap: General tasks, real-time chat, RAG, bulk, classification
    "gemini-3-flash-preview": ModelConfig(
        name="gemini-3-flash-preview",
        provider="google",
        input_cost_per_1m=0.50,
        output_cost_per_1m=3.00,
        context_window=1_000_000,
        best_for=[TaskType.CHAT, TaskType.SUMMARIZATION, TaskType.RAG,
                  TaskType.BULK_EXTRACTION, TaskType.CLASSIFICATION],
        api_model_id="gemini-3-flash-preview"
    ),

    # Quality: Grounded search, deep research, complex analysis
    "gemini-3-pro-preview": ModelConfig(
        name="gemini-3-pro-preview",
        provider="google",
        input_cost_per_1m=2.00,
        output_cost_per_1m=12.00,
        context_window=1_000_000,
        best_for=[],  # Used explicitly, not auto-routed
        api_model_id="gemini-3-pro-preview"
    ),

    # Balanced: Complex analysis, writing
    "claude-sonnet-4.5": ModelConfig(
        name="claude-sonnet-4.5",
        provider="anthropic",
        input_cost_per_1m=3.00,
        output_cost_per_1m=15.00,
        context_window=200_000,
        best_for=[],  # Fallback only — Opus handles all Anthropic tasks
        api_model_id="claude-sonnet-4-5-20250929"
    ),

    # Premium: ALL complex tasks (analysis, battlecards, strategy, reasoning)
    "claude-opus-4.5": ModelConfig(
        name="claude-opus-4.5",
        provider="anthropic",
        input_cost_per_1m=15.00,
        output_cost_per_1m=75.00,
        context_window=200_000,
        best_for=[
            TaskType.ANALYSIS, TaskType.BATTLECARD, TaskType.STRATEGY,
            TaskType.COMPLEX_REASONING, TaskType.DISCOVERY,
        ],
        api_model_id="claude-opus-4-5-20251101"
    ),

    # OpenAI fallback
    "gpt-4o": ModelConfig(
        name="gpt-4o",
        provider="openai",
        input_cost_per_1m=2.50,
        output_cost_per_1m=10.00,
        context_window=128_000,
        best_for=[TaskType.ANALYSIS, TaskType.CHAT, TaskType.RAG],
        api_model_id="gpt-4o"
    ),

    "gpt-4o-mini": ModelConfig(
        name="gpt-4o-mini",
        provider="openai",
        input_cost_per_1m=0.15,
        output_cost_per_1m=0.60,
        context_window=128_000,
        best_for=[TaskType.CLASSIFICATION, TaskType.SUMMARIZATION, TaskType.CHAT],
        api_model_id="gpt-4o-mini"
    )
}

# Optionally register Vertex AI model when enabled via env var
if os.getenv("VERTEX_AI_ENABLED", "false").lower() == "true":
    MODELS["vertex-ai-flash"] = ModelConfig(
        name="vertex-ai-flash",
        provider="vertex_ai",
        input_cost_per_1m=0.10,
        output_cost_per_1m=0.40,
        context_window=1_000_000,
        best_for=[],  # Not auto-routed; use model_override to select
        api_model_id="gemini-3-flash-preview"
    )
    MODELS["vertex-ai-pro"] = ModelConfig(
        name="vertex-ai-pro",
        provider="vertex_ai",
        input_cost_per_1m=1.50,
        output_cost_per_1m=12.00,
        context_window=1_000_000,
        best_for=[],  # Not auto-routed; use model_override to select
        api_model_id="gemini-3-pro-preview"
    )
    logger.info("Vertex AI models registered (VERTEX_AI_ENABLED=true)")

# Optionally register Ollama local model when enabled
if os.getenv("OLLAMA_ENABLED", "false").lower() == "true":
    _ollama_model = os.getenv("OLLAMA_DEFAULT_MODEL", "llama3.1:8b")
    MODELS[f"ollama-{_ollama_model}"] = ModelConfig(
        name=f"ollama-{_ollama_model}",
        provider="ollama",
        input_cost_per_1m=0.0,
        output_cost_per_1m=0.0,
        context_window=128_000,
        best_for=[],  # Not auto-routed; use model_override to select
        api_model_id=_ollama_model
    )
    logger.info(f"Ollama model registered: ollama-{_ollama_model}")

# Optionally register LiteLLM proxy when enabled
if os.getenv("LITELLM_ENABLED", "false").lower() == "true":
    MODELS["litellm-proxy"] = ModelConfig(
        name="litellm-proxy",
        provider="litellm",
        input_cost_per_1m=0.0,  # Cost tracked by LiteLLM proxy
        output_cost_per_1m=0.0,
        context_window=128_000,
        best_for=[],  # Not auto-routed; use model_override
        api_model_id="gpt-4o"  # Default model on proxy
    )
    logger.info("LiteLLM proxy model registered")


# Default routing rules
TASK_TO_DEFAULT_MODEL: Dict[TaskType, str] = {
    TaskType.BULK_EXTRACTION: "gemini-3-flash-preview",
    TaskType.CLASSIFICATION: "gemini-3-flash-preview",
    TaskType.CHAT: "gemini-3-flash-preview",
    TaskType.SUMMARIZATION: "gemini-3-flash-preview",
    TaskType.RAG: "gemini-3-flash-preview",
    TaskType.ANALYSIS: "claude-opus-4.5",
    TaskType.BATTLECARD: "claude-opus-4.5",
    TaskType.STRATEGY: "claude-opus-4.5",
    TaskType.COMPLEX_REASONING: "claude-opus-4.5",
    TaskType.DISCOVERY: "claude-opus-4.5"
}


# =============================================================================
# EXCEPTIONS
# =============================================================================

class BudgetExceededException(Exception):
    """Raised when daily budget is exceeded."""
    pass


class ModelUnavailableException(Exception):
    """Raised when a model is unavailable."""
    pass


# =============================================================================
# COST TRACKER
# =============================================================================

@dataclass
class UsageRecord:
    """Record of a single AI usage."""
    model: str
    task_type: TaskType
    tokens_input: int
    tokens_output: int
    cost_usd: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    latency_ms: Optional[int] = None
    user_id: Optional[str] = None
    agent_type: Optional[str] = None


class CostTracker:
    """
    Track AI usage and costs.

    Maintains daily totals and enforces budget limits.
    """

    def __init__(self, daily_budget_usd: float = 50.0):
        self.daily_budget_usd = daily_budget_usd
        self._usage_records: List[UsageRecord] = []
        self._daily_totals: Dict[date, float] = {}

    def record_usage(
        self,
        model: str,
        task_type: TaskType,
        tokens_input: int,
        tokens_output: int,
        latency_ms: Optional[int] = None,
        user_id: Optional[str] = None,
        agent_type: Optional[str] = None
    ) -> UsageRecord:
        """Record a usage event and calculate cost."""
        config = MODELS.get(model)
        if not config:
            logger.warning(f"Unknown model: {model}, using estimated cost")
            # Conservative estimate
            cost = (tokens_input / 1_000_000) * 5.0 + (tokens_output / 1_000_000) * 15.0
        else:
            cost = (
                (tokens_input / 1_000_000) * config.input_cost_per_1m +
                (tokens_output / 1_000_000) * config.output_cost_per_1m
            )

        record = UsageRecord(
            model=model,
            task_type=task_type,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            cost_usd=cost,
            latency_ms=latency_ms,
            user_id=user_id,
            agent_type=agent_type
        )

        self._usage_records.append(record)

        # Cap usage records to prevent unbounded memory growth
        if len(self._usage_records) > 10_000:
            self._usage_records = self._usage_records[-5_000:]

        # Update daily total
        today = date.today()
        self._daily_totals[today] = self._daily_totals.get(today, 0.0) + cost

        return record

    def get_today_spend(self) -> float:
        """Get total spend for today."""
        return self._daily_totals.get(date.today(), 0.0)

    def get_remaining_budget(self) -> float:
        """Get remaining budget for today."""
        return self.daily_budget_usd - self.get_today_spend()

    def check_budget(self, estimated_cost: float = 0.0) -> bool:
        """Check if budget allows a request."""
        return self.get_today_spend() + estimated_cost <= self.daily_budget_usd

    def get_usage_summary(self, since: Optional[datetime] = None) -> Dict[str, Any]:
        """Get usage summary."""
        records = self._usage_records
        if since:
            records = [r for r in records if r.timestamp >= since]

        if not records:
            return {
                "total_cost_usd": 0.0,
                "total_requests": 0,
                "total_tokens_input": 0,
                "total_tokens_output": 0,
                "by_model": {},
                "by_task": {}
            }

        by_model: Dict[str, Dict] = {}
        by_task: Dict[str, Dict] = {}

        for r in records:
            # By model
            if r.model not in by_model:
                by_model[r.model] = {"cost": 0.0, "count": 0, "tokens": 0}
            by_model[r.model]["cost"] += r.cost_usd
            by_model[r.model]["count"] += 1
            by_model[r.model]["tokens"] += r.tokens_input + r.tokens_output

            # By task
            task_name = r.task_type.value if isinstance(r.task_type, TaskType) else str(r.task_type)
            if task_name not in by_task:
                by_task[task_name] = {"cost": 0.0, "count": 0}
            by_task[task_name]["cost"] += r.cost_usd
            by_task[task_name]["count"] += 1

        return {
            "total_cost_usd": sum(r.cost_usd for r in records),
            "total_requests": len(records),
            "total_tokens_input": sum(r.tokens_input for r in records),
            "total_tokens_output": sum(r.tokens_output for r in records),
            "by_model": by_model,
            "by_task": by_task
        }


# =============================================================================
# AI ROUTER
# =============================================================================

class AIRouter:
    """
    Route AI requests to optimal model based on task type and cost constraints.

    Usage:
        router = AIRouter()

        # Get recommended model
        model = await router.route_request(
            task_type=TaskType.BULK_EXTRACTION,
            prompt_tokens=50000,
            expected_output_tokens=10000
        )

        # Generate with automatic model selection
        response = await router.generate(
            prompt="Extract company names from...",
            task_type=TaskType.BULK_EXTRACTION
        )
    """

    def __init__(
        self,
        daily_budget_usd: float = 50.0,
        fallback_enabled: bool = True
    ):
        self.cost_tracker = CostTracker(daily_budget_usd)
        self.fallback_enabled = fallback_enabled

        # Client cache
        self._clients: Dict[str, Any] = {}

    def _get_client(self, provider: str):
        """Get or create API client for provider."""
        if provider in self._clients:
            return self._clients[provider]

        if provider == "openai":
            try:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                self._clients[provider] = client
                return client
            except ImportError:
                raise ModelUnavailableException("OpenAI client not installed")

        elif provider == "anthropic":
            try:
                from anthropic import AsyncAnthropic
                client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
                self._clients[provider] = client
                return client
            except ImportError:
                raise ModelUnavailableException("Anthropic client not installed")

        elif provider == "google":
            try:
                from google import genai
                client = genai.Client(api_key=os.getenv("GOOGLE_AI_API_KEY"))
                self._clients[provider] = client
                return client
            except ImportError:
                raise ModelUnavailableException("Google GenAI SDK not installed. Run: pip install google-genai")

        elif provider == "deepseek":
            # DeepSeek uses OpenAI-compatible API
            try:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(
                    api_key=os.getenv("DEEPSEEK_API_KEY"),
                    base_url="https://api.deepseek.com/v1"
                )
                self._clients[provider] = client
                return client
            except ImportError:
                raise ModelUnavailableException("OpenAI client not installed (needed for DeepSeek)")

        elif provider == "vertex_ai":
            try:
                from vertex_ai_provider import get_vertex_provider
                client = get_vertex_provider()
                if client is None or not client.is_available:
                    raise ModelUnavailableException(
                        "Vertex AI not configured (check GCP credentials)"
                    )
                self._clients[provider] = client
                return client
            except ImportError:
                raise ModelUnavailableException(
                    "Vertex AI provider not available"
                )

        elif provider == "ollama":
            try:
                from ollama_provider import get_ollama_provider
                client = get_ollama_provider()
                if client is None:
                    raise ModelUnavailableException("Ollama not available")
                self._clients[provider] = client
                return client
            except ImportError:
                raise ModelUnavailableException(
                    "Ollama provider not available"
                )

        elif provider == "litellm":
            try:
                from litellm_provider import get_litellm_provider
                client = get_litellm_provider()
                if client is None:
                    raise ModelUnavailableException("LiteLLM not available")
                self._clients[provider] = client
                return client
            except ImportError:
                raise ModelUnavailableException(
                    "LiteLLM provider not available"
                )

        raise ModelUnavailableException(f"Unknown provider: {provider}")

    def estimate_cost(
        self,
        model: str,
        prompt_tokens: int,
        expected_output_tokens: int
    ) -> float:
        """Estimate cost for a request."""
        config = MODELS.get(model)
        if not config:
            return 0.0

        return (
            (prompt_tokens / 1_000_000) * config.input_cost_per_1m +
            (expected_output_tokens / 1_000_000) * config.output_cost_per_1m
        )

    async def route_request(
        self,
        task_type: TaskType,
        prompt_tokens: int,
        expected_output_tokens: int,
        max_cost_usd: Optional[float] = None,
        preferred_model: Optional[str] = None
    ) -> str:
        """
        Route request to optimal model.

        Args:
            task_type: Type of task
            prompt_tokens: Estimated input tokens
            expected_output_tokens: Expected output tokens
            max_cost_usd: Maximum cost for this request
            preferred_model: Optional model preference

        Returns:
            Model name to use
        """
        # Check daily budget
        if not self.cost_tracker.check_budget():
            raise BudgetExceededException(
                f"Daily budget ${self.cost_tracker.daily_budget_usd} exceeded. "
                f"Today's spend: ${self.cost_tracker.get_today_spend():.4f}"
            )

        # If preferred model specified and available, use it
        if preferred_model and preferred_model in MODELS:
            estimated = self.estimate_cost(preferred_model, prompt_tokens, expected_output_tokens)
            if self.cost_tracker.check_budget(estimated):
                if max_cost_usd is None or estimated <= max_cost_usd:
                    return preferred_model

        # Get default model for task
        default_model = TASK_TO_DEFAULT_MODEL.get(task_type, "gemini-3-flash-preview")

        # Find models capable of this task
        capable_models = [
            (name, config)
            for name, config in MODELS.items()
            if task_type in config.best_for
        ]

        if not capable_models:
            # Use default if no specialized models
            capable_models = [(default_model, MODELS[default_model])]

        # Calculate cost for each model
        options = []
        for name, config in capable_models:
            est_cost = self.estimate_cost(name, prompt_tokens, expected_output_tokens)

            # Check constraints
            if not self.cost_tracker.check_budget(est_cost):
                continue
            if max_cost_usd and est_cost > max_cost_usd:
                continue

            options.append((name, est_cost, config))

        if not options:
            # Fall back to cheapest option
            logger.warning("No model fits constraints, falling back to gemini-3-flash-preview")
            return "gemini-3-flash-preview"

        # Prefer the default model for this task type if it's in the options
        for name, est_cost, config in options:
            if name == default_model:
                return name

        # Otherwise sort by cost (cheapest first)
        options.sort(key=lambda x: x[1])

        return options[0][0]

    async def generate(
        self,
        prompt: str,
        task_type: TaskType,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        model_override: Optional[str] = None,
        user_id: Optional[str] = None,
        agent_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate response with automatic model selection.

        Args:
            prompt: User prompt
            task_type: Task type for routing
            system_prompt: Optional system prompt
            max_tokens: Maximum output tokens
            temperature: Generation temperature
            model_override: Force specific model
            user_id: User ID for tracking
            agent_type: Agent type for tracking

        Returns:
            Dict with response, model, cost, usage
        """
        import tiktoken
        import time

        # Estimate tokens
        try:
            enc = tiktoken.get_encoding("cl100k_base")
            prompt_tokens = len(enc.encode(prompt))
            if system_prompt:
                prompt_tokens += len(enc.encode(system_prompt))
        except Exception:
            # Fallback estimation
            prompt_tokens = len(prompt.split()) * 2

        # Select model
        if model_override:
            model = model_override
        else:
            model = await self.route_request(
                task_type=task_type,
                prompt_tokens=prompt_tokens,
                expected_output_tokens=max_tokens
            )

        config = MODELS.get(model)
        if not config:
            raise ModelUnavailableException(f"Unknown model: {model}")

        # Generate response
        start_time = time.time()
        response_text = ""
        output_tokens = 0

        try:
            if config.provider == "openai" or config.provider == "deepseek":
                response_text, output_tokens = await self._generate_openai(
                    config, prompt, system_prompt, max_tokens, temperature
                )
            elif config.provider == "anthropic":
                response_text, output_tokens = await self._generate_anthropic(
                    config, prompt, system_prompt, max_tokens, temperature
                )
            elif config.provider == "google":
                response_text, output_tokens = await self._generate_google(
                    config, prompt, system_prompt, max_tokens, temperature
                )
            elif config.provider == "vertex_ai":
                response_text, output_tokens = await self._generate_vertex_ai(
                    config, prompt, system_prompt, max_tokens, temperature
                )
            elif config.provider == "ollama":
                ollama_client = self._get_client("ollama")
                result = await ollama_client.generate(
                    prompt=prompt, model=config.api_model_id,
                    system_prompt=system_prompt, max_tokens=max_tokens,
                    temperature=temperature
                )
                response_text = result["response"]
                output_tokens = result["tokens_output"]
            elif config.provider == "litellm":
                litellm_client = self._get_client("litellm")
                result = await litellm_client.generate(
                    prompt=prompt, model=config.api_model_id,
                    system_prompt=system_prompt, max_tokens=max_tokens,
                    temperature=temperature
                )
                response_text = result["response"]
                output_tokens = result["tokens_output"]
            else:
                raise ModelUnavailableException(f"Unsupported provider: {config.provider}")

        except Exception as e:
            logger.error(f"Generation failed with {model}: {e}")

            # 3-tier fallback: Claude Opus → GPT-4o → Gemini
            if self.fallback_enabled:
                if config.provider == "anthropic" and model != "gpt-4o":
                    logger.info("Anthropic failed, falling back to gpt-4o")
                    return await self.generate(
                        prompt=prompt, task_type=task_type,
                        system_prompt=system_prompt, max_tokens=max_tokens,
                        temperature=temperature, model_override="gpt-4o",
                        user_id=user_id, agent_type=agent_type
                    )
                if model != "gemini-3-flash-preview":
                    logger.info("Falling back to gemini-3-flash-preview")
                    return await self.generate(
                        prompt=prompt, task_type=task_type,
                        system_prompt=system_prompt, max_tokens=max_tokens,
                        temperature=temperature, model_override="gemini-3-flash-preview",
                        user_id=user_id, agent_type=agent_type
                    )
                # Try Ollama as last resort if available
                if os.getenv("OLLAMA_ENABLED", "false").lower() == "true":
                    _ollama_default = os.getenv(
                        "OLLAMA_DEFAULT_MODEL", "llama3.1:8b"
                    )
                    ollama_model = f"ollama-{_ollama_default}"
                    if model != ollama_model and ollama_model in MODELS:
                        logger.info(
                            f"Falling back to local Ollama: {ollama_model}"
                        )
                        return await self.generate(
                            prompt=prompt, task_type=task_type,
                            system_prompt=system_prompt,
                            max_tokens=max_tokens,
                            temperature=temperature,
                            model_override=ollama_model,
                            user_id=user_id, agent_type=agent_type
                        )
            raise

        latency_ms = int((time.time() - start_time) * 1000)

        # Record usage
        record = self.cost_tracker.record_usage(
            model=model,
            task_type=task_type,
            tokens_input=prompt_tokens,
            tokens_output=output_tokens,
            latency_ms=latency_ms,
            user_id=user_id,
            agent_type=agent_type
        )

        # Log to Langfuse if enabled (zero overhead if disabled)
        try:
            from observability import log_ai_cost
            log_ai_cost(
                model=model,
                agent_type=agent_type or "unknown",
                task_type=task_type.value,
                tokens_input=prompt_tokens,
                tokens_output=output_tokens,
                cost_usd=record.cost_usd,
                latency_ms=latency_ms,
                user_id=user_id
            )
        except Exception:
            pass  # Langfuse logging must never break generation

        return {
            "response": response_text,
            "model": model,
            "provider": config.provider,
            "tokens_input": prompt_tokens,
            "tokens_output": output_tokens,
            "cost_usd": record.cost_usd,
            "latency_ms": latency_ms
        }

    async def generate_json(
        self,
        prompt: str,
        task_type: TaskType,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        model_override: Optional[str] = None,
        user_id: Optional[str] = None,
        agent_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a JSON response. Wraps system prompt with JSON instruction."""
        json_instruction = ("You MUST respond with valid JSON only. No markdown fencing, "
                            "no explanation, no text outside the JSON object.")
        if system_prompt:
            enhanced_system = f"{system_prompt}\n\n{json_instruction}"
        else:
            enhanced_system = json_instruction

        result = await self.generate(
            prompt=prompt, task_type=task_type,
            system_prompt=enhanced_system, max_tokens=max_tokens,
            temperature=temperature, model_override=model_override,
            user_id=user_id, agent_type=agent_type
        )

        # Parse the response as JSON, stripping any markdown fencing
        raw = result["response"].strip()
        if raw.startswith("```"):
            # Remove opening fence (```json or ```)
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        try:
            result["response_json"] = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("generate_json: Failed to parse JSON, returning raw text")
            result["response_json"] = {"raw": raw}
        return result

    async def _generate_openai(
        self,
        config: ModelConfig,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float
    ) -> tuple[str, int]:
        """Generate with OpenAI-compatible API."""
        client = self._get_client(config.provider)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await client.chat.completions.create(
            model=config.api_model_id or config.name,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )

        text = response.choices[0].message.content or ""
        tokens = response.usage.completion_tokens if response.usage else len(text.split())

        return text, tokens

    async def _generate_anthropic(
        self,
        config: ModelConfig,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float
    ) -> tuple[str, int]:
        """Generate with Anthropic API."""
        client = self._get_client(config.provider)

        kwargs = {
            "model": config.api_model_id or config.name,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}]
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        response = await client.messages.create(**kwargs)

        text = response.content[0].text if response.content else ""
        tokens = response.usage.output_tokens if response.usage else len(text.split())

        return text, tokens

    async def _generate_google(
        self,
        config: ModelConfig,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float
    ) -> tuple[str, int]:
        """Generate with Google Gemini API (using google-genai unified SDK)."""
        from google.genai import types as genai_types

        client = self._get_client(config.provider)
        model_name = config.api_model_id or config.name

        # Build full prompt with system instruction
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        # Use new Client API via asyncio.to_thread for sync-to-async
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model_name,
            contents=full_prompt,
            config=genai_types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            ),
        )

        text = response.text if hasattr(response, 'text') else ""
        tokens = len(text.split()) * 2  # Approximate

        return text, tokens

    async def _generate_vertex_ai(
        self,
        config: ModelConfig,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float
    ) -> tuple[str, int]:
        """Generate with Google Cloud Vertex AI provider."""
        client = self._get_client(config.provider)
        model_name = config.api_model_id or config.name

        response = await client.generate(
            prompt=prompt,
            model=model_name,
            system_instruction=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        if not response.success:
            raise ModelUnavailableException(
                f"Vertex AI error: {response.error}"
            )

        tokens = len(response.content.split()) * 2  # Approximate
        return response.content, tokens


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_router: Optional[AIRouter] = None


def get_ai_router() -> AIRouter:
    """Get or create the AI router instance."""
    global _router

    if _router is None:
        daily_budget = float(os.getenv("AI_DAILY_BUDGET_USD", "50.0"))
        fallback = os.getenv("AI_FALLBACK_ENABLED", "true").lower() == "true"
        _router = AIRouter(daily_budget_usd=daily_budget, fallback_enabled=fallback)

    return _router


# =============================================================================
# CLI FOR TESTING
# =============================================================================

if __name__ == "__main__":
    import asyncio  # noqa: F811

    async def test():
        print("AI Router Test\n")
        print("=" * 60)

        router = get_ai_router()

        # Test routing
        test_cases = [
            (TaskType.BULK_EXTRACTION, 500000, 100000),  # Large batch
            (TaskType.CHAT, 1000, 500),                   # Quick chat
            (TaskType.ANALYSIS, 10000, 5000),             # Analysis
            (TaskType.STRATEGY, 5000, 3000),              # Strategy
        ]

        print("\nRouting Test:")
        print("-" * 60)
        for task_type, input_tokens, output_tokens in test_cases:
            model = await router.route_request(
                task_type=task_type,
                prompt_tokens=input_tokens,
                expected_output_tokens=output_tokens
            )
            cost = router.estimate_cost(model, input_tokens, output_tokens)
            print(f"  {task_type.value:20} -> {model:20} (${cost:.4f})")

        # Cost comparison
        print("\n\nCost Comparison (100 competitor discovery):")
        print("-" * 60)

        test_input = 500000
        test_output = 100000

        for model_name, config in MODELS.items():
            cost = router.estimate_cost(model_name, test_input, test_output)
            print(f"  {model_name:20}: ${cost:.4f}")

        print(f"\nToday's spend: ${router.cost_tracker.get_today_spend():.4f}")
        print(f"Remaining budget: ${router.cost_tracker.get_remaining_budget():.4f}")

    asyncio.run(test())
