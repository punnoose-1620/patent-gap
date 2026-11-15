"""
First-fetch search_limitations seeding.

After patent page isolation (in-memory case_data) and before create_case:
  1) Classify commercial layer + sellable unit + buyer + justification
  2) Suggest companies + typed URLs locked to that classification
Validate through add_limitations (separate retry budgets), then leave accepts
on case_data for persist. Fail closed: if step 1 never completes, skip step 2.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from structures.cases import (
    _commercial_classification_complete,
    add_limitations,
)

MAX_CLASSIFY_ATTEMPTS = 3
MAX_COMPANY_ATTEMPTS = 5

COMMERCIAL_LAYER_DEFINITIONS = """
commercial_layer must be EXACTLY one of the following. Read the full meaning
before choosing — the label alone is not enough.

finished_device:
  The patent’s commercially relevant offering is a complete product a buyer
  purchases and uses as a whole unit (appliance, tool, finished instrument,
  packaged device). Claims describe the assembled product or its user-facing
  system, not only a replaceable sub-part sold on its own.

component_part:
  The commercially relevant offering is a part, module, fitting, chip, or
  subsystem that is manufactured and sold as its own product line, typically
  for integration into a larger machine. Prefer this when the invention is the
  part itself even if that part later sits inside a finished device.

medicine_consumable:
  The commercially relevant offering is a drug, biologic, diagnostic reagent,
  cartridge, or other consumable that is sold for use-up / replenishment rather
  than as durable equipment.

software_service:
  The commercially relevant offering is software, a hosted platform, a network
  function, or a subscription service that customers license or operate. Prefer
  this for core-network / cloud / SaaS style inventions even when hardware
  exists nearby in the same industry.

method_only:
  The claims are primarily a process or method with no clear standalone product
  SKU. Commercial focus is sparse: assignees and clear implementers of that
  process only. Use this when forcing a product layer would invent a product
  that the patent does not really sell.
""".strip()

SEED_CLASSIFY_PROMPT = """
You classify the commercial focus for a patent case on FIRST fetch only.
Do NOT suggest companies or URLs in this step.

Goal: decide what is actually sold because of this patent, who buys it, and
which commercial_layer that maps to. The user may edit suggestions later.

""" + COMMERCIAL_LAYER_DEFINITIONS + """

Required outputs:
1) sellable_unit — short phrase for the thing a customer would buy (product /
   part / drug / software function / process implementation). Be specific
   (e.g. "5G core AUSF / subscriber identity function", not just "5G").
2) buyer — who purchases that sellable unit (e.g. mobile network operators,
   furniture OEMs, hospitals, consumers).
3) commercial_layer — exactly one enum value from the definitions above.
4) why_this_layer — 1–3 sentences tying title/claims to that layer and
   sellable_unit. Explain why adjacent layers were not chosen.

Rules:
- Choose the layer of the sellable unit itself, not the broad industry.
- If unsure between finished_device and component_part, ask: would a buyer
  purchase this as a standalone SKU, or only as part of a larger finished good?
- If fixing prior errors, correct only the failing fields.

Return JSON matching the schema.

Patent context:
Title: <title_replacement>
Description: <description_replacement>
Assignees / applicants / inventors:
<owners_replacement>
Keywords: <keywords_replacement>
Claims (excerpt):
<claims_replacement>

Prior validation errors to fix (if any):
<errors_replacement>
""".strip()

SEED_COMPANIES_PROMPT = """
You seed search_limitations companies and URLs for a patent case on FIRST fetch.
Classification is already locked — do NOT change commercial_layer, sellable_unit,
buyer, or why_this_layer.

Locked classification:
- commercial_layer: <layer_replacement>
- sellable_unit: <sellable_unit_replacement>
- buyer: <buyer_replacement>
- why_this_layer: <why_replacement>

Company rules:
- Only list brands or factories that make or sell this specific sellable_unit
  as a commercial offering (or a direct commercial equivalent).
- For finished_device: list OEMs / brands that manufacture or brand that finished
  sellable unit (the product the buyer purchases).
- For component_part, medicine_consumable, software_service, and method_only:
  list brands or factories that make or sell that sellable unit itself — not
  the last consumer point of contact for a larger finished good that merely
  contains or uses it.
- Each reason must name the company’s offering in product language (product
  line / SKU class) matching the sellable_unit, not only the broad industry.
- Include assignees/applicants when they are real commercial entities that sell
  the sellable_unit.
- Prefer well-known searchable names. If unsure a company sells this unit, omit
  rather than guess. Propose about 3–8 companies.
- For each company provide name, reason, and confidence (high|medium|low).

URL rules:
- Optionally add URLs in buckets:
  - home_page: official company/product home pages for the listed makers
  - product_listings: manufacturer product-section roots for the sellable_unit
  - support_docs: support / downloads / manuals hubs for those brands
- Prefer manufacturer / OEM / vendor sites. Marketplace or retailer storefronts
  are not valid focus URLs.
- If unsure a URL is currently live and applicable, omit it. Prefer an empty
  URL list over a questionable link.
- Do NOT resubmit companies/URLs listed under Already accepted.
- If fixing prior errors, only submit replacements for failed items (or new
  candidates).

Return JSON matching the schema.

Patent context:
Title: <title_replacement>
Description: <description_replacement>
Assignees / applicants / inventors:
<owners_replacement>
Keywords: <keywords_replacement>
Claims (excerpt):
<claims_replacement>

Already accepted companies (do not alter/resubmit):
<accepted_companies_replacement>

Already accepted URLs (do not alter/resubmit):
<accepted_urls_replacement>

Prior validation errors to fix (if any):
<errors_replacement>
""".strip()


class CommercialClassificationSuggestion(BaseModel):
    sellable_unit: str = Field(
        description="Specific thing a customer would buy for this patent"
    )
    buyer: str = Field(description="Who purchases that sellable unit")
    commercial_layer: str = Field(
        description=(
            "finished_device|component_part|medicine_consumable|"
            "software_service|method_only"
        )
    )
    why_this_layer: str = Field(
        description="1–3 sentences tying claims to the chosen layer"
    )


class SuggestedCompany(BaseModel):
    name: str = Field(description="Company or brand name")
    reason: str = Field(
        description="Why this company sells the locked sellable_unit"
    )
    confidence: str = Field(description="high, medium, or low")


class SuggestedLimitationUrls(BaseModel):
    home_page: list[str] = Field(default_factory=list)
    product_listings: list[str] = Field(default_factory=list)
    support_docs: list[str] = Field(default_factory=list)


class SearchLimitationsCompaniesSuggestion(BaseModel):
    companies: list[SuggestedCompany] = Field(default_factory=list)
    urls: SuggestedLimitationUrls = Field(default_factory=SuggestedLimitationUrls)


def _owners_blob(case_data: dict) -> str:
    parts: list[str] = []
    for key in (
        "current_assignee",
        "assignee",
        "applicant",
        "inventors",
        "owners",
    ):
        value = case_data.get(key)
        if isinstance(value, list):
            for item in value:
                text = str(item or "").strip()
                if text:
                    parts.append(f"- {key}: {text}")
        elif isinstance(value, str) and value.strip():
            parts.append(f"- {key}: {value.strip()}")
    return "\n".join(parts) or "(none)"


def _claims_excerpt(case_data: dict, limit: int = 8) -> str:
    claims = case_data.get("claims")
    lines: list[str] = []
    if isinstance(claims, list):
        for item in claims[:limit]:
            if isinstance(item, str) and item.strip():
                lines.append(f"- {item.strip()[:500]}")
            elif isinstance(item, dict):
                text = (
                    item.get("documented_claim")
                    or item.get("claim")
                    or item.get("text")
                    or item.get("market_language_claim")
                    or ""
                )
                if str(text).strip():
                    lines.append(f"- {str(text).strip()[:500]}")
    elif isinstance(claims, dict):
        for key, value in list(claims.items())[:limit]:
            if isinstance(value, dict):
                text = value.get("documented_claim") or value.get("claim") or ""
                if str(text).strip():
                    lines.append(f"- {key}: {str(text).strip()[:500]}")
            elif isinstance(value, str) and value.strip():
                lines.append(f"- {key}: {value.strip()[:500]}")
    return "\n".join(lines) or "(none)"


def _keywords_blob(case_data: dict) -> str:
    keywords = case_data.get("keywords") or []
    if isinstance(keywords, str):
        return keywords.strip() or "(none)"
    if isinstance(keywords, list):
        return ", ".join(str(k).strip() for k in keywords if str(k).strip()) or "(none)"
    return "(none)"


def _limitations_already_populated(limitations: dict) -> bool:
    companies = limitations.get("companies") or []
    urls = limitations.get("urls") or []
    has_companies = isinstance(companies, list) and any(
        str(c).strip() for c in companies
    )
    has_urls = isinstance(urls, list) and any(str(u).strip() for u in urls)
    return bool(has_companies or has_urls)


def _patent_context_replacements(case_data: dict) -> dict[str, str]:
    return {
        "<title_replacement>": str(case_data.get("title") or "").strip()
        or "(untitled)",
        "<description_replacement>": (
            str(case_data.get("description") or "").strip()[:4000] or "(none)"
        ),
        "<owners_replacement>": _owners_blob(case_data),
        "<keywords_replacement>": _keywords_blob(case_data),
        "<claims_replacement>": _claims_excerpt(case_data),
    }


def _apply_replacements(template: str, replacements: dict[str, str]) -> str:
    out = template
    for key, value in replacements.items():
        out = out.replace(key, value)
    return out


def _suggest_commercial_classification(
    case_data: dict,
    *,
    prior_errors: list[str],
) -> CommercialClassificationSuggestion:
    from llm_brain.gemini import Gemini

    replacements = _patent_context_replacements(case_data)
    replacements["<errors_replacement>"] = (
        "\n".join(f"- {e}" for e in prior_errors) or "(none)"
    )
    prompt = _apply_replacements(SEED_CLASSIFY_PROMPT, replacements)
    api = Gemini()._client
    response = api.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_json_schema": CommercialClassificationSuggestion.model_json_schema(),
        },
    )
    return CommercialClassificationSuggestion.model_validate_json(response.text)


def _suggest_companies_and_urls(
    case_data: dict,
    *,
    limitations: dict,
    accepted_companies: list[str],
    accepted_urls: list[str],
    prior_errors: list[str],
) -> SearchLimitationsCompaniesSuggestion:
    from llm_brain.gemini import Gemini

    replacements = _patent_context_replacements(case_data)
    replacements.update(
        {
            "<layer_replacement>": str(
                limitations.get("commercial_layer") or ""
            ).strip()
            or "(missing)",
            "<sellable_unit_replacement>": str(
                limitations.get("sellable_unit") or ""
            ).strip()
            or "(missing)",
            "<buyer_replacement>": str(limitations.get("buyer") or "").strip()
            or "(missing)",
            "<why_replacement>": str(
                limitations.get("why_this_layer") or ""
            ).strip()
            or "(missing)",
            "<accepted_companies_replacement>": (
                "\n".join(f"- {c}" for c in accepted_companies) or "(none)"
            ),
            "<accepted_urls_replacement>": (
                "\n".join(f"- {u}" for u in accepted_urls) or "(none)"
            ),
            "<errors_replacement>": (
                "\n".join(f"- {e}" for e in prior_errors) or "(none)"
            ),
        }
    )
    prompt = _apply_replacements(SEED_COMPANIES_PROMPT, replacements)
    api = Gemini()._client
    response = api.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_json_schema": SearchLimitationsCompaniesSuggestion.model_json_schema(),
        },
    )
    return SearchLimitationsCompaniesSuggestion.model_validate_json(response.text)


def _run_classify_step(
    case_data: dict,
    limitations: dict,
    *,
    max_attempts: int,
) -> tuple[dict, list[str], int]:
    """Step 1: persist commercial classification. Fail closed on errors."""
    prior_errors: list[str] = []
    attempts = 0
    last_result: dict[str, Any] = {}

    while attempts < max_attempts:
        attempts += 1
        try:
            suggestion = _suggest_commercial_classification(
                case_data, prior_errors=prior_errors
            )
        except Exception as exc:
            prior_errors = [f"classification_failed: {type(exc).__name__}: {exc}"]
            print(
                f"LOG: search_limitations classify attempt {attempts} failed "
                f"({type(exc).__name__}: {exc})",
                flush=True,
            )
            continue

        last_result = add_limitations(
            limitations,
            commercial_layer=suggestion.commercial_layer,
            sellable_unit=suggestion.sellable_unit,
            buyer=suggestion.buyer,
            why_this_layer=suggestion.why_this_layer,
            companies=None,
            urls=None,
        )
        limitations = last_result["search_limitations"]
        case_data["search_limitations"] = limitations
        prior_errors = list(last_result.get("errors") or [])
        print(
            f"LOG: search_limitations classify attempt {attempts}: "
            f"layer={last_result.get('commercial_layer')!r} "
            f"sellable_unit={last_result.get('sellable_unit')!r} "
            f"buyer={last_result.get('buyer')!r} "
            f"errors={len(prior_errors)}",
            flush=True,
        )
        if not prior_errors and _commercial_classification_complete(limitations):
            break

    return limitations, prior_errors, attempts


def _run_companies_step(
    case_data: dict,
    limitations: dict,
    *,
    max_attempts: int,
) -> tuple[dict, list[str], int]:
    """Step 2: companies + URLs locked to existing classification."""
    prior_errors: list[str] = []
    attempts = 0

    while attempts < max_attempts:
        attempts += 1
        try:
            suggestion = _suggest_companies_and_urls(
                case_data,
                limitations=limitations,
                accepted_companies=list(limitations.get("companies") or []),
                accepted_urls=list(limitations.get("urls") or []),
                prior_errors=prior_errors,
            )
        except Exception as exc:
            prior_errors = [f"suggestion_failed: {type(exc).__name__}: {exc}"]
            print(
                f"LOG: search_limitations companies attempt {attempts} failed "
                f"({type(exc).__name__}: {exc})",
                flush=True,
            )
            continue

        urls_payload = {
            "home_page": list(suggestion.urls.home_page or []),
            "product_listings": list(suggestion.urls.product_listings or []),
            "support_docs": list(suggestion.urls.support_docs or []),
        }
        companies_payload = [
            {
                "name": row.name,
                "reason": row.reason,
                "confidence": row.confidence,
            }
            for row in (suggestion.companies or [])
        ]
        last_result = add_limitations(
            limitations,
            companies=companies_payload,
            urls=urls_payload,
        )
        limitations = last_result["search_limitations"]
        case_data["search_limitations"] = limitations
        prior_errors = list(last_result.get("errors") or [])
        print(
            f"LOG: search_limitations companies attempt {attempts}: "
            f"new_companies={last_result.get('newly_accepted_companies')} "
            f"new_urls={len(last_result.get('newly_accepted_urls') or [])} "
            f"errors={len(prior_errors)} "
            f"layer={last_result.get('commercial_layer')}",
            flush=True,
        )
        if not prior_errors:
            break

    return limitations, prior_errors, attempts


def seed_search_limitations_on_fetch(
    case_data: dict,
    *,
    max_classify_attempts: int = MAX_CLASSIFY_ATTEMPTS,
    max_company_attempts: int = MAX_COMPANY_ATTEMPTS,
    max_attempts: int | None = None,
) -> dict[str, Any]:
    """
    Seed case_data['search_limitations'] before create_case.

    Skips when companies/urls already present. Otherwise:
      1) Gemini commercial classification → add_limitations
      2) Only if classification complete: Gemini companies/URLs → add_limitations
    Fail closed if step 1 never completes. Mutates case_data in place.

    max_attempts (legacy): if set, used as max_company_attempts.
    """
    if max_attempts is not None:
        max_company_attempts = max_attempts

    if not isinstance(case_data, dict):
        return {"skipped": True, "reason": "invalid_case_data"}

    limitations = case_data.get("search_limitations")
    if not isinstance(limitations, dict):
        limitations = {}
        case_data["search_limitations"] = limitations

    if _limitations_already_populated(limitations):
        print(
            "LOG: search_limitations seed skipped (already populated)",
            flush=True,
        )
        return {
            "skipped": True,
            "reason": "already_populated",
            "search_limitations": limitations,
        }

    classify_errors: list[str] = []
    company_errors: list[str] = []
    classify_attempts = 0
    company_attempts = 0

    if not _commercial_classification_complete(limitations):
        limitations, classify_errors, classify_attempts = _run_classify_step(
            case_data,
            limitations,
            max_attempts=max_classify_attempts,
        )

    if not _commercial_classification_complete(limitations):
        print(
            "LOG: search_limitations seed fail-closed after classify "
            f"(errors={len(classify_errors)})",
            flush=True,
        )
        case_data["search_limitations"] = limitations
        return {
            "skipped": False,
            "classify_attempts": classify_attempts,
            "company_attempts": 0,
            "attempts": classify_attempts,
            "search_limitations": limitations,
            "errors": classify_errors,
            "ok": False,
            "accepted_companies": list(limitations.get("companies") or []),
            "accepted_urls": list(limitations.get("urls") or []),
            "commercial_layer": limitations.get("commercial_layer"),
            "sellable_unit": limitations.get("sellable_unit"),
            "buyer": limitations.get("buyer"),
            "why_this_layer": limitations.get("why_this_layer"),
        }

    limitations, company_errors, company_attempts = _run_companies_step(
        case_data,
        limitations,
        max_attempts=max_company_attempts,
    )

    from structures.cases import (
        _exact_dedupe_strings,
        _fuzzy_dedupe_strings,
        _normalize_url_key,
    )

    limitations["companies"] = _fuzzy_dedupe_strings(
        limitations.get("companies") or []
    )
    limitations["urls"] = _exact_dedupe_strings(
        limitations.get("urls") or [], key_fn=_normalize_url_key
    )
    case_data["search_limitations"] = limitations

    prior_errors = company_errors or classify_errors
    return {
        "skipped": False,
        "classify_attempts": classify_attempts,
        "company_attempts": company_attempts,
        "attempts": classify_attempts + company_attempts,
        "search_limitations": limitations,
        "errors": prior_errors,
        "ok": len(prior_errors) == 0,
        "accepted_companies": list(limitations.get("companies") or []),
        "accepted_urls": list(limitations.get("urls") or []),
        "commercial_layer": limitations.get("commercial_layer"),
        "sellable_unit": limitations.get("sellable_unit"),
        "buyer": limitations.get("buyer"),
        "why_this_layer": limitations.get("why_this_layer"),
    }
