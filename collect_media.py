#!/usr/bin/env python3
"""
Discover Lifeline PDFs that are only referenced on external sites.

Workflow:
1. Use the Serper API to run Google searches that look for lifeline.org.au/media PDFs.
2. Fetch each external result page and extract any Lifeline PDF links it contains.
3. Append the findings to `external-media.csv` and refresh `pdfs.txt`.
4. (Optional) Download any newly discovered PDFs into /pdfs.

Run with:
    uv run python collect_media.py --download
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

SERPER_ENDPOINT = "https://google.serper.dev/search"
USER_AGENT = "lifeline-collect-media/0.1 (+https://lifeline.org.au)"
PDF_PREFIX = "https://www.lifeline.org.au/media/"
EXCLUDED_SOURCE_HOSTS = {
    "lifeline.org.au",
    "www.lifeline.org.au",
    "toolkit.lifeline.org.au",
}
MANIFEST_COLUMNS = (
    "pdf_url",
    "sources",
    "source_title",
    "first_query",
    "first_seen_at",
    "last_seen_at",
    "downloaded_file",
    "notes",
)
DEFAULT_QUERIES = [
    "site:lifeline.org.au/media filetype:pdf -site:lifeline.org.au -site:www.lifeline.org.au -site:toolkit.lifeline.org.au",
    '"https://www.lifeline.org.au/media" -site:lifeline.org.au -site:toolkit.lifeline.org.au',
    '"www.lifeline.org.au/media" filetype:pdf -site:lifeline.org.au -site:toolkit.lifeline.org.au',
    '"lifeline.org.au/media" filetype:pdf -site:lifeline.org.au -site:toolkit.lifeline.org.au',
    '"lifeline" filetype:pdf -site:lifeline.org.au -site:www.lifeline.org.au -site:toolkit.lifeline.org.au',
    '"lifeline report" filetype:pdf -site:lifeline.org.au -site:www.lifeline.org.au -site:toolkit.lifeline.org.au',
    '"lifeline media" filetype:pdf -site:lifeline.org.au -site:www.lifeline.org.au -site:toolkit.lifeline.org.au',
    '"lifeline australia" filetype:pdf -site:lifeline.org.au -site:www.lifeline.org.au -site:toolkit.lifeline.org.au',
    '"lifeline research" filetype:pdf -site:lifeline.org.au -site:www.lifeline.org.au -site:toolkit.lifeline.org.au',
    '"lifeline policy " filetype:pdf -site:lifeline.org.au -site:www.lifeline.org.au -site:toolkit.lifeline.org.au',
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_manifest(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        manifest = {}
        for row in reader:
            if not row.get("pdf_url"):
                continue
            manifest[row["pdf_url"]] = _seed_defaults(row)
        return manifest


def _seed_defaults(row: Dict[str, str]) -> Dict[str, str]:
    for column in MANIFEST_COLUMNS:
        row.setdefault(column, "")
    return row


def write_manifest(path: Path, manifest: Dict[str, Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        for pdf_url in sorted(manifest.keys()):
            writer.writerow(_seed_defaults(manifest[pdf_url]))


def write_pdf_list(path: Path, pdf_urls: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for url in sorted(set(filter(None, pdf_urls))):
            handle.write(f"{url}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search for Lifeline PDFs referenced on non-Lifeline sites."
    )
    parser.add_argument(
        "--query",
        action="append",
        dest="queries",
        help="Custom search query (can be passed multiple times).",
    )
    parser.add_argument(
        "--queries-file",
        type=Path,
        help="Optional text file with one query per line.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("external-media.csv"),
        help="Path to the manifest CSV (default: external-media.csv).",
    )
    parser.add_argument(
        "--pdf-list",
        type=Path,
        default=Path("pdfs.txt"),
        help="Where to write the deduplicated list of PDF URLs (default: pdfs.txt).",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download any PDFs that are missing from the /pdfs directory.",
    )
    parser.add_argument(
        "--download-dir",
        type=Path,
        default=Path("pdfs"),
        help="Directory to store downloaded PDFs (default: ./pdfs).",
    )
    parser.add_argument(
        "--per-page",
        type=int,
        default=10,
        help="Results to request from Serper per page (default: 10).",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=3,
        help="Maximum pages to request per query (default: 3).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="HTTP timeout in seconds (default: 20).",
    )
    parser.add_argument(
        "--serper-key",
        help="Override the SERPER_API_KEY from .env.",
    )
    parser.add_argument(
        "--use-jina-reader",
        action="store_true",
        help="Fallback to the Jina Reader proxy when a page blocks direct requests.",
    )
    parser.add_argument(
        "--gl",
        default="au",
        help="Geolocation code for Serper (default: au).",
    )
    parser.add_argument(
        "--hl",
        default="en",
        help="Language code for Serper (default: en).",
    )
    return parser.parse_args()


def load_queries(args: argparse.Namespace) -> List[str]:
    queries: List[str] = []
    if args.queries_file:
        if not args.queries_file.exists():
            print(f"❌ queries file not found: {args.queries_file}", file=sys.stderr)
            sys.exit(1)
        with args.queries_file.open("r", encoding="utf-8") as handle:
            queries.extend(line.strip() for line in handle if line.strip())
    if args.queries:
        queries.extend(args.queries)
    if not queries:
        queries = DEFAULT_QUERIES
    return queries


def search_serper(
    query: str,
    api_key: str,
    *,
    per_page: int,
    max_pages: int,
    timeout: int,
    gl: str,
    hl: str,
) -> Iterable[Dict[str, str]]:
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }
    for page_idx in range(1, max_pages + 1):
        payload = {
            "q": query,
            "page": page_idx,
            "num": per_page,
            "gl": gl,
            "hl": hl,
        }
        try:
            response = httpx.post(
                SERPER_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            print(
                f"❌ Serper error {exc.response.status_code} for '{query}'",
                file=sys.stderr,
            )
            break
        except httpx.HTTPError as exc:
            print(f"❌ Serper request failed for '{query}': {exc}", file=sys.stderr)
            break

        data = response.json()
        organic = data.get("organic", [])
        if not organic:
            break
        for hit in organic:
            yield hit
        if len(organic) < per_page:
            break


def allowed_source(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host not in EXCLUDED_SOURCE_HOSTS


def normalize_pdf_url(href: str) -> Optional[str]:
    if not href:
        return None
    href = href.strip()
    if href.startswith("//"):
        href = f"https:{href}"
    if href.startswith("/media/"):
        href = f"https://www.lifeline.org.au{href}"
    if not href.startswith("http"):
        return None
    if "lifeline.org.au/media/" not in href.lower():
        return None
    cleaned = href.split("#", 1)[0].split("?", 1)[0]
    if not cleaned.lower().startswith(PDF_PREFIX):
        return None
    return cleaned


def fetch_page(
    url: str,
    *,
    timeout: int,
    use_jina_reader: bool,
    jina_key: Optional[str],
) -> Optional[str]:
    headers = {"User-Agent": USER_AGENT}
    try:
        response = httpx.get(
            url, timeout=timeout, headers=headers, follow_redirects=True
        )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if "text/html" in content_type or "text/plain" in content_type:
            return response.text
    except httpx.HTTPError:
        pass

    if not use_jina_reader:
        return None

    normalized = url.replace("https://", "").replace("http://", "")
    proxy_url = f"https://r.jina.ai/http://{normalized}"
    proxy_headers = {"User-Agent": USER_AGENT}
    if jina_key:
        proxy_headers["Authorization"] = f"Bearer {jina_key}"
    try:
        response = httpx.get(proxy_url, timeout=timeout, headers=proxy_headers)
        response.raise_for_status()
        return response.text
    except httpx.HTTPError:
        return None


def extract_pdf_links(html: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    pdf_urls: List[str] = []
    for tag in soup.find_all("a", href=True):
        pdf_url = normalize_pdf_url(tag["href"])
        if pdf_url:
            pdf_urls.append(pdf_url)
    return pdf_urls


def update_manifest_entry(
    manifest: Dict[str, Dict[str, str]],
    *,
    pdf_url: str,
    source_url: str,
    source_title: str,
    query: str,
) -> bool:
    entry = manifest.get(pdf_url)
    now = utc_now()
    is_new = entry is None
    if entry is None:
        entry = {
            "pdf_url": pdf_url,
            "sources": "",
            "source_title": "",
            "first_query": query,
            "first_seen_at": now,
            "last_seen_at": now,
            "downloaded_file": "",
            "notes": "",
        }
        manifest[pdf_url] = entry
    else:
        entry["last_seen_at"] = now
    if source_title and not entry.get("source_title"):
        entry["source_title"] = source_title
    sources = [
        item.strip() for item in entry.get("sources", "").split(" | ") if item.strip()
    ]
    if source_url and source_url not in sources:
        sources.append(source_url)
        entry["sources"] = " | ".join(sources)
    return is_new


def download_pdf(url: str, output_dir: Path, timeout: int) -> Optional[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(urlparse(url).path).name or "download.pdf"
    if not filename.lower().endswith(".pdf"):
        filename = f"{filename}.pdf"
    destination = output_dir / filename
    if destination.exists():
        return destination
    headers = {"User-Agent": USER_AGENT}
    try:
        with httpx.Client(
            timeout=timeout, headers=headers, follow_redirects=True
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            destination.write_bytes(response.content)
            return destination
    except httpx.HTTPError as exc:
        print(f"❌ Failed to download {url}: {exc}", file=sys.stderr)
        return None


def main() -> None:
    load_dotenv()
    args = parse_args()
    queries = load_queries(args)
    serper_key = args.serper_key or os.getenv("SERPER_API_KEY")
    if not serper_key:
        print(
            "❌ SERPER_API_KEY is missing. Add it to .env or pass --serper-key.",
            file=sys.stderr,
        )
        sys.exit(1)

    manifest_path = args.output.resolve()
    pdf_list_path = args.pdf_list.resolve()
    download_dir = args.download_dir.resolve()

    manifest = load_manifest(manifest_path)
    visited_sources: Dict[str, Optional[str]] = {}
    jina_key = os.getenv("JINA_API_KEY")
    new_pdfs = 0
    total_pdfs = 0

    for query in queries:
        print(f"🔎 Searching: {query}")
        for hit in search_serper(
            query,
            serper_key,
            per_page=args.per_page,
            max_pages=args.max_pages,
            timeout=args.timeout,
            gl=args.gl,
            hl=args.hl,
        ):
            source_url = hit.get("link")
            if not source_url or not allowed_source(source_url):
                continue
            if source_url not in visited_sources:
                html = fetch_page(
                    source_url,
                    timeout=args.timeout,
                    use_jina_reader=args.use_jina_reader,
                    jina_key=jina_key,
                )
                visited_sources[source_url] = html
            html = visited_sources[source_url]
            if not html:
                continue
            pdf_urls = extract_pdf_links(html)
            if not pdf_urls:
                continue
            source_title = hit.get("title") or ""
            for pdf_url in pdf_urls:
                total_pdfs += 1
                if update_manifest_entry(
                    manifest,
                    pdf_url=pdf_url,
                    source_url=source_url,
                    source_title=source_title,
                    query=query,
                ):
                    new_pdfs += 1

    write_manifest(manifest_path, manifest)
    write_pdf_list(pdf_list_path, manifest.keys())

    print(f"📦 Total PDFs in manifest: {len(manifest)}")
    print(f"✨ New PDFs discovered this run: {new_pdfs}")
    print(f"🔁 PDF references scanned: {total_pdfs}")
    print(f"📝 Manifest saved to: {manifest_path}")
    print(f"🧾 PDF list saved to: {pdf_list_path}")

    if args.download:
        print("📥 Downloading newly discovered PDFs...")
        downloaded = 0
        for pdf_url, entry in manifest.items():
            destination = entry.get("downloaded_file")
            if destination and Path(destination).exists():
                continue
            saved_path = download_pdf(pdf_url, download_dir, args.timeout)
            if saved_path:
                try:
                    entry["downloaded_file"] = str(saved_path.relative_to(Path.cwd()))
                except ValueError:
                    entry["downloaded_file"] = str(saved_path)
                downloaded += 1
        if downloaded:
            write_manifest(manifest_path, manifest)
            print(f"✅ Downloaded {downloaded} PDFs into {download_dir}")
        else:
            print("ℹ️ No new PDFs required downloading.")


if __name__ == "__main__":
    main()
