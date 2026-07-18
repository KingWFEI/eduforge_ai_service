"""Backward-compatible import and background-task entry for resource generation v2."""

import logging

from app.agents.resource_generation.graph import ResourceGenerationGraphService
from app.db.session import SessionLocal


logger = logging.getLogger("app.services.resource_generation_graph")


def run_resource_generation_graph(resource_task_id: str) -> None:
    db = SessionLocal()
    try:
        ResourceGenerationGraphService(db).run(resource_task_id)
    except Exception:
        logger.exception("resource generation background task failed | task_id=%s", resource_task_id)
    finally:
        db.close()


__all__ = ["ResourceGenerationGraphService", "run_resource_generation_graph"]
