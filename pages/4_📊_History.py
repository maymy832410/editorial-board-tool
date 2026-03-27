"""Page 4: History & Tools — sent log, bounce import, retraction data."""

import io
import streamlit as st
import pandas as pd

st.header("📊 History & Tools")

# ── Sent invitations log ──
st.subheader("📬 Sent Invitations")

if st.session_state.get("db_ready"):
    try:
        from db_client import get_sent_details, get_sent_count
        total_sent = get_sent_count()
        st.metric("Total Sent", total_sent)

        if total_sent > 0:
            sent_rows = get_sent_details(limit=total_sent)
            df_sent = pd.DataFrame(sent_rows)
            if "sent_at" in df_sent.columns:
                df_sent["sent_at"] = pd.to_datetime(df_sent["sent_at"])
                df_sent = df_sent.sort_values("sent_at", ascending=False)

            st.dataframe(df_sent, use_container_width=True, hide_index=True)

            csv = df_sent.to_csv(index=False)
            st.download_button("📥 Export Sent Log", csv, "sent_invitations.csv", "text/csv")
    except Exception as e:
        st.error(f"Error loading sent log: {e}")
else:
    st.warning("Database not connected. Set DATABASE_URL to view history.")

# ── Bounce log import ──
st.divider()
st.subheader("⚠️ Bounce Log Import")
st.caption("Upload a Brevo bounce export (tab-separated). Columns: Date, Sender, Sender Domain, Recipient, Recipient Domain, Category, Status, Info")

bounce_file = st.file_uploader("Upload bounce log", type=["csv", "tsv", "txt"], key="bounce_upload")

if bounce_file and st.session_state.get("db_ready"):
    try:
        content = bounce_file.getvalue().decode("utf-8")
        # Try tab-separated first, then comma
        try:
            df_bounce = pd.read_csv(io.StringIO(content), sep="\t")
        except Exception:
            df_bounce = pd.read_csv(io.StringIO(content))

        st.write(f"Found {len(df_bounce)} rows. Columns: {list(df_bounce.columns)}")

        # Auto-detect recipient column
        recipient_col = None
        for col in df_bounce.columns:
            if "recipient" in col.lower() and "domain" not in col.lower():
                recipient_col = col
                break
        if not recipient_col:
            recipient_col = st.selectbox("Select email column", df_bounce.columns)

        category_col = None
        for col in df_bounce.columns:
            if "category" in col.lower():
                category_col = col
                break

        info_col = None
        for col in df_bounce.columns:
            if "info" in col.lower():
                info_col = col
                break

        date_col = None
        for col in df_bounce.columns:
            if "date" in col.lower():
                date_col = col
                break

        if st.button("📥 Import Bounces"):
            from db_client import import_bounces
            bounce_records = []
            for _, row in df_bounce.iterrows():
                email = str(row.get(recipient_col, "")).strip()
                if email and "@" in email:
                    bounce_records.append({
                        "email": email.lower(),
                        "category": str(row.get(category_col, "")) if category_col else "",
                        "info": str(row.get(info_col, "")) if info_col else "",
                        "bounced_at": str(row.get(date_col, "")) if date_col else None,
                    })
            count = import_bounces(bounce_records)
            st.success(f"Imported {count} bounced emails")

    except Exception as e:
        st.error(f"Error parsing bounce file: {e}")

# Show current bounced emails
if st.session_state.get("db_ready"):
    try:
        from db_client import get_all_bounced
        bounced = get_all_bounced()
        if bounced:
            st.caption(f"{len(bounced)} bounced emails in database")
            with st.expander("View bounced emails"):
                st.dataframe(pd.DataFrame(bounced), use_container_width=True, hide_index=True)
    except Exception:
        pass

# ── Retraction Watch CSV upload ──
st.divider()
st.subheader("🔴 Retraction Watch Data")
st.caption("Upload a CSV containing retracted author names. Select the name column for matching.")

retraction_file = st.file_uploader("Upload retraction watch CSV", type=["csv"], key="retraction_upload")

if retraction_file:
    try:
        df_ret = pd.read_csv(retraction_file)
        st.write(f"Found {len(df_ret)} rows. Columns: {list(df_ret.columns)}")

        name_col = st.selectbox("Select author name column", df_ret.columns, key="ret_name_col")

        if st.button("✅ Load Retraction Data"):
            from retraction_checker import RetractionChecker
            checker = RetractionChecker(df_ret, name_col)
            st.session_state.retraction_checker = checker
            st.success(f"Loaded {len(checker.names_lower)} retracted author names for matching")
    except Exception as e:
        st.error(f"Error loading retraction file: {e}")

if st.session_state.get("retraction_checker"):
    st.success(f"✅ Retraction checker active — {len(st.session_state.retraction_checker.names_lower)} names loaded")

# ── Import previously sent CSV ──
st.divider()
st.subheader("📄 Import Previously Sent")
st.caption("Upload sent_invitations_rows.csv to merge into the database.")

sent_csv = st.file_uploader("Upload sent invitations CSV", type=["csv"], key="sent_csv_upload")

if sent_csv and st.session_state.get("db_ready"):
    try:
        df_sent_upload = pd.read_csv(sent_csv)
        st.write(f"Found {len(df_sent_upload)} rows")

        if st.button("📥 Import Sent Records"):
            from db_client import import_sent_csv
            count = import_sent_csv(df_sent_upload)
            st.success(f"Imported {count} records")
    except Exception as e:
        st.error(f"Error: {e}")

# ── Statistics ──
if st.session_state.get("db_ready"):
    st.divider()
    st.subheader("📈 Statistics")
    try:
        from db_client import get_sent_details
        details = get_sent_details()
        if details:
            df_details = pd.DataFrame(details)
            if "publisher" in df_details.columns:
                st.write("**By Publisher:**")
                pub_counts = df_details["publisher"].value_counts()
                st.bar_chart(pub_counts)

            if "sent_at" in df_details.columns:
                df_details["sent_at"] = pd.to_datetime(df_details["sent_at"])
                df_details["date"] = df_details["sent_at"].dt.date
                st.write("**By Date:**")
                date_counts = df_details["date"].value_counts().sort_index()
                st.line_chart(date_counts)
    except Exception:
        pass
