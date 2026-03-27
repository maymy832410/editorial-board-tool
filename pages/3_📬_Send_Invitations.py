"""Page 3: Send Invitations — template selection, bulk/individual send."""

import streamlit as st

from email_sender import EmailSender
from templates import get_template_names, format_template, get_template
from pdf_generator import generate_invitation_pdf

st.header("📬 Send Invitations")

if not st.session_state.get("authors"):
    st.info("No authors loaded. Go to **🔍 Search** first.")
    st.stop()

# ── Journal config (sidebar, autosaved) ──
st.sidebar.subheader("📰 Journal Configuration")

journal_name = st.sidebar.text_input("Journal Name", key="journal_name")
journal_issn = st.sidebar.text_input("ISSN", key="journal_issn")
journal_link = st.sidebar.text_input("Journal Website", key="journal_link")
publisher_location = st.sidebar.text_input("Publisher Location", key="publisher_location")
editor_in_chief = st.sidebar.text_input("Editor-in-Chief Name", key="eic_name")
scopus_indexed = st.sidebar.checkbox("Scopus Indexed", key="scopus_indexed")

# Autosave journal config to DB
if st.sidebar.button("💾 Save Journal Config", key="save_journal"):
    if journal_name and st.session_state.get("db_ready"):
        try:
            from db_client import save_config
            save_config(journal_name, "journal", {
                "journal_name": journal_name,
                "journal_issn": journal_issn,
                "journal_link": journal_link,
                "publisher_location": publisher_location,
                "eic_name": editor_in_chief,
                "scopus_indexed": scopus_indexed,
            })
            st.sidebar.success("Saved!")
        except Exception as e:
            st.sidebar.error(f"Save failed: {e}")

# Load saved journal config
if st.session_state.get("db_ready"):
    try:
        from db_client import load_configs
        journal_configs = load_configs("journal")
        if journal_configs:
            names = ["-- Select --"] + [c["config_name"] for c in journal_configs]
            load_j = st.sidebar.selectbox("Load journal config", names, key="load_journal")
            if load_j != "-- Select --":
                for c in journal_configs:
                    if c["config_name"] == load_j:
                        cfg = c["config_data"]
                        st.session_state.journal_name = cfg.get("journal_name", "")
                        st.session_state.journal_issn = cfg.get("journal_issn", "")
                        st.session_state.journal_link = cfg.get("journal_link", "")
                        st.session_state.publisher_location = cfg.get("publisher_location", "")
                        st.session_state.eic_name = cfg.get("eic_name", "")
                        st.session_state.scopus_indexed = cfg.get("scopus_indexed", False)
                        st.rerun()
    except Exception:
        pass

# ── Publisher / SMTP ──
st.subheader("📧 Email Configuration")

sender = EmailSender()
publishers = sender.get_all_publisher_options()

if not publishers:
    st.warning("No email accounts configured. Set EMAIL_CREDENTIALS environment variable.")
    st.stop()

pub_options = {p["name"]: p["id"] for p in publishers}
selected_pub_name = st.selectbox("Publisher Account", list(pub_options.keys()), key="pub_select")
publisher_id = pub_options[selected_pub_name]
publisher_name = sender.get_publisher_name(publisher_id)
sender_email = sender.get_publisher_email(publisher_id)

st.caption(f"Sending from: **{sender_email}**")

if st.button("🔌 Test Connection"):
    ok, msg = sender.test_connection(publisher_id)
    if ok:
        st.success(msg)
    else:
        st.error(msg)

# ── Template ──
st.subheader("📝 Email Template")

template_names = get_template_names()
template_options = {v: k for k, v in template_names.items()}
selected_template_name = st.selectbox("Template", list(template_options.keys()), key="template_select")
template_id = template_options[selected_template_name]

attach_pdf = st.checkbox("Attach PDF invitation letter", value=True, key="attach_pdf")

# Preview
with st.expander("Preview Template"):
    preview = format_template(
        template_id=template_id,
        author_name="[Author Name]",
        journal_name=journal_name or "[Journal]",
        journal_issn=journal_issn or "[ISSN]",
        journal_link=journal_link or "[Link]",
        editor_in_chief_name=editor_in_chief or "[EiC]",
        publisher_name=publisher_name or "[Publisher]",
        sender_email=sender_email or "[Email]",
        publisher_location=publisher_location or "[Location]",
        scopus_indexed=scopus_indexed,
    )
    st.write(f"**Subject:** {preview['subject']}")
    st.text(preview["body"])

# ── Authors ready to send ──
st.divider()
st.subheader("📤 Send")

# Get only authors with email
authors_with_email = [a for a in st.session_state.authors if a.get("email")]

# Filter out bounced
bounced_set = set()
sent_set = set()
if st.session_state.get("db_ready"):
    try:
        from db_client import get_all_sent, get_all_bounced
        sent_set = {r["orcid_id"] for r in get_all_sent() if r.get("orcid_id")}
        bounced_set = {r["email"].lower() for r in get_all_bounced() if r.get("email")}
    except Exception:
        pass

skip_sent = st.checkbox("Skip already invited", value=True, key="skip_sent")
sendable = []
for a in authors_with_email:
    email = a.get("email", "").lower()
    if email in bounced_set:
        continue
    if skip_sent and a.get("orcid_id") in sent_set:
        continue
    sendable.append(a)

st.info(f"**{len(sendable)}** authors ready to send (of {len(authors_with_email)} with email)")

# ── Bulk send ──
if sendable:
    if st.button(f"🚀 Send to All {len(sendable)} Authors", type="primary"):
        if not journal_name:
            st.error("Please fill in Journal Name in the sidebar.")
            st.stop()

        progress = st.progress(0, text="Sending...")
        success_count = 0
        fail_count = 0
        status_text = st.empty()

        for i, author in enumerate(sendable):
            name = author.get("name", "")
            email = author.get("email", "")
            orcid_id = author.get("orcid_id", "")

            formatted = format_template(
                template_id=template_id,
                author_name=name,
                journal_name=journal_name,
                journal_issn=journal_issn,
                journal_link=journal_link,
                editor_in_chief_name=editor_in_chief,
                publisher_name=publisher_name,
                sender_email=sender_email,
                publisher_location=publisher_location,
                scopus_indexed=scopus_indexed,
            )

            pdf_bytes = None
            if attach_pdf:
                try:
                    pdf_bytes = generate_invitation_pdf(
                        publisher_id=publisher_id,
                        recipient_name=name,
                        email_body=formatted["body"],
                        subject=formatted["subject"],
                        journal_name=journal_name,
                        journal_link=journal_link,
                    )
                except Exception:
                    pdf_bytes = None

            ok, msg = sender.send_email(
                publisher_id=publisher_id,
                to_email=email,
                subject=formatted["subject"],
                body=formatted["body"],
                to_name=name,
                pdf_attachment=pdf_bytes,
            )

            if ok:
                success_count += 1
                # Record in DB
                if st.session_state.get("db_ready") and orcid_id:
                    try:
                        from db_client import mark_sent
                        mark_sent(orcid_id, name, email, publisher_id)
                    except Exception:
                        pass
            else:
                fail_count += 1

            progress.progress((i + 1) / len(sendable), text=f"Sent {i + 1}/{len(sendable)}")
            status_text.caption(f"✅ {success_count} sent | ❌ {fail_count} failed")

        progress.empty()
        st.success(f"Done! ✅ {success_count} sent, ❌ {fail_count} failed")

# ── Individual send table ──
st.divider()
st.subheader("Individual Send")

if sendable:
    for author in sendable[:50]:  # Show first 50
        name = author.get("name", "")
        email = author.get("email", "")
        orcid_id = author.get("orcid_id", "")

        col1, col2, col3, col4 = st.columns([3, 3, 2, 2])
        col1.write(name)
        col2.write(email)
        col3.write(author.get("institution", "")[:30])

        if col4.button("Send", key=f"send_{orcid_id or name}"):
            formatted = format_template(
                template_id=template_id,
                author_name=name,
                journal_name=journal_name,
                journal_issn=journal_issn,
                journal_link=journal_link,
                editor_in_chief_name=editor_in_chief,
                publisher_name=publisher_name,
                sender_email=sender_email,
                publisher_location=publisher_location,
                scopus_indexed=scopus_indexed,
            )

            pdf_bytes = None
            if attach_pdf:
                try:
                    pdf_bytes = generate_invitation_pdf(
                        publisher_id=publisher_id,
                        recipient_name=name,
                        email_body=formatted["body"],
                        subject=formatted["subject"],
                        journal_name=journal_name,
                        journal_link=journal_link,
                    )
                except Exception:
                    pdf_bytes = None

            ok, msg = sender.send_email(
                publisher_id=publisher_id,
                to_email=email,
                subject=formatted["subject"],
                body=formatted["body"],
                to_name=name,
                pdf_attachment=pdf_bytes,
            )

            if ok:
                st.toast(f"✅ Sent to {name}")
                if st.session_state.get("db_ready") and orcid_id:
                    try:
                        from db_client import mark_sent
                        mark_sent(orcid_id, name, email, publisher_id)
                    except Exception:
                        pass
            else:
                st.toast(f"❌ Failed: {msg}")
