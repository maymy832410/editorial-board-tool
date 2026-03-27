"""Page 2: Results — review, fetch emails, export."""

import asyncio
import streamlit as st
import pandas as pd

st.header("📋 Search Results")

if not st.session_state.get("search_done") or not st.session_state.get("authors"):
    st.info("No search results yet. Go to **🔍 Search** to find researchers.")
    st.stop()

authors = st.session_state.authors

# ── Top metrics ──
total = len(authors)
with_email = sum(1 for a in authors if a.get("email"))
without_email = total - with_email
retracted = sum(1 for a in authors if a.get("retraction_flag", {}).get("match"))
sent_set = set()
bounced_set = set()
if st.session_state.get("db_ready"):
    try:
        from db_client import get_all_sent, get_all_bounced
        sent_set = {r["orcid_id"] for r in get_all_sent() if r.get("orcid_id")}
        bounced_set = {r["email"].lower() for r in get_all_bounced() if r.get("email")}
    except Exception:
        pass
previously_sent = sum(1 for a in authors if a.get("orcid_id") in sent_set)

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Total", total)
m2.metric("With Email", with_email)
m3.metric("Without Email", without_email)
m4.metric("Retracted", retracted)
m5.metric("Previously Sent", previously_sent)

# ── In-page filters ──
st.subheader("Filter Results")
col1, col2, col3 = st.columns(3)

with col1:
    disciplines = sorted({a.get("discipline") for a in authors if a.get("discipline")})
    filter_disciplines = st.multiselect("Filter by discipline", disciplines, key="filter_disc")

with col2:
    filter_options = st.multiselect(
        "Show",
        ["With email only", "Hide already invited", "Hide retracted"],
        key="filter_show",
    )

with col3:
    filter_institution = st.text_input("Filter by institution", key="filter_inst")

# Apply filters
filtered = list(authors)
if filter_disciplines:
    filtered = [a for a in filtered if a.get("discipline") in filter_disciplines]
if "With email only" in filter_options:
    filtered = [a for a in filtered if a.get("email")]
if "Hide already invited" in filter_options:
    filtered = [a for a in filtered if a.get("orcid_id") not in sent_set]
if "Hide retracted" in filter_options:
    filtered = [a for a in filtered if not a.get("retraction_flag", {}).get("match")]
if filter_institution:
    kw = filter_institution.lower()
    filtered = [a for a in filtered if kw in (a.get("institution") or "").lower()]

st.caption(f"Showing {len(filtered)} of {total} authors")

# ── Fetch Emails button ──
st.divider()

need_email_count = sum(1 for a in filtered if not a.get("email"))
if need_email_count > 0:
    if st.button(f"📧 Fetch Emails for {need_email_count} authors without email", type="primary"):
        from email_pipeline import fetch_emails_batch_async

        progress_bar = st.progress(0, text="Starting email pipeline...")
        status_text = st.empty()

        def update_progress(done, total, stage):
            if total > 0:
                progress_bar.progress(done / total, text=f"{stage}: {done}/{total}")

        # Run async pipeline
        loop = asyncio.new_event_loop()
        updated = loop.run_until_complete(
            fetch_emails_batch_async(
                filtered,
                on_progress=update_progress,
            )
        )
        loop.close()

        progress_bar.empty()
        status_text.empty()

        # Update session state
        # Build a lookup from author_id
        updated_lookup = {}
        for a in updated:
            aid = a.get("author_id")
            if aid:
                updated_lookup[aid] = a

        for i, a in enumerate(st.session_state.authors):
            aid = a.get("author_id")
            if aid and aid in updated_lookup:
                st.session_state.authors[i] = updated_lookup[aid]

        new_emails = sum(1 for a in updated if a.get("email")) - (len(updated) - need_email_count)
        st.success(f"✅ Found **{new_emails}** new emails")
        st.rerun()

# ── Author table ──
st.divider()

# Build display dataframe
rows = []
for a in filtered:
    email = a.get("email", "")
    source = a.get("email_source", "")

    # Retraction badge
    rf = a.get("retraction_flag", {})
    retraction = ""
    if rf.get("match"):
        if rf["type"] == "exact":
            retraction = "🔴 EXACT"
        else:
            retraction = f"🟠 FUZZY ({rf.get('score', '')}%)"

    # Status badge
    status = ""
    orcid = a.get("orcid_id", "")
    if orcid in sent_set:
        status = "✅ SENT"
    if email and email.lower() in bounced_set:
        status = "⚠️ BOUNCED"

    rows.append({
        "Name": a.get("name", ""),
        "H-Index": a.get("h_index", ""),
        "Institution": a.get("institution", ""),
        "Country": a.get("country", ""),
        "Discipline": a.get("discipline", ""),
        "Email": email,
        "Source": source,
        "Retraction": retraction,
        "Status": status,
        "ORCID": orcid,
    })

df = pd.DataFrame(rows)

# Pagination
page_size = 50
total_pages = max(1, (len(df) + page_size - 1) // page_size)
page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, key="results_page")
start_idx = (page - 1) * page_size
end_idx = start_idx + page_size

st.dataframe(
    df.iloc[start_idx:end_idx],
    use_container_width=True,
    hide_index=True,
    column_config={
        "Email": st.column_config.TextColumn("Email", width="medium"),
        "Name": st.column_config.TextColumn("Name", width="medium"),
    },
)

st.caption(f"Page {page} of {total_pages}")

# ── Export ──
st.divider()
col_e1, col_e2 = st.columns(2)
with col_e1:
    csv_all = df.to_csv(index=False)
    st.download_button("📥 Export All (CSV)", csv_all, "authors_all.csv", "text/csv")
with col_e2:
    df_with_email = df[df["Email"] != ""]
    csv_email = df_with_email.to_csv(index=False)
    st.download_button("📥 Export With Email (CSV)", csv_email, "authors_with_email.csv", "text/csv")
