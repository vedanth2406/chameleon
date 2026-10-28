"""Shared internal types; these are metadata, not design-schema fields."""

from typing import TypedDict


class LayoutUnit(TypedDict):
    """Elements that travel together; explicit group_id membership wins.

    source_bounds is (x, y, width, height) in source-canvas pixels.
    role is an inferred hint, never a required input label.
    importance is in [0, 1], with larger values indicating higher priority.
    """

    key: str
    element_ids: list[str]
    source_bounds: tuple[float, float, float, float]
    role: str
    importance: float


class ContainerRelationship(TypedDict):
    container_id: str
    child_unit_keys: list[str]
    child_ids: list[str]
    confidence: float
    signals: list[str]
    # Left/top/right/bottom padding relative to the source child envelope.
    padding: tuple[float, float, float, float]


class LayerRelationship(TypedDict):
    element_ids: tuple[str, str]
    confidence: float
    signals: list[str]
    overlap_fraction: float
    visible_overlap_fraction: float
    # Local normalized alpha bounds; geometry only, no cached/generated pixels.
    content_bounds: dict[str, tuple[float, float, float, float]]


class Analysis(TypedDict):
    """Read-only layout metadata referencing original element IDs."""

    units: list[LayoutUnit]
    background_ids: list[str]
    decoration_ids: list[str]
    intentional_overlap_pairs: list[tuple[str, str]]
    diagnostics: list[str]
    containers: list[ContainerRelationship]
    layers: list[LayerRelationship]


class Evaluation(TypedDict):
    """Hard failures and soft costs; lower score is better.

    Hard errors make a candidate infeasible regardless of its score. resize()
    warns if it must return an infeasible result because no candidate passed.
    """

    hard_errors: list[str]
    penalties: dict[str, float]
    score: float
