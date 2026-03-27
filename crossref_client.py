"""Crossref API client — free email extraction from paper metadata."""

import time
from typing import Optional, List, Dict
import requests

from config import CROSSREF_BASE_URL, OPENALEX_EMAIL


class CrossrefClient:
    """Extract author emails from Crossref paper metadata."""

    def __init__(self, email: str = OPENALEX_EMAIL):
        self.email = email
        self.base_url = CROSSREF_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": f"EditorialBoardTool/2.0 (mailto:{email})"
        })

    def search_author_emails(self, author_name: str, rows: int = 5) -> Optional[str]:
        """
        Search Crossref for papers by this author and extract any email.

        Returns the first institutional email found, or any email, or None.
        """
        try:
            params = {
                "query.author": author_name,
                "rows": rows,
                "select": "author",
                "mailto": self.email,
            }
            resp = self.session.get(
                f"{self.base_url}/works", params=params, timeout=15
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            items = data.get("message", {}).get("items", [])

            personal_domains = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "live.com"}
            institutional: List[str] = []
            personal: List[str] = []

            name_parts = set(author_name.lower().split())

            for item in items:
                for author in item.get("author", []):
                    # Check if this author record likely matches
                    given = (author.get("given") or "").lower()
                    family = (author.get("family") or "").lower()
                    if not (family in name_parts or given in name_parts):
                        continue

                    email = author.get("email")
                    if email:
                        email = email.strip().lower()
                        domain = email.split("@")[-1] if "@" in email else ""
                        if domain in personal_domains:
                            personal.append(email)
                        else:
                            institutional.append(email)

            if institutional:
                return institutional[0]
            if personal:
                return personal[0]
            return None

        except Exception:
            return None

    def search_author_emails_batch(
        self, authors: List[Dict], delay: float = 0.3
    ) -> Dict[str, Optional[str]]:
        """
        Batch search: returns {orcid_id: email_or_none}.

        Respects rate limits with a delay between requests.
        """
        results: Dict[str, Optional[str]] = {}
        for author in authors:
            orcid_id = author.get("orcid_id", "")
            name = author.get("name", "")
            if not name:
                results[orcid_id] = None
                continue
            email = self.search_author_emails(name)
            results[orcid_id] = email
            time.sleep(delay)
        return results
