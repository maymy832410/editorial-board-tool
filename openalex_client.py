"""OpenAlex API client — domain/field/subfield search with enhanced filters."""

import time
from typing import Generator, Optional, List
import requests

from config import OPENALEX_BASE_URL, OPENALEX_EMAIL


class OpenAlexClient:
    """Client for querying OpenAlex API for author data."""

    def __init__(self, email: str = OPENALEX_EMAIL):
        self.email = email
        self.base_url = OPENALEX_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": f"EditorialBoardTool/2.0 (mailto:{email})"
        })
        self._topic_cache: dict[str, List[str]] = {}

    def _make_request(self, endpoint: str, params: dict, max_retries: int = 3) -> dict:
        """Make a request with retry logic and exponential backoff."""
        params["mailto"] = self.email
        url = f"{self.base_url}/{endpoint}"

        for attempt in range(max_retries):
            try:
                response = self.session.get(url, params=params, timeout=30)
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429 or response.status_code >= 500:
                    time.sleep((2 ** attempt) * 2)
                    continue
                else:
                    response.raise_for_status()
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    time.sleep((2 ** attempt) * 2)
                    continue
                raise e
        raise Exception(f"Failed to fetch data after {max_retries} retries")

    # ── Taxonomy helpers ─────────────────────────────────────────────

    def get_domains(self) -> list:
        """Fetch all OpenAlex domains (top-level classification)."""
        data = self._make_request("domains", {"per_page": 50})
        return [
            {"id": d["id"].split("/")[-1], "display_name": d["display_name"]}
            for d in data.get("results", [])
        ]

    def get_fields(self, domain_id: Optional[str] = None) -> list:
        """Fetch fields, optionally filtered by domain."""
        params = {"per_page": 200}
        if domain_id:
            params["filter"] = f"domain.id:domains/{domain_id}"
        data = self._make_request("fields", params)
        return [
            {"id": f["id"].split("/")[-1], "display_name": f["display_name"]}
            for f in data.get("results", [])
        ]

    def get_subfields(self, field_id: Optional[str] = None) -> list:
        """Fetch subfields, optionally filtered by field."""
        params = {"per_page": 200}
        if field_id:
            params["filter"] = f"field.id:fields/{field_id}"
        data = self._make_request("subfields", params)
        return [
            {"id": s["id"].split("/")[-1], "display_name": s["display_name"]}
            for s in data.get("results", [])
        ]

    def search_topics(
        self,
        keywords: list,
        max_per_keyword: int = 3,
        max_total: int = 25,
    ) -> tuple:
        """Search for topic IDs matching keywords. Returns (ids, details)."""
        topic_ids = set()
        topic_details = []

        for keyword in keywords:
            keyword = keyword.strip()
            if not keyword or len(topic_ids) >= max_total:
                break
            try:
                data = self._make_request("topics", {"search": keyword, "per_page": max_per_keyword})
                for topic in data.get("results", []):
                    if len(topic_ids) >= max_total:
                        break
                    tid = topic.get("id", "").split("/")[-1]
                    if tid and tid not in topic_ids:
                        topic_ids.add(tid)
                        topic_details.append({
                            "id": tid,
                            "name": topic.get("display_name", ""),
                            "works_count": topic.get("works_count", 0),
                            "keyword": keyword,
                        })
                time.sleep(0.1)
            except Exception:
                continue
        return list(topic_ids), topic_details

    # ── Topic resolution ────────────────────────────────────────────

    def resolve_topic_ids_for_subfields(self, subfield_ids: List[str]) -> List[str]:
        """Fetch all topic IDs that belong to the given subfields.

        The /authors endpoint only supports `topics.id`, not `topics.subfield.id`,
        so we must resolve subfields → topic IDs first.
        """
        cache_key = "sf:" + ",".join(sorted(subfield_ids))
        if cache_key in self._topic_cache:
            return self._topic_cache[cache_key]

        sf_filter = "|".join(f"subfields/{sid}" for sid in subfield_ids)
        all_ids = []
        page = 1
        while True:
            data = self._make_request("topics", {
                "filter": f"subfield.id:{sf_filter}",
                "per_page": 200,
                "page": page,
            })
            results = data.get("results", [])
            if not results:
                break
            all_ids.extend(r["id"].split("/")[-1] for r in results)
            if len(results) < 200:
                break
            page += 1
            time.sleep(0.1)
        self._topic_cache[cache_key] = all_ids
        return all_ids

    def resolve_topic_ids_for_field(self, field_id: str) -> List[str]:
        """Fetch all topic IDs that belong to the given field."""
        cache_key = f"field:{field_id}"
        if cache_key in self._topic_cache:
            return self._topic_cache[cache_key]

        all_ids = []
        page = 1
        while True:
            data = self._make_request("topics", {
                "filter": f"field.id:fields/{field_id}",
                "per_page": 200,
                "page": page,
            })
            results = data.get("results", [])
            if not results:
                break
            all_ids.extend(r["id"].split("/")[-1] for r in results)
            if len(results) < 200:
                break
            page += 1
            time.sleep(0.1)
        self._topic_cache[cache_key] = all_ids
        return all_ids

    # ── Filter builder ───────────────────────────────────────────────

    MAX_OR_VALUES = 100  # OpenAlex rejects >100 pipe-separated values

    def _resolve_all_topic_ids(
        self,
        topic_ids: Optional[List[str]] = None,
        field_id: Optional[str] = None,
        subfield_ids: Optional[List[str]] = None,
    ) -> List[str]:
        """Resolve subfield/field selections + keyword topics into a single list of topic IDs."""
        resolved = []
        if subfield_ids:
            resolved = self.resolve_topic_ids_for_subfields(subfield_ids)
        elif field_id:
            resolved = self.resolve_topic_ids_for_field(field_id)

        if topic_ids:
            seen = set(resolved)
            resolved.extend(tid for tid in topic_ids if tid not in seen)
        return resolved

    def _build_base_filter(
        self,
        h_index_min: Optional[int] = None,
        h_index_max: Optional[int] = None,
        country_codes: Optional[List[str]] = None,
        exclude_country_codes: Optional[List[str]] = None,
        require_orcid: bool = False,
    ) -> str:
        """Build filter string excluding topic IDs (those are handled via batching)."""
        filters = []
        if h_index_min is not None:
            filters.append(f"summary_stats.h_index:>{h_index_min - 1}")
        if h_index_max is not None:
            filters.append(f"summary_stats.h_index:<{h_index_max + 1}")
        if country_codes:
            filters.append(f"last_known_institutions.country_code:{'|'.join(country_codes)}")
        if exclude_country_codes:
            for cc in exclude_country_codes:
                filters.append(f"last_known_institutions.country_code:!{cc}")
        if require_orcid:
            filters.append("has_orcid:true")
        return ",".join(filters)

    def build_filter(
        self,
        h_index_min: Optional[int] = None,
        h_index_max: Optional[int] = None,
        country_codes: Optional[List[str]] = None,
        exclude_country_codes: Optional[List[str]] = None,
        topic_ids: Optional[List[str]] = None,
        field_id: Optional[str] = None,
        subfield_ids: Optional[List[str]] = None,
        require_orcid: bool = False,
    ) -> str:
        """Build the filter string for the OpenAlex /authors endpoint.

        If topic count exceeds MAX_OR_VALUES, only the first batch is included.
        For proper handling of large topic sets, use search_authors / get_total_count directly.
        """
        base = self._build_base_filter(
            h_index_min=h_index_min, h_index_max=h_index_max,
            country_codes=country_codes, exclude_country_codes=exclude_country_codes,
            require_orcid=require_orcid,
        )
        all_topic_ids = self._resolve_all_topic_ids(topic_ids, field_id, subfield_ids)
        if all_topic_ids:
            chunk = all_topic_ids[:self.MAX_OR_VALUES]
            topic_part = f"topics.id:{'|'.join(chunk)}"
            return f"{base},{topic_part}" if base else topic_part
        return base

    # ── Author search ────────────────────────────────────────────────

    def _topic_batches(self, all_topic_ids: List[str]) -> List[List[str]]:
        """Split topic IDs into chunks of MAX_OR_VALUES."""
        if not all_topic_ids:
            return [[]]
        return [
            all_topic_ids[i:i + self.MAX_OR_VALUES]
            for i in range(0, len(all_topic_ids), self.MAX_OR_VALUES)
        ]

    def search_authors(
        self,
        h_index_min: Optional[int] = None,
        h_index_max: Optional[int] = None,
        country_codes: Optional[List[str]] = None,
        exclude_country_codes: Optional[List[str]] = None,
        topic_ids: Optional[List[str]] = None,
        field_id: Optional[str] = None,
        subfield_ids: Optional[List[str]] = None,
        require_orcid: bool = False,
        max_results: int = 2000,
        per_page: int = 200,
    ) -> Generator[dict, None, None]:
        """Search for authors, yielding parsed records with automatic pagination.

        When topic IDs exceed 100, runs multiple batched queries and deduplicates.
        """
        base_filter = self._build_base_filter(
            h_index_min=h_index_min, h_index_max=h_index_max,
            country_codes=country_codes, exclude_country_codes=exclude_country_codes,
            require_orcid=require_orcid,
        )
        all_topic_ids = self._resolve_all_topic_ids(topic_ids, field_id, subfield_ids)
        batches = self._topic_batches(all_topic_ids)

        seen_ids: set = set()
        total_yielded = 0

        for batch in batches:
            if total_yielded >= max_results:
                break

            if batch:
                topic_part = f"topics.id:{'|'.join(batch)}"
                filter_str = f"{base_filter},{topic_part}" if base_filter else topic_part
            else:
                filter_str = base_filter

            cursor = "*"
            while cursor and total_yielded < max_results:
                params = {
                    "filter": filter_str,
                    "select": "id,display_name,orcid,summary_stats,last_known_institutions,works_count,cited_by_count,topics",
                    "per_page": min(per_page, max_results - total_yielded),
                    "cursor": cursor,
                }
                data = self._make_request("authors", params)
                results = data.get("results", [])
                if not results:
                    break

                for author in results:
                    aid = author.get("id")
                    if aid in seen_ids:
                        continue
                    seen_ids.add(aid)
                    yield self._parse_author(author)
                    total_yielded += 1
                    if total_yielded >= max_results:
                        break

                cursor = data.get("meta", {}).get("next_cursor")
                time.sleep(0.1)

    def _parse_author(self, author: dict) -> dict:
        """Parse raw OpenAlex author record into app format."""
        from disciplines import get_discipline_from_topics

        orcid_url = author.get("orcid")
        orcid_id = orcid_url.split("/")[-1] if orcid_url else None

        institutions = author.get("last_known_institutions", [])
        inst_name = institutions[0].get("display_name") if institutions else None
        inst_country = institutions[0].get("country_code") if institutions else None

        h_index = (author.get("summary_stats") or {}).get("h_index")

        topics = author.get("topics", [])
        all_topics = [t.get("display_name") for t in topics if t.get("display_name")]
        specialty = topics[0].get("display_name") if topics else None
        subfield = None
        if topics:
            sf = topics[0].get("subfield", {})
            subfield = sf.get("display_name") if sf else None

        return {
            "author_id": author.get("id"),
            "name": author.get("display_name"),
            "orcid_id": orcid_id,
            "orcid_url": orcid_url,
            "h_index": h_index,
            "works_count": author.get("works_count"),
            "cited_by_count": author.get("cited_by_count"),
            "institution": inst_name,
            "country": inst_country,
            "discipline": get_discipline_from_topics(topics),
            "specialty": specialty,
            "subfield": subfield,
            "all_topics": all_topics,
            "research_areas": ", ".join(all_topics[:3]) if all_topics else None,
        }

    def get_total_count(
        self,
        h_index_min: Optional[int] = None,
        h_index_max: Optional[int] = None,
        country_codes: Optional[List[str]] = None,
        exclude_country_codes: Optional[List[str]] = None,
        topic_ids: Optional[List[str]] = None,
        field_id: Optional[str] = None,
        subfield_ids: Optional[List[str]] = None,
        require_orcid: bool = False,
    ) -> int:
        """Get total author count. Sums across batches when >100 topic IDs."""
        base_filter = self._build_base_filter(
            h_index_min=h_index_min, h_index_max=h_index_max,
            country_codes=country_codes, exclude_country_codes=exclude_country_codes,
            require_orcid=require_orcid,
        )
        all_topic_ids = self._resolve_all_topic_ids(topic_ids, field_id, subfield_ids)
        batches = self._topic_batches(all_topic_ids)

        total = 0
        for batch in batches:
            if batch:
                topic_part = f"topics.id:{'|'.join(batch)}"
                filter_str = f"{base_filter},{topic_part}" if base_filter else topic_part
            else:
                filter_str = base_filter
            data = self._make_request("authors", {"filter": filter_str, "per_page": 1})
            total += data.get("meta", {}).get("count", 0)
        return total
