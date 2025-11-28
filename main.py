"""Audit Drupal pages for broken links, legacy domains, and placeholder text."""

from __future__ import annotations

import argparse
import asyncio
import csv
import os
import re
import sys
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple, Union
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from bs4.element import Tag
from dotenv import load_dotenv

USER_AGENT = "seo-descriptions-audit/0.2 (+https://lifeline.org.au)"

DEV_PROD_HOSTS = {
    "lla-drupal-app-prod.salmonground-819df123.australiaeast.azurecontainerapps.io",
    "lla-drupal-app-uat.victoriouspond-08331c17.australiaeast.azurecontainerapps.io",
}

BLOCKED_LIFELINE_HOSTS = {
    "lifeline.org.au",
    "www.lifeline.org.au",
    "toolkit.lifeline.org.au",
}

PLACEHOLDER_PATTERNS = [
    re.compile(r"lorem ipsum", re.IGNORECASE),
    re.compile(r"\bplaceholder\b", re.IGNORECASE),
]

MAX_PLACEHOLDER_MATCHES = 20
PLACEHOLDER_CONTEXT = 80

EXCLUDED_HREF_PREFIXES = ("mailto:", "tel:", "javascript:", "data:", "#")


SoupElement = Union[BeautifulSoup, Tag]


@dataclass
class SourceRow:
    url: str


@dataclass
class Issue:
    url: str
    issue_type: str
    snippet: str


@dataclass
class PageLink:
    raw: str
    absolute: str
    host: str
    anchor_text: str
    was_absolute: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=str,
        default="/home/aido/projects/seo-descriptions/seo-descriptions.csv",
        help="Path to the CSV that lists URLs to audit.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="/home/aido/projects/seo-descriptions/seo-descriptions-results.csv",
        help="Path for the CSV results file.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit for the number of rows to process.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Maximum number of concurrent page audits (default: 5).",
    )
    args = parser.parse_args()
    if args.concurrency < 1:
        parser.error("--concurrency must be at least 1.")
    return args


def load_source_rows(path: str) -> List[SourceRow]:
    rows: List[SourceRow] = []
    with open(path, newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for raw in reader:
            url = extract_url_from_row(raw)
            if not url:
                continue
            rows.append(SourceRow(url=url))
    return rows


def extract_url_from_row(raw: Dict[str, str]) -> Optional[str]:
    normalized = {
        (key or "").strip().lower().lstrip("\ufeff"): (value or "").strip()
        for key, value in raw.items()
    }
    for candidate in ("link", "url", "full-link", "full link", "page url", "page-url"):
        value = normalized.get(candidate)
        if value:
            return value
    return None


def ensure_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is required.")
    return value


def collapse_whitespace(text: str) -> str:
    return " ".join(text.split())


def trim_snippet(text: str, limit: int = 200) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def get_audit_root(soup: BeautifulSoup) -> SoupElement:
    main_tag = soup.find("main")
    if main_tag:
        return main_tag
    return soup


def resolve_href(base_url: str, href: str) -> Optional[Tuple[str, str, bool]]:
    trimmed = (href or "").strip()
    if not trimmed:
        return None
    lowered = trimmed.lower()
    if lowered.startswith(EXCLUDED_HREF_PREFIXES):
        return None
    if trimmed.startswith("//"):
        target = f"https:{trimmed}"
        was_absolute = True
    else:
        was_absolute = bool(urlparse(trimmed).netloc)
        target = urljoin(base_url, trimmed)
    target, _ = urldefrag(target)
    parsed = urlparse(target)
    host = parsed.netloc.lower()
    return target, host, was_absolute


def extract_page_links(container: SoupElement, base_url: str) -> List[PageLink]:
    links: List[PageLink] = []
    base_host = urlparse(base_url).netloc.lower()
    for anchor in container.find_all("a"):
        href = anchor.get("href")
        if not href:
            continue
        resolved = resolve_href(base_url, href)
        if not resolved:
            continue
        absolute, host, was_absolute = resolved
        anchor_text = collapse_whitespace(anchor.get_text(" ", strip=True))
        links.append(
            PageLink(
                raw=href.strip(),
                absolute=absolute,
                host=host or base_host,
                anchor_text=anchor_text,
                was_absolute=was_absolute,
            )
        )
    return links


def link_snippet(link: PageLink, extra: Optional[str] = None) -> str:
    text = link.anchor_text or "<no text>"
    target = link.raw or link.absolute
    snippet = f'"{text}" -> {target}'
    if extra:
        snippet = f"{snippet} ({extra})"
    return trim_snippet(snippet)


async def fetch_page(
    client: httpx.AsyncClient,
    url: str,
    auth: Tuple[str, str],
) -> Tuple[str, Optional[str], Optional[str]]:
    try:
        response = await client.get(url, auth=auth)
    except httpx.HTTPError as exc:
        print(f"Failed to fetch {url}: {exc}", file=sys.stderr)
        return "error", None, str(exc)

    if response.status_code == 404:
        print(f"{url} returned 404.", file=sys.stderr)
        return "404", None, None

    if 200 <= response.status_code < 300:
        return "OK", response.text, None

    reason = f"status {response.status_code}"
    print(f"{url} returned {reason}.", file=sys.stderr)
    return "error", None, reason


def detect_absolute_links(
    page_url: str,
    links: Iterable[PageLink],
    predicate: Callable[[str], bool],
    issue_type: str,
) -> List[Issue]:
    issues: List[Issue] = []
    for link in links:
        if not link.was_absolute:
            continue
        if predicate(link.host):
            issues.append(Issue(url=page_url, issue_type=issue_type, snippet=link_snippet(link)))
    return issues


async def detect_broken_links(
    page_url: str,
    links: Iterable[PageLink],
    base_host: str,
    client: httpx.AsyncClient,
    auth: Tuple[str, str],
    cache: Dict[str, Optional[int]],
) -> List[Issue]:
    issues: List[Issue] = []
    seen: Set[str] = set()
    for link in links:
        if link.host != base_host:
            continue
        if link.absolute in seen:
            continue
        seen.add(link.absolute)
        status = await fetch_link_status(link.absolute, client, auth, cache)
        if status is None:
            issues.append(
                Issue(
                    url=page_url,
                    issue_type="Broken link",
                    snippet=link_snippet(link, "request failed"),
                )
            )
            continue
        if status >= 400:
            issues.append(
                Issue(
                    url=page_url,
                    issue_type="Broken link",
                    snippet=link_snippet(link, f"returned HTTP {status}"),
                )
            )
    return issues


async def fetch_link_status(
    url: str,
    client: httpx.AsyncClient,
    auth: Tuple[str, str],
    cache: Dict[str, Optional[int]],
) -> Optional[int]:
    if url in cache:
        return cache[url]
    try:
        response = await client.get(url, auth=auth)
    except httpx.HTTPError as exc:
        print(f"Failed to fetch linked URL {url}: {exc}", file=sys.stderr)
        cache[url] = None
        return None
    cache[url] = response.status_code
    return response.status_code


def find_placeholder_text(page_url: str, container: SoupElement) -> List[Issue]:
    issues: List[Issue] = []
    for tag in container(["script", "style", "noscript", "template"]):
        tag.decompose()
    text = collapse_whitespace(container.get_text(separator=" ", strip=True))
    if not text:
        return issues
    for pattern in PLACEHOLDER_PATTERNS:
        for match in pattern.finditer(text):
            snippet = snippet_from_text(text, match.start(), match.end())
            issues.append(
                Issue(
                    url=page_url,
                    issue_type="Placeholder text",
                    snippet=f'Found "{match.group(0)}" in "{snippet}"',
                )
            )
            if len(issues) >= MAX_PLACEHOLDER_MATCHES:
                return issues
    return issues


def snippet_from_text(text: str, start: int, end: int) -> str:
    snippet_start = max(0, start - PLACEHOLDER_CONTEXT)
    snippet_end = min(len(text), end + PLACEHOLDER_CONTEXT)
    snippet = text[snippet_start:snippet_end].strip()
    return trim_snippet(snippet)


def write_results(path: str, rows: Iterable[Issue]) -> None:
    fieldnames = ["URL", "Issue Type", "Snippet"]
    with open(path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "URL": row.url,
                    "Issue Type": row.issue_type,
                    "Snippet": row.snippet,
                }
            )


async def process_row(
    *,
    idx: int,
    total: int,
    row: SourceRow,
    web_client: httpx.AsyncClient,
    auth: Tuple[str, str],
    semaphore: asyncio.Semaphore,
    cache: Dict[str, Optional[int]],
) -> List[Issue]:
    async with semaphore:
        print(f"[{idx}/{total}] Auditing {row.url}")
        page_status, html, error = await fetch_page(web_client, row.url, auth)
        issues: List[Issue] = []

        if page_status == "404":
            issues.append(Issue(url=row.url, issue_type="Page 404", snippet="GET returned 404"))
            return issues

        if page_status == "error":
            issues.append(
                Issue(
                    url=row.url,
                    issue_type="Fetch failed",
                    snippet=error or "Unknown error",
                )
            )
            return issues

        soup = BeautifulSoup(html or "", "html.parser")
        root = get_audit_root(soup)
        links = extract_page_links(root, row.url)
        base_host = urlparse(row.url).netloc.lower()

        issues.extend(
            detect_absolute_links(
                page_url=row.url,
                links=links,
                predicate=lambda host: host in DEV_PROD_HOSTS,
                issue_type="Absolute link to dev/prod domain",
            )
        )

        issues.extend(
            detect_absolute_links(
                page_url=row.url,
                links=links,
                predicate=lambda host: host in BLOCKED_LIFELINE_HOSTS,
                issue_type="Link to lifeline.org.au",
            )
        )

        issues.extend(
            await detect_broken_links(
                page_url=row.url,
                links=links,
                base_host=base_host,
                client=web_client,
                auth=auth,
                cache=cache,
            )
        )

        issues.extend(find_placeholder_text(row.url, root))

        return issues


async def run_audit(args: argparse.Namespace) -> None:
    load_dotenv()

    username = ensure_env("HTTP_USERNAME")
    password = ensure_env("HTTP_PASSWORD")

    source_rows = load_source_rows(args.input)
    if args.limit:
        source_rows = source_rows[: args.limit]

    print(f"Loaded {len(source_rows)} URLs from {args.input}.")

    semaphore = asyncio.Semaphore(args.concurrency)
    link_cache: Dict[str, Optional[int]] = {}

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=httpx.Timeout(30.0, connect=10.0),
        follow_redirects=True,
    ) as web_client:
        tasks = [
            asyncio.create_task(
                process_row(
                    idx=idx,
                    total=len(source_rows),
                    row=row,
                    web_client=web_client,
                    auth=(username, password),
                    semaphore=semaphore,
                    cache=link_cache,
                )
            )
            for idx, row in enumerate(source_rows, start=1)
        ]
        nested_results = await asyncio.gather(*tasks)

    issues = [issue for result in nested_results for issue in result]

    write_results(args.output, issues)
    if issues:
        print(f"Wrote {len(issues)} issues to {args.output}")
    else:
        print(f"No issues found. Wrote empty report to {args.output}")


def main() -> None:
    args = parse_args()
    asyncio.run(run_audit(args))


if __name__ == "__main__":
    main()
