"""Python-only Streamlit web interface for the lead generation agent.

Run:
    streamlit run app.py

The project contains no custom HTML, JavaScript or CSS. Streamlit renders the
browser interface from Python code.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

import config
import places
from lead_generator import collect_leads, validate_pincode


st.set_page_config(
    page_title="Lead Generation Agent",
    page_icon="🔎",
    layout="wide",
)

st.title("Lead Generation Agent")
st.caption(
    "Find local businesses by category and pincode, including phone, email, "
    "website, Instagram and Facebook details when publicly available."
)

with st.form("lead_search_form"):
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        pincode = st.text_input("Pincode", placeholder="Example: 700075")
    with col2:
        domain = st.text_input(
            "Business Domain / Category",
            placeholder="Example: restaurant, gym, salon",
        )
    with col3:
        min_records = st.number_input(
            "Minimum Records",
            min_value=1,
            max_value=200,
            value=int(config.MIN_RECORDS),
            step=1,
        )

    submitted = st.form_submit_button("Generate Leads", type="primary")

if submitted:
    clean_pincode = pincode.strip()
    clean_domain = domain.strip()

    if not validate_pincode(clean_pincode):
        st.error("Invalid pincode. Enter digits only (4 to 10 digits).")
        st.stop()
    if not clean_domain:
        st.error("Please enter a business domain/category.")
        st.stop()

    status_box = st.status("Starting lead search...", expanded=True)
    metric_placeholder = st.empty()
    table_placeholder = st.empty()

    def show_progress(event: dict) -> None:
        records = event.get("records") or []
        candidates = int(event.get("total_candidates") or 0)
        page = int(event.get("current_page") or 0)
        skipped = int(event.get("skipped_no_phone") or 0)
        message = event.get("message") or "Working..."

        status_box.write(message)
        with metric_placeholder.container():
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Leads Collected", len(records))
            m2.metric("Candidates Seen", candidates)
            m3.metric("Current Page", page)
            m4.metric("Skipped: No Phone", skipped)

        if records:
            preview = pd.DataFrame(
                [
                    {
                        "Business Name": row.get("name", ""),
                        "Address": row.get("address", ""),
                        "Phone Number": row.get("phone", ""),
                        "Email ID": row.get("email", ""),
                        "Website": row.get("website", ""),
                        "Instagram": row.get("instagram", ""),
                        "Facebook": row.get("facebook", ""),
                    }
                    for row in records
                ]
            )
            table_placeholder.dataframe(preview, use_container_width=True, hide_index=True)

    try:
        result = collect_leads(
            pincode=clean_pincode,
            domain=clean_domain,
            min_records=int(min_records),
            progress_callback=show_progress,
            export_excel=True,
        )
    except places.PlacesAPIError as exc:
        status_box.update(label="Lead search failed", state="error", expanded=True)
        st.error(str(exc))
    except ValueError as exc:
        status_box.update(label="Invalid input", state="error", expanded=True)
        st.error(str(exc))
    except Exception as exc:  # noqa: BLE001
        status_box.update(label="Unexpected error", state="error", expanded=True)
        st.error(f"Unexpected error: {exc}")
    else:
        records = result["records"]
        status_box.update(
            label="Lead search completed",
            state="complete",
            expanded=False,
        )

        st.subheader(f"Results ({len(records)})")
        st.info(result["message"])
        st.caption(
            f"Candidates seen: {result['total_candidates']} | "
            f"Skipped without phone: {result['skipped_no_phone']} | "
            f"Duration: {result['duration']} seconds"
        )

        if records:
            final_df = pd.DataFrame(
                [
                    {
                        "Business Name": row.get("name", ""),
                        "Address": row.get("address", ""),
                        "Phone Number": row.get("phone", ""),
                        "Email ID": row.get("email", ""),
                        "Website": row.get("website", ""),
                        "Instagram": row.get("instagram", ""),
                        "Facebook": row.get("facebook", ""),
                    }
                    for row in records
                ]
            )
            st.dataframe(final_df, use_container_width=True, hide_index=True)

            output_path = Path(result["output_path"])
            if output_path.exists():
                with output_path.open("rb") as excel_file:
                    st.download_button(
                        "Download Excel",
                        data=excel_file.read(),
                        file_name=output_path.name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                    )
        else:
            st.warning("No results to display.")

st.divider()
st.caption(
    "Data is gathered from Google Places and publicly accessible business websites. "
    "Email and social links are best-effort results and may not be available for every business."
)
