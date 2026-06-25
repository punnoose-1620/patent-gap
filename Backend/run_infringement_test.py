"""One-off test runner for live infringement analysis on EP1434512."""
import json
import sys
import threading
import time

from app import app
from controller import start_patent_analysis, start_product_analysis
from models.cases import get_case_by_id, update_case

CASE_ID = "googlepatents_6f6b00e6-af66-4588-8cbe-7b8c2205f66d_EP1434512"
POLL_SECONDS = 120


def _bucket_claims(case_data):
    ref_claims = case_data.get("claims")
    original_lang_asserted_claims = []
    original_lang_independent_claims = []
    original_lang_core_claims = []
    original_lang_pivotal_claims = []
    market_lang_asserted_claims = []
    market_lang_independent_claims = []
    market_lang_core_claims = []
    market_lang_pivotal_claims = []
    search_type = "bucketed"

    if isinstance(ref_claims, list):
        search_type = "generic"
        original_lang_asserted_claims = list(ref_claims)
    elif isinstance(ref_claims, dict):
        for claim_data in ref_claims.values():
            claim_type = claim_data.get("claim_type")
            if claim_type == "asserted_claim":
                original_lang_asserted_claims.append(claim_data.get("documented_claim", ""))
                market_lang_asserted_claims.append(claim_data.get("market_language_claim", ""))
            elif claim_type == "independent_claim":
                original_lang_independent_claims.append(claim_data.get("documented_claim", ""))
                market_lang_independent_claims.append(claim_data.get("market_language_claim", ""))
            elif claim_type == "core_claim":
                original_lang_core_claims.append(claim_data.get("documented_claim", ""))
                market_lang_core_claims.append(claim_data.get("market_language_claim", ""))
            elif claim_type == "pivotal_claim":
                original_lang_pivotal_claims.append(claim_data.get("documented_claim", ""))
                market_lang_pivotal_claims.append(claim_data.get("market_language_claim", ""))

    return (
        search_type,
        original_lang_asserted_claims,
        original_lang_independent_claims,
        original_lang_core_claims,
        original_lang_pivotal_claims,
        market_lang_asserted_claims,
        market_lang_independent_claims,
        market_lang_core_claims,
        market_lang_pivotal_claims,
    )


def _print_snapshot(label):
    case = get_case_by_id(CASE_ID) or {}
    infringements = case.get("infringements") or []
    print(f"\n=== {label} @ {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
    print(f"title: {case.get('title')}")
    print(f"infringement_analysis_status: {case.get('infringement_analysis_status')}")
    print(f"patent_analysis_time_taken: {case.get('patent_analysis_time_taken')}")
    print(f"product_analysis_time_taken: {case.get('product_analysis_time_taken')}")
    print(f"patent_status_flags: {json.dumps(case.get('patent_status_flags', {}), indent=2)}")
    print(f"product_status_flags: {json.dumps(case.get('product_status_flags', {}), indent=2)}")
    print(f"infringements count: {len(infringements)}")
    if infringements:
        sample = infringements[:3]
        for idx, item in enumerate(sample, 1):
            title = item.get("title") or item.get("product_name") or item.get("_id")
            print(f"  sample {idx}: {title}")
    sys.stdout.flush()


def _analysis_finished(status):
    if not status:
        return False
    if status.startswith("Error"):
        return True
    return status.strip().lower() == "completed"


def main():
    case_data = get_case_by_id(CASE_ID)
    if not case_data:
        raise SystemExit(f"Case not found: {CASE_ID}")

    (
        search_type,
        original_lang_asserted_claims,
        original_lang_independent_claims,
        original_lang_core_claims,
        original_lang_pivotal_claims,
        market_lang_asserted_claims,
        market_lang_independent_claims,
        market_lang_core_claims,
        market_lang_pivotal_claims,
    ) = _bucket_claims(case_data)

    keywords = case_data.get("keywords") or []
    owners = case_data.get("owners") or []
    if not owners:
        owners = list(case_data.get("current_assignee") or [])
        if case_data.get("applicant"):
            owners.append(case_data["applicant"])
        owners.extend(case_data.get("inventors") or [])
        owners = [o.strip() for o in owners if isinstance(o, str) and o.strip()]

    country = case_data.get("country", "")
    ref_case_title = case_data.get("title", "")
    ids_to_avoid = case_data.get("excluded_case_ids", [])
    ref_case_id = case_data.get("_id", "").split("_")[-1]
    titles_to_avoid = case_data.get("excluded_case_titles", [])
    search_limitations = case_data.get("search_limitations", {})

    print(f"Starting analysis for {CASE_ID}")
    print(f"keywords: {keywords}")
    print(
        "claim buckets:",
        len(original_lang_asserted_claims),
        len(original_lang_independent_claims),
        len(original_lang_core_claims),
        len(original_lang_pivotal_claims),
    )

    update_case(
        CASE_ID,
        {
            "infringements": [],
            "product_analysis_time_taken": "",
            "patent_analysis_time_taken": "",
        },
    )

    patent_thread = threading.Thread(
        target=start_patent_analysis,
        name=f"patent_analysis_{CASE_ID}",
        args=(
            app,
            CASE_ID,
            keywords,
            country,
            ref_case_title,
            ref_case_id,
            titles_to_avoid,
            ids_to_avoid,
            search_type,
            original_lang_asserted_claims,
            original_lang_independent_claims,
            original_lang_core_claims,
            original_lang_pivotal_claims,
        ),
        daemon=False,
    )
    product_thread = threading.Thread(
        target=start_product_analysis,
        name=f"product_analysis_{CASE_ID}",
        args=(
            app,
            CASE_ID,
            keywords,
            owners,
            search_limitations,
            market_lang_asserted_claims,
            market_lang_independent_claims,
            market_lang_core_claims,
            market_lang_pivotal_claims,
            search_type,
        ),
        daemon=False,
    )

    _print_snapshot("before start")
    patent_thread.start()
    product_thread.start()
    _print_snapshot("immediately after start")

    while True:
        time.sleep(POLL_SECONDS)
        case = get_case_by_id(CASE_ID) or {}
        status = case.get("infringement_analysis_status", "")
        _print_snapshot("poll")
        if _analysis_finished(status):
            break
        if not patent_thread.is_alive() and not product_thread.is_alive() and status:
            break

    patent_thread.join(timeout=5)
    product_thread.join(timeout=5)
    _print_snapshot("final")


if __name__ == "__main__":
    main()
