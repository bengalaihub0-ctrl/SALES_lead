"""Core lead-generation workflow shared by the Streamlit UI and CLI."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Callable, Any

import config
import places
import website_finder
from exporter import export_to_excel

logger = config.get_logger(__name__)

PINCODE_PATTERN = re.compile(r"^\d{4,10}$")
ProgressCallback = Callable[[dict[str, Any]], None]


def validate_pincode(pincode: str) -> bool:
    """Return True when *pincode* contains 4-10 digits only."""
    return bool(PINCODE_PATTERN.fullmatch(pincode.strip()))


def _notify(callback: ProgressCallback | None, **payload: Any) -> None:
    if callback is not None:
        callback(payload)


def collect_leads(
    pincode: str,
    domain: str,
    min_records: int = config.MIN_RECORDS,
    progress_callback: ProgressCallback | None = None,
    export_excel: bool = True,
) -> dict[str, Any]:
    """Collect local-business leads and optionally export them to Excel.

    Returns a dictionary containing records, counts, duration, a message and
    the generated Excel path (when ``export_excel`` is True and records exist).
    """
    started_at = datetime.now(timezone.utc)
    pincode = pincode.strip()
    domain = domain.strip()

    if not validate_pincode(pincode):
        raise ValueError("Invalid pincode. Enter digits only (4 to 10 digits).")
    if not domain:
        raise ValueError("Business domain/category is required.")
    if not 1 <= int(min_records) <= 200:
        raise ValueError("Minimum records must be between 1 and 200.")

    min_records = int(min_records)
    query = f"{domain} in {pincode}"
    logger.info("Starting lead search: pincode=%s domain=%s", pincode, domain)

    records: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    skipped_no_phone = 0
    page_token: str | None = None
    total_candidates = 0
    current_page = 0

    _notify(
        progress_callback,
        stage="starting",
        message="Starting lead search...",
        records=records.copy(),
        total_candidates=0,
        skipped_no_phone=0,
        current_page=0,
    )

    for page_index in range(config.MAX_PAGES):
        current_page = page_index + 1
        stubs, page_token = places.text_search_page(query, page_token)
        total_candidates += len(stubs)

        _notify(
            progress_callback,
            stage="searching",
            message=f"Processing search page {current_page}...",
            records=records.copy(),
            total_candidates=total_candidates,
            skipped_no_phone=skipped_no_phone,
            current_page=current_page,
        )

        for stub in stubs:
            place_id = stub.get("id")
            if not place_id or place_id in seen_ids:
                continue
            seen_ids.add(place_id)

            details = places.get_place_details(place_id)
            if not details:
                continue

            phone = details.get("internationalPhoneNumber", "")
            if not phone:
                skipped_no_phone += 1
                _notify(
                    progress_callback,
                    stage="processing",
                    message="Skipping a business without a phone number...",
                    records=records.copy(),
                    total_candidates=total_candidates,
                    skipped_no_phone=skipped_no_phone,
                    current_page=current_page,
                )
                continue

            website = details.get("websiteUri")
            contact = website_finder.gather_contact_info(website) if website else {}

            record = {
                "place_id": place_id,
                "name": details.get("displayName", {}).get("text", ""),
                "address": details.get("formattedAddress", ""),
                "phone": phone,
                "website": website or "",
                "email": contact.get("email") or "",
                "instagram": contact.get("instagram") or "",
                "facebook": contact.get("facebook") or "",
                "source": "google_places",
                "captured_at": datetime.now(timezone.utc).isoformat(),
            }
            records.append(record)

            _notify(
                progress_callback,
                stage="processing",
                message=f"Collected {len(records)} lead(s)...",
                records=records.copy(),
                total_candidates=total_candidates,
                skipped_no_phone=skipped_no_phone,
                current_page=current_page,
            )

            if len(records) >= min_records:
                break

        logger.info(
            "Page %d: %d lead(s) with phone collected (%d candidates seen)",
            current_page,
            len(records),
            total_candidates,
        )

        if len(records) >= min_records or not page_token:
            break

    output_path = ""
    if records and export_excel:
        safe_domain = re.sub(r"\W+", "_", domain.lower()).strip("_") or "business"
        filename = f"leads_{pincode}_{safe_domain}.xlsx"
        output_path = export_to_excel(records, filename)

    duration = round((datetime.now(timezone.utc) - started_at).total_seconds(), 1)

    if not records:
        message = "No businesses with phone numbers were found for this search."
    elif len(records) < min_records:
        message = (
            f"Found {len(records)} lead(s). Fewer than the requested {min_records} "
            "records were available with phone numbers."
        )
    else:
        message = f"Collected {len(records)} lead(s) successfully."

    result = {
        "records": records,
        "total_candidates": total_candidates,
        "skipped_no_phone": skipped_no_phone,
        "current_page": current_page,
        "duration": duration,
        "message": message,
        "output_path": output_path,
    }

    _notify(progress_callback, stage="done", **result)
    logger.info(
        "Lead search complete: records=%d candidates=%d duration=%.1fs",
        len(records),
        total_candidates,
        duration,
    )
    return result
