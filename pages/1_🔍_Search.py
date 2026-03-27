"""Page 1: Search & Filter Configuration."""

import streamlit as st
import json

from openalex_client import OpenAlexClient
from geography import CONTINENTS, COUNTRIES, get_country_codes_for_continents
from config import DEFAULT_H_INDEX_MIN, DEFAULT_H_INDEX_MAX, DEFAULT_MAX_RESULTS

st.header("🔍 Search Researchers")

# ── Initialize ──
client = OpenAlexClient()

if "search_authors_list" not in st.session_state:
    st.session_state.search_authors_list = []


# ── Autosave / Load config ──
def _load_saved_searches():
    if not st.session_state.get("db_ready"):
        return []
    try:
        from db_client import load_configs
        return load_configs("search_filter")
    except Exception:
        return []


def _save_search(name, config_data):
    if not st.session_state.get("db_ready"):
        return
    try:
        from db_client import save_config
        save_config(name, "search_filter", config_data)
    except Exception:
        pass


# ── Taxonomy dropdowns ──
st.subheader("📚 Research Area")

# Cache taxonomy data
@st.cache_data(ttl=3600)
def fetch_domains():
    return client.get_domains()

@st.cache_data(ttl=3600)
def fetch_fields(domain_id):
    return client.get_fields(domain_id)

@st.cache_data(ttl=3600)
def fetch_subfields(field_id):
    return client.get_subfields(field_id)


col1, col2, col3 = st.columns(3)

with col1:
    domains = fetch_domains()
    domain_options = {d["display_name"]: d["id"] for d in domains}
    selected_domain = st.selectbox(
        "Domain",
        options=["-- All --"] + list(domain_options.keys()),
        key="domain_select",
    )
    domain_id = domain_options.get(selected_domain)

with col2:
    if domain_id:
        fields = fetch_fields(domain_id)
    else:
        fields = fetch_fields(None)
    field_options = {f["display_name"]: f["id"] for f in fields}
    selected_field = st.selectbox(
        "Field",
        options=["-- All --"] + list(field_options.keys()),
        key="field_select",
    )
    field_id = field_options.get(selected_field)

with col3:
    if field_id:
        subfields = fetch_subfields(field_id)
        subfield_options = {s["display_name"]: s["id"] for s in subfields}
        selected_subfields = st.multiselect(
            "Subfields (optional)",
            options=list(subfield_options.keys()),
            key="subfield_select",
        )
        subfield_ids = [subfield_options[s] for s in selected_subfields] if selected_subfields else None
    else:
        subfield_ids = None
        st.multiselect("Subfields (optional)", options=[], disabled=True, key="subfield_disabled")

# Keyword topic refinement
keywords_raw = st.text_area(
    "Additional keyword tags (comma-separated, optional)",
    placeholder="e.g. machine learning, neural networks",
    key="keyword_tags",
)
keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()] if keywords_raw else []

# ── Sidebar filters ──
st.sidebar.subheader("🌍 Geography")

# Continent selector
selected_continents = st.sidebar.multiselect(
    "Continents",
    options=list(CONTINENTS.keys()),
    key="continent_select",
)

# Auto-fill country codes from continents
continent_codes = get_country_codes_for_continents(selected_continents) if selected_continents else []

# Let user further refine
all_country_names = sorted(COUNTRIES.keys())
include_countries = st.sidebar.multiselect(
    "Include countries",
    options=all_country_names,
    default=[],
    key="include_countries",
)
include_codes = [COUNTRIES[c] for c in include_countries if c in COUNTRIES]

# Combine continent + manual country codes
all_include_codes = list(set(continent_codes + include_codes)) if (continent_codes or include_codes) else None

exclude_countries = st.sidebar.multiselect(
    "Exclude countries",
    options=all_country_names,
    key="exclude_countries",
)
exclude_codes = [COUNTRIES[c] for c in exclude_countries if c in COUNTRIES] if exclude_countries else None

st.sidebar.subheader("📊 H-Index Range")
h_min = st.sidebar.number_input("Min H-Index", min_value=0, value=DEFAULT_H_INDEX_MIN, key="h_min")
h_max = st.sidebar.number_input("Max H-Index", min_value=0, value=DEFAULT_H_INDEX_MAX, key="h_max")

st.sidebar.subheader("⚙️ Options")
max_results = st.sidebar.number_input("Max results per batch", min_value=100, max_value=50000, value=DEFAULT_MAX_RESULTS, step=500, key="max_results")
require_orcid = st.sidebar.checkbox("Require ORCID", value=False, key="require_orcid")

# ── Exclude filters ──
st.sidebar.subheader("🚫 Exclusions")
exclude_invited = st.sidebar.checkbox("Exclude previously invited", value=True, key="exclude_invited")
exclude_retracted = st.sidebar.checkbox("Exclude retracted authors", value=False, key="exclude_retracted")
exclude_institution = st.sidebar.text_input("Exclude institution keyword", key="exclude_institution")

# ── Save / Load search configs ──
st.sidebar.divider()
st.sidebar.subheader("💾 Saved Searches")

saved_searches = _load_saved_searches()
if saved_searches:
    saved_names = ["-- New search --"] + [s["config_name"] for s in saved_searches]
    load_choice = st.sidebar.selectbox("Load saved search", options=saved_names, key="load_search")
    if load_choice != "-- New search --":
        for s in saved_searches:
            if s["config_name"] == load_choice:
                cfg = s["config_data"]
                # Apply loaded config to session state
                for k, v in cfg.items():
                    st.session_state[k] = v
                st.sidebar.success(f"Loaded: {load_choice}")
                break

save_name = st.sidebar.text_input("Save current search as", key="save_search_name")
if st.sidebar.button("💾 Save Search", key="save_search_btn"):
    if save_name:
        config_data = {
            "domain_select": st.session_state.get("domain_select"),
            "field_select": st.session_state.get("field_select"),
            "subfield_select": st.session_state.get("subfield_select", []),
            "keyword_tags": st.session_state.get("keyword_tags", ""),
            "continent_select": st.session_state.get("continent_select", []),
            "include_countries": st.session_state.get("include_countries", []),
            "exclude_countries": st.session_state.get("exclude_countries", []),
            "h_min": h_min,
            "h_max": h_max,
            "max_results": max_results,
            "require_orcid": require_orcid,
            "exclude_invited": exclude_invited,
            "exclude_retracted": exclude_retracted,
            "exclude_institution": st.session_state.get("exclude_institution", ""),
        }
        _save_search(save_name, config_data)
        st.sidebar.success(f"Saved: {save_name}")

# ── Search button ──
st.divider()

if st.button("🔍 Search OpenAlex", type="primary", use_container_width=True):
    # Resolve topic IDs from keywords
    topic_ids = None
    topic_details = []
    if keywords:
        with st.spinner("Resolving keywords to topics..."):
            topic_ids, topic_details = client.search_topics(keywords)
        if topic_details:
            st.info(f"Matched {len(topic_details)} topics from keywords")

    # Build exclude sets
    excluded_orcids = set()
    if exclude_invited and st.session_state.get("db_ready"):
        try:
            from db_client import get_all_sent
            for row in get_all_sent():
                if row.get("orcid_id"):
                    excluded_orcids.add(row["orcid_id"])
        except Exception:
            pass

    retraction_checker = st.session_state.get("retraction_checker")

    # Count first
    with st.spinner("Counting results..."):
        total = client.get_total_count(
            h_index_min=h_min,
            h_index_max=h_max,
            country_codes=all_include_codes,
            exclude_country_codes=exclude_codes,
            topic_ids=topic_ids,
            field_id=field_id,
            subfield_ids=subfield_ids,
            require_orcid=require_orcid,
        )
    st.info(f"Found **{total:,}** matching authors. Fetching up to {max_results:,}...")

    # Fetch
    authors = []
    progress = st.progress(0, text="Fetching authors...")
    for i, author in enumerate(client.search_authors(
        h_index_min=h_min,
        h_index_max=h_max,
        country_codes=all_include_codes,
        exclude_country_codes=exclude_codes,
        topic_ids=topic_ids,
        field_id=field_id,
        subfield_ids=subfield_ids,
        require_orcid=require_orcid,
        max_results=max_results,
    )):
        # Exclude already invited
        if author.get("orcid_id") and author["orcid_id"] in excluded_orcids:
            continue

        # Exclude by institution keyword
        if exclude_institution and author.get("institution"):
            if exclude_institution.lower() in author["institution"].lower():
                continue

        # Check retraction
        if retraction_checker and exclude_retracted:
            result = retraction_checker.check(author.get("name", ""))
            if result["match"]:
                continue
        elif retraction_checker:
            result = retraction_checker.check(author.get("name", ""))
            author["retraction_flag"] = result

        authors.append(author)
        if (i + 1) % 50 == 0:
            progress.progress(min((i + 1) / max_results, 1.0), text=f"Fetched {len(authors)} authors...")

    progress.empty()

    st.session_state.authors = authors
    st.session_state.search_done = True
    st.session_state.search_resume_state = client.last_search_state
    st.session_state.search_total = total
    # Save search params for Load More
    st.session_state.last_search_params = {
        "h_index_min": h_min, "h_index_max": h_max,
        "country_codes": all_include_codes, "exclude_country_codes": exclude_codes,
        "topic_ids": topic_ids, "field_id": field_id,
        "subfield_ids": subfield_ids, "require_orcid": require_orcid,
    }
    st.success(f"✅ Found **{len(authors)}** authors after filters")

# ── Show current results summary + Load More ──
if st.session_state.get("search_done") and st.session_state.get("authors"):
    n = len(st.session_state.authors)
    with_email = sum(1 for a in st.session_state.authors if a.get("email"))
    total_available = st.session_state.get("search_total", n)
    st.info(f"Current results: **{n:,}** authors (**{with_email}** with email) out of **{total_available:,}** total. Go to **📋 Results** to review.")

    # Load More button
    if st.session_state.get("search_resume_state"):
        st.warning(f"More authors available beyond the current {n:,}. Click below to load the next batch.")
        if st.button("📥 Load More Authors", type="secondary", use_container_width=True):
            params = st.session_state.last_search_params
            resume = st.session_state.search_resume_state

            # Rebuild exclude sets
            excluded_orcids = set()
            if st.session_state.get("exclude_invited") and st.session_state.get("db_ready"):
                try:
                    from db_client import get_all_sent
                    for row in get_all_sent():
                        if row.get("orcid_id"):
                            excluded_orcids.add(row["orcid_id"])
                except Exception:
                    pass
            # Also exclude already-fetched authors by ID
            existing_ids = {a.get("author_id") for a in st.session_state.authors if a.get("author_id")}

            retraction_checker = st.session_state.get("retraction_checker")
            exc_inst = st.session_state.get("exclude_institution", "")
            exc_retracted = st.session_state.get("exclude_retracted", False)

            new_authors = []
            progress = st.progress(0, text="Loading more authors...")
            for i, author in enumerate(client.search_authors(
                **params,
                max_results=max_results,
                resume_state=resume,
            )):
                if author.get("author_id") in existing_ids:
                    continue
                if author.get("orcid_id") and author["orcid_id"] in excluded_orcids:
                    continue
                if exc_inst and author.get("institution"):
                    if exc_inst.lower() in author["institution"].lower():
                        continue
                if retraction_checker and exc_retracted:
                    result = retraction_checker.check(author.get("name", ""))
                    if result["match"]:
                        continue
                elif retraction_checker:
                    result = retraction_checker.check(author.get("name", ""))
                    author["retraction_flag"] = result

                new_authors.append(author)
                if (i + 1) % 50 == 0:
                    progress.progress(min((i + 1) / max_results, 1.0), text=f"Loaded {len(new_authors)} more...")

            progress.empty()

            st.session_state.authors.extend(new_authors)
            st.session_state.search_resume_state = client.last_search_state
            st.success(f"✅ Loaded **{len(new_authors)}** more authors (total: **{len(st.session_state.authors):,}**)")
            st.rerun()
    else:
        st.caption("All matching authors have been loaded.")
