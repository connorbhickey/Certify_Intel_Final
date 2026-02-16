from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Optional
from discovery_agent import DiscoveryAgent
import asyncio

router = APIRouter(
    prefix="/api/discovery",
    tags=["discovery"]
)

agent = DiscoveryAgent()

@router.post("/run")
async def run_discovery(max_candidates: int = 10, background_tasks: BackgroundTasks = None):
    """Trigger the autonomous discovery agent."""
    if background_tasks:
        background_tasks.add_task(agent.run_discovery_loop, max_candidates)
        return {"status": "started", "message": "Discovery agent running in background"}
    else:
        # Blocking run (not recommended for production but good for testing)
        results = await agent.run_discovery_loop(max_candidates)
        return {"status": "completed", "count": len(results), "results": results}

@router.get("/status")
def get_discovery_status():
    """Get current status of discovery agent (mock)."""
    return {"status": "idle", "last_run": agent.last_search_time}
