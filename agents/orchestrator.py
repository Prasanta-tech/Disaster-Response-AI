from __future__ import annotations

import asyncio
from typing import Any

from agents import (
    commander_agent,
    correlation_agent,
    nlp_agent,
    resource_agent,
    satellite_agent,
    verification_agent,
    vision_agent,
)


async def run(incident: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    # The orchestrator routes work only; domain reasoning remains inside each agent.
    nlp, vision, verification = await asyncio.gather(
        asyncio.to_thread(nlp_agent.run, incident),
        asyncio.to_thread(vision_agent.run, incident),
        asyncio.to_thread(verification_agent.run, incident),
    )
    incident["verification"] = verification
    correlation = await asyncio.to_thread(correlation_agent.run, incident, candidates)
    satellite = await asyncio.to_thread(satellite_agent.run, incident, nlp)
    outputs = {
        "nlp": nlp,
        "vision": vision,
        "verification": verification,
        "correlation": correlation,
        "satellite": satellite,
    }
    outputs["resource"] = await asyncio.to_thread(resource_agent.run, outputs)
    commander = await asyncio.to_thread(commander_agent.run, outputs)
    return {"agent_outputs": outputs, "commander_decision": commander}
