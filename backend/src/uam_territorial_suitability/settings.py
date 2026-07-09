"""Per-deployment data source configuration.

No personal/municipal file paths are hardcoded anywhere in this repository
(D07) — a deployment for a given municipality sets these environment
variables to point at its own datasets. Any unset variable simply disables
the criterion(a) that depend on it; the API reports that explicitly rather
than silently skipping it (see api/routes.py CriterionStatus.NOT_IMPLEMENTED).
"""

import os


def reh_corridors_path() -> str | None:
    return os.environ.get("REH_CORRIDORS_PATH")


def dsm_path() -> str | None:
    """Digital Surface Model (MDS) — for the obstacles criterion. Must
    capture surface objects (buildings, vegetation), not bare earth."""
    return os.environ.get("DSM_PATH")


def dtm_path() -> str | None:
    """Digital Terrain Model (MDT) — for the topography criterion. Must be
    bare-earth; do NOT point this at the same file as DSM_PATH (see D35)."""
    return os.environ.get("DTM_PATH")
