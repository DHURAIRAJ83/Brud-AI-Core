"""Knowledge coverage statistics -- pure arithmetic over already-
fetched items, never a model-based estimate.

Two distinct coverage concepts, kept explicit rather than blended into
one fake percentage:

- `documentation_coverage`: of the knowledge items that exist, what
  fraction have a real description and at least one documentation
  reference. Always computable from the catalog alone.
- `catalog_coverage`: of the *real system* (route files, services,
  pages -- a reference count the caller supplies, e.g. from a prior
  architecture audit), what fraction has a knowledge item at all. Only
  computed when the caller supplies a reference count for that domain;
  otherwise reported as `None` ("unknown"), never guessed.
"""

from __future__ import annotations

from typing import Any


def _pct(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(100 * numerator / denominator, 1)


def compute_domain_coverage(
    domain_key: str,
    items: list[dict[str, Any]],
    *,
    reference_count: int | None = None,
) -> dict[str, Any]:
    documented = sum(
        1 for item in items if item.get("description", "").strip() and item.get("related_documentation")
    )
    return {
        "domain": domain_key,
        "item_count": len(items),
        "documented_count": documented,
        "documentation_coverage_pct": _pct(documented, len(items)),
        "reference_count": reference_count,
        "catalog_coverage_pct": (
            _pct(len(items), reference_count) if reference_count is not None else None
        ),
    }


def compute_overall_coverage(domain_stats: list[dict[str, Any]]) -> dict[str, Any]:
    total_items = sum(d["item_count"] for d in domain_stats)
    total_documented = sum(d["documented_count"] for d in domain_stats)
    known_reference_domains = [d for d in domain_stats if d["reference_count"] is not None]
    total_reference = sum(d["reference_count"] for d in known_reference_domains)
    total_reference_items = sum(
        d["item_count"] for d in domain_stats if d["reference_count"] is not None
    )
    return {
        "total_items": total_items,
        "total_documented": total_documented,
        "documentation_coverage_pct": _pct(total_documented, total_items),
        "catalog_coverage_pct": (
            _pct(total_reference_items, total_reference) if known_reference_domains else None
        ),
        "domains_with_known_reference_count": len(known_reference_domains),
        "domains_total": len(domain_stats),
    }
