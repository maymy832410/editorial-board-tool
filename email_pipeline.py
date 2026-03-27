"""Unified free email pipeline: OpenAlex Works → ORCID → Crossref."""

import asyncio
from typing import Optional, Callable, Dict, List

from crossref_client import CrossrefClient
from orcid_async import AsyncOrcidClient
from config import OPENALEX_BASE_URL, OPENALEX_EMAIL

import requests


# ── Thin OpenAlex Works email helper (avoids circular import) ──

_session = requests.Session()
_session.headers.update({"User-Agent": f"EditorialBoardTool/2.0 (mailto:{OPENALEX_EMAIL})"})


def _openalex_email_from_works(author_openalex_id: str) -> Optional[str]:
    """Fetch email from OpenAlex works/authorships for an author."""
    try:
        short_id = author_openalex_id.split("/")[-1] if "/" in author_openalex_id else author_openalex_id
        url = f"{OPENALEX_BASE_URL}/works"
        params = {
            "filter": f"authorships.author.id:{short_id}",
            "select": "authorships",
            "per_page": 10,
            "mailto": OPENALEX_EMAIL,
        }
        resp = _session.get(url, params=params, timeout=20)
        if resp.status_code != 200:
            return None

        for work in resp.json().get("results", []):
            for authorship in work.get("authorships", []):
                author_data = authorship.get("author", {})
                aid = (author_data.get("id") or "").split("/")[-1]
                if aid == short_id:
                    email = authorship.get("raw_author_name_email") or author_data.get("email")
                    if email:
                        return email.strip()
        return None
    except Exception:
        return None


# ── Pipeline ──

def fetch_email_for_author(
    author: dict,
    crossref_client: Optional[CrossrefClient] = None,
) -> Dict:
    """
    Run the 3-stage free pipeline for a single author synchronously.

    Returns: {"email": str|None, "source": str|None}
    """
    author_id = author.get("author_id", "")
    orcid_id = author.get("orcid_id")
    name = author.get("name", "")

    # Stage 1 — OpenAlex Works
    email = _openalex_email_from_works(author_id) if author_id else None
    if email:
        return {"email": email, "source": "OpenAlex Works"}

    # Stage 2 — ORCID (sync wrapper for single call)
    if orcid_id:
        try:
            loop = asyncio.new_event_loop()
            async def _fetch():
                async with AsyncOrcidClient(max_concurrent=1) as c:
                    return await c.get_email(orcid_id)
            email = loop.run_until_complete(_fetch())
            loop.close()
        except Exception:
            email = None
        if email:
            return {"email": email, "source": "ORCID"}

    # Stage 3 — Crossref
    if name:
        if crossref_client is None:
            crossref_client = CrossrefClient()
        email = crossref_client.search_author_emails(name)
        if email:
            return {"email": email, "source": "Crossref"}

    return {"email": None, "source": None}


async def _orcid_email(orcid_id: str) -> Optional[str]:
    """Async helper to get a single ORCID email."""
    async with AsyncOrcidClient(max_concurrent=1) as c:
        return await c.get_email(orcid_id)


async def fetch_emails_batch_async(
    authors: List[dict],
    on_progress: Optional[Callable] = None,
    max_concurrent: int = 10,
) -> List[dict]:
    """
    Batch pipeline: for each author without an email, run
    OpenAlex Works → ORCID batch → Crossref.

    Returns the same author list with 'email' and 'email_source' filled in.
    """
    # Separate authors that already have emails from those that don't
    need_email = [a for a in authors if not a.get("email")]
    have_email = [a for a in authors if a.get("email")]

    total = len(need_email)
    done = 0

    # ---- Stage 1: OpenAlex Works (sync, but fast per author) ----
    still_need: List[dict] = []
    for author in need_email:
        author_id = author.get("author_id", "")
        email = _openalex_email_from_works(author_id) if author_id else None
        if email:
            author["email"] = email
            author["email_source"] = "OpenAlex Works"
        else:
            still_need.append(author)
        done += 1
        if on_progress:
            on_progress(done, total, "OpenAlex Works")

    # ---- Stage 2: ORCID batch (async, fast parallel) ----
    orcid_authors = [a for a in still_need if a.get("orcid_id")]
    if orcid_authors:
        async with AsyncOrcidClient(max_concurrent=max_concurrent) as orcid_client:
            tasks = []
            for a in orcid_authors:
                tasks.append(orcid_client.get_email(a["orcid_id"]))
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for a, result in zip(orcid_authors, results):
                if isinstance(result, str) and result:
                    a["email"] = result
                    a["email_source"] = "ORCID"
                done += 1
                if on_progress:
                    on_progress(done, total, "ORCID")

    # Update still_need
    still_need = [a for a in still_need if not a.get("email")]

    # ---- Stage 3: Crossref (sync, polite rate) ----
    if still_need:
        crossref = CrossrefClient()
        for author in still_need:
            name = author.get("name", "")
            if name:
                email = crossref.search_author_emails(name)
                if email:
                    author["email"] = email
                    author["email_source"] = "Crossref"
            done += 1
            if on_progress:
                on_progress(done, total, "Crossref")

    # Merge
    all_authors = have_email + need_email
    return all_authors
