"""Phase 20 Step 3 -- Web query classification.

A pure mapping from Phase 17's *already-computed* domain/subdomain/
freshness onto one of the five Step-2 Web categories -- never a
reclassification of Phase 17's own decision (that stays sealed). This
only decides which `source_category_rules` entry in the trust policy
applies to this particular Web attempt.
"""

from __future__ import annotations

from core_model.web_search import WEB_QUERY_CATEGORIES


def classify_web_category(*, domain: str | None, subdomain: str | None, freshness: str) -> str:
    if subdomain == "software_documentation":
        category = "current_software_documentation"
    elif domain == "government_services" and subdomain == "legal_or_regulatory_current":
        category = "current_rules_and_regulations"
    elif domain == "government_services":
        category = "government_service_information"
    elif subdomain in ("technical_industry", "business_process"):
        category = "official_product_documentation"
    else:
        category = "current_general_information"

    assert category in WEB_QUERY_CATEGORIES
    return category


__all__ = ["classify_web_category"]
