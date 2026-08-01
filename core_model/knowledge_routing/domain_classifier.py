"""Deterministic knowledge-domain + subdomain classification (Step 3).

Same bilingual-keyword-lexicon-plus-scoring approach as
`intent_classifier`, loaded from the checksummed policy file. Domain and
subdomain are scored independently -- a subdomain match only applies
within its own declared parent domain's keyword hits, so a subdomain
can be more specific evidence for (never a replacement for) its parent.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core_model.knowledge_routing import POLICY_VERSION, SUBDOMAINS_BY_DOMAIN
from core_model.knowledge_routing.policy_loader import get_policy
from core_model.knowledge_routing.reason_codes import DOMAIN_REASON_CODE_BY_VALUE


def _hits(text_lower: str, lexicon: list[str]) -> tuple[str, ...]:
    return tuple(word for word in lexicon if word and word.lower() in text_lower)


@dataclass(frozen=True)
class DomainResult:
    domain: str
    subdomain: str | None
    confidence_band: str
    reason_codes: tuple[str, ...]
    matched_rules: tuple[str, ...]
    policy_version: str
    secondary_domains: tuple[str, ...] = field(default_factory=tuple)


def classify_domain(text: str) -> DomainResult:
    policy = get_policy()
    text_lower = text.lower()
    domain_lexicons = policy.get("domains", {})

    scored: list[tuple[str, tuple[str, ...]]] = []
    for domain, entry in domain_lexicons.items():
        hits = _hits(text_lower, entry.get("keywords_en", [])) + _hits(
            text_lower, entry.get("keywords_ta", [])
        )
        if hits:
            scored.append((domain, hits))

    if not scored:
        return DomainResult(
            domain="unknown",
            subdomain=None,
            confidence_band="unknown",
            reason_codes=(DOMAIN_REASON_CODE_BY_VALUE["unknown"],),
            matched_rules=(),
            policy_version=POLICY_VERSION,
        )

    scored.sort(key=lambda pair: len(pair[1]), reverse=True)
    primary_domain, primary_hits = scored[0]
    secondary = tuple(domain for domain, _ in scored[1:] if domain != primary_domain)

    subdomain = None
    subdomain_hits: tuple[str, ...] = ()
    subdomain_lexicons = domain_lexicons.get(primary_domain, {}).get("subdomains", {})
    best_subdomain_score = 0
    for candidate_sub in SUBDOMAINS_BY_DOMAIN.get(primary_domain, ()):
        entry = subdomain_lexicons.get(candidate_sub, {})
        hits = _hits(text_lower, entry.get("keywords_en", [])) + _hits(
            text_lower, entry.get("keywords_ta", [])
        )
        if len(hits) > best_subdomain_score:
            best_subdomain_score = len(hits)
            subdomain = candidate_sub
            subdomain_hits = hits

    reason_codes = [DOMAIN_REASON_CODE_BY_VALUE[primary_domain]]
    if subdomain:
        reason_codes.append(DOMAIN_REASON_CODE_BY_VALUE[subdomain])

    confidence_band = "high" if len(primary_hits) >= 2 or subdomain_hits else "medium"
    all_matched = tuple(dict.fromkeys((*primary_hits, *subdomain_hits)))

    return DomainResult(
        domain=primary_domain,
        subdomain=subdomain,
        confidence_band=confidence_band,
        reason_codes=tuple(reason_codes),
        matched_rules=all_matched,
        policy_version=POLICY_VERSION,
        secondary_domains=secondary,
    )


__all__ = ["DomainResult", "classify_domain"]
