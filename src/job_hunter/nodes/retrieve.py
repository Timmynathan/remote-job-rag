from __future__ import annotations

import logging

from job_hunter.models import Job
from job_hunter.sources import arbeitnow, himalayas, jobicy, remoteok, remotive, wwr

logger = logging.getLogger(__name__)

_SOURCE_MODULES = (remotive, arbeitnow, jobicy, remoteok, himalayas, wwr)


def retrieve_node(state: dict) -> dict:
    """Fetch every source's current feed once per pass and merge into `candidates`.

    Only one call per source per pass (not one per generated query): none of
    these free APIs meaningfully filter by search term server-side (verified
    directly for Remotive - different terms returned identical results), so
    role/seniority/geo targeting all happens client-side in
    validate_dedupe_node instead.

    Each source call is isolated so one flaky/down API doesn't take out the
    whole run - failures are logged and skipped.

    Merging by job_id (rather than replacing the list each pass) means a job
    already found - and possibly already validated/scored - on an earlier
    refine-loop iteration is never lost on a later pass.
    """
    candidates: dict[str, Job] = {job.job_id: job for job in state.get("candidates", [])}
    http_client = state.get("http_client")

    for source_module in _SOURCE_MODULES:
        try:
            jobs = source_module.fetch_jobs(client=http_client)
        except Exception:
            logger.warning("Source %s failed, skipping", source_module.__name__, exc_info=True)
            continue
        for job in jobs:
            candidates.setdefault(job.job_id, job)

    return {"candidates": list(candidates.values())}
