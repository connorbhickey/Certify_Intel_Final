"""
Certify Intel - Analytics Routes (v5.0.2)
Executive summary, chat, and analytics API endpoints.

v5.0.2: Added hybrid AI support (OpenAI + Gemini)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db, Competitor, SystemPrompt, KnowledgeBaseItem
from analytics import AnalyticsEngine
import logging
import time
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import Gemini provider (v5.0.2)
try:
    from gemini_provider import GeminiProvider, AIRouter, get_ai_router
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.info("Gemini provider not available")

router = APIRouter()
analytics_engine = AnalyticsEngine()

# Global progress tracker for AI summary generation
ai_summary_progress = {
    "active": False,
    "step": "idle",
    "step_description": "",
    "progress": 0,
    "total_steps": 5,
    "started_at": None,
    "estimated_seconds": 30
}

def update_progress(step: int, description: str):
    """Update the global progress tracker."""
    ai_summary_progress["step"] = step
    ai_summary_progress["step_description"] = description
    ai_summary_progress["progress"] = int((step / ai_summary_progress["total_steps"]) * 100)


@router.get("/api/analytics/summary/progress")
async def get_summary_progress():
    """Get current AI summary generation progress."""
    return ai_summary_progress

@router.get("/api/analytics/summary")
async def get_dashboard_summary(db: Session = Depends(get_db)):
    """
    Generate executive summary for the dashboard with progress tracking.

    v5.0.2: Now uses hybrid AI routing (OpenAI or Gemini based on config)
    """
    try:
        # Initialize progress
        ai_summary_progress["active"] = True
        ai_summary_progress["started_at"] = time.time()

        # Step 1: Fetch competitors
        update_progress(1, "Loading competitor data...")
        competitors = db.query(Competitor).filter(Competitor.is_deleted == False).all()

        # Step 2: Get Custom System Prompt
        update_progress(2, "Loading AI configuration...")
        system_prompt = db.query(SystemPrompt).filter(SystemPrompt.key == "dashboard_summary").first()
        prompt_content = system_prompt.content if system_prompt else None

        # Step 3: Get Knowledge Base Context (RAG)
        update_progress(3, "Gathering knowledge base context...")
        kb_items = db.query(KnowledgeBaseItem).filter(KnowledgeBaseItem.is_active == True).all()
        kb_context = "\n".join([f"Note: {item.content_text}" for item in kb_items])

        # Step 4: Prepare data for AI
        update_progress(4, "Preparing data for analysis...")
        comp_dicts = []
        for c in competitors:
            comp_dicts.append({
                "name": c.name,
                "threat_level": c.threat_level,
                "base_price": c.base_price,
                "target_segments": c.target_segments,
                "key_features": c.key_features,
                "product_categories": c.product_categories
            })

        # Step 5: Generate AI Summary (v5.0.2 - Hybrid Routing)
        update_progress(5, "Generating executive summary with AI...")

        # Determine which provider to use
        active_provider = analytics_engine.insight_generator.get_active_provider()
        data_context = analytics_engine.insight_generator._prepare_context(comp_dicts)

        full_user_content = f"Competitive Landscape Data:\n{data_context}\n\n"
        if kb_context:
            full_user_content += f"Internal Knowledge Base Context:\n{kb_context}\n"

        default_system_prompt = "You are a Chief Strategy Officer. Analyze the competitive landscape data provided and generate a concise executive summary (2-3 sentences) and 3 bullet points of actionable strategic advice for 'Certify Health' (our company). Focus on threats, pricing pressure, and feature gaps."

        if active_provider == "gemini" and GEMINI_AVAILABLE:
            # Use Gemini
            gemini = GeminiProvider()
            if gemini.is_available:
                response = gemini.generate_text(
                    prompt=full_user_content,
                    system_prompt=prompt_content or default_system_prompt,
                    temperature=0.7,
                    max_tokens=1000
                )

                ai_summary_progress["active"] = False
                ai_summary_progress["progress"] = 100
                ai_summary_progress["step_description"] = "Complete!"

                return {
                    "summary": response.content if response.success else "Failed to generate summary",
                    "type": "ai",
                    "data_points_analyzed": len(competitors),
                    "generated_at": datetime.utcnow().isoformat(),
                    "model": gemini.config.model,
                    "provider": "Gemini",
                    "cost_estimate": response.cost_estimate
                }

        # Use OpenAI (default or fallback)
        if analytics_engine.insight_generator.has_openai:
            from openai import OpenAI
            client = analytics_engine.insight_generator.client

            messages = [
                {"role": "system", "content": prompt_content or default_system_prompt},
                {"role": "user", "content": full_user_content}
            ]

            model = os.getenv("OPENAI_MODEL", "gpt-4")
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7
            )

            summary_text = response.choices[0].message.content

            ai_summary_progress["active"] = False
            ai_summary_progress["progress"] = 100
            ai_summary_progress["step_description"] = "Complete!"

            return {
                "summary": summary_text,
                "type": "ai",
                "data_points_analyzed": len(competitors),
                "generated_at": datetime.utcnow().isoformat(),
                "model": model,
                "provider": "OpenAI"
            }

        # No AI available, use fallback
        ai_summary_progress["active"] = False
        ai_summary_progress["progress"] = 100
        return analytics_engine.insight_generator.generate_insight(comp_dicts)

    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        ai_summary_progress["active"] = False
        ai_summary_progress["step_description"] = f"Error: {str(e)}"
        return {"error": str(e)}

@router.post("/api/analytics/chat")
async def chat_with_analytics(message: dict, db: Session = Depends(get_db)):
    """
    Chat with the AI about competitive intelligence.

    v5.0.2: Now supports hybrid AI routing (OpenAI or Gemini based on config)
    """
    user_msg = message.get("message", "")
    try:
        # Get Chat Persona
        persona = db.query(SystemPrompt).filter(SystemPrompt.key == "chat_persona").first()
        system_msg = persona.content if persona else "You are a competitive intelligence assistant."

        # Simple RAG: Fetch relevant KB items
        kb_items = db.query(KnowledgeBaseItem).filter(KnowledgeBaseItem.is_active == True).all()
        kb_context = "\n".join([f"- {item.content_text}" for item in kb_items])

        # Fetch Top Threats for context
        top_threats = db.query(Competitor).filter(
            Competitor.is_deleted == False,
            Competitor.threat_level == "High"
        ).limit(5).all()
        threat_context = "\n".join([f"{c.name}: {c.notes}" for c in top_threats])

        context_block = f"""
        Internal Knowledge Base:
        {kb_context}

        Top Threats Context:
        {threat_context}
        """

        full_prompt = f"Context data:\n{context_block}\n\nUser question: {user_msg}"

        # v5.0.2: Determine which provider to use for chat
        ai_provider = os.getenv("AI_PROVIDER", "hybrid")

        # For chat, prefer OpenAI (better at conversation) unless forced to Gemini
        use_gemini = (ai_provider == "gemini") or (
            ai_provider == "hybrid" and
            os.getenv("AI_QUALITY_TASKS", "openai") == "gemini"
        )

        if use_gemini and GEMINI_AVAILABLE:
            # Try Gemini first
            gemini = GeminiProvider()
            if gemini.is_available:
                response = gemini.generate_text(
                    prompt=full_prompt,
                    system_prompt=system_msg,
                    temperature=0.7
                )

                if response.success:
                    return {
                        "success": True,
                        "response": response.content,
                        "provider": "gemini",
                        "model": gemini.config.model
                    }

        # Use OpenAI (default or fallback)
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)

            model = os.getenv("OPENAI_MODEL", "gpt-4")
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "system", "content": f"Context data:\n{context_block}"},
                    {"role": "user", "content": user_msg}
                ],
                temperature=0.7
            )

            return {
                "success": True,
                "response": response.choices[0].message.content,
                "provider": "openai",
                "model": model
            }

        # No AI available
        return {
            "success": False,
            "response": "No AI provider configured. Please set OPENAI_API_KEY or GOOGLE_AI_API_KEY.",
            "provider": "none"
        }

    except Exception as e:
        logger.error(f"Chat error: {e}")
        return {
            "success": False,
            "response": "I apologize, but I'm having trouble connecting to my brain right now. Please try again later.",
            "error": str(e)
        }

from datetime import datetime
