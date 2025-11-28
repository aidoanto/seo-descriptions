#!/usr/bin/env python3
"""
Script to download unique PDFs from pdfs.txt to the /pdfs directory.

This script:
1. Reads all URLs from pdfs.txt
2. Filters for unique URLs
3. Downloads each PDF to the /pdfs directory
4. Shows progress and handles errors gracefully
"""

import httpx
from pathlib import Path
from urllib.parse import urlparse
import sys


def get_unique_urls(file_path: str) -> list[str]:
    """Read URLs from file and return unique ones."""
    urls = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            url = line.strip()
            if url and url not in urls:
                urls.append(url)
    return urls


def get_filename_from_url(url: str) -> str:
    """Extract filename from URL."""
    parsed = urlparse(url)
    filename = Path(parsed.path).name
    # If no filename found, create one from the URL
    if not filename or not filename.endswith('.pdf'):
        # Use the last part of the path or a hash
        filename = parsed.path.split('/')[-1] or 'download.pdf'
        if not filename.endswith('.pdf'):
            filename += '.pdf'
    return filename


def download_pdf(url: str, output_dir: Path, timeout: int = 30) -> tuple[bool, str]:
    """
    Download a PDF from URL to output directory.
    
    Returns:
        (success, status) where status is 'downloaded', 'skipped', or 'failed'
    """
    filename = get_filename_from_url(url)
    output_path = output_dir / filename
    
    # Skip if file already exists
    if output_path.exists():
        file_size = output_path.stat().st_size / 1024  # Size in KB
        print(f"  ⏭️  Skipping {filename} (already exists, {file_size:.1f} KB)")
        return True, 'skipped'
    
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            
            # Verify it's actually a PDF
            content_type = response.headers.get('content-type', '').lower()
            if 'pdf' not in content_type and not url.endswith('.pdf'):
                print(f"  ⚠️  Warning: {filename} might not be a PDF (content-type: {content_type})")
            
            # Write the file
            output_path.write_bytes(response.content)
            file_size = len(response.content) / 1024  # Size in KB
            print(f"  ✅ Downloaded {filename} ({file_size:.1f} KB)")
            return True, 'downloaded'
            
    except httpx.TimeoutException:
        print(f"  ❌ Timeout downloading {filename}")
        return False, 'failed'
    except httpx.HTTPStatusError as e:
        print(f"  ❌ HTTP error {e.response.status_code} for {filename}")
        return False, 'failed'
    except Exception as e:
        print(f"  ❌ Error downloading {filename}: {e}")
        return False, 'failed'


def main():
    """Main function to orchestrate the download process."""
    # Setup paths
    script_dir = Path(__file__).parent
    pdfs_file = script_dir / 'pdfs.txt'
    output_dir = script_dir / 'pdfs'
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(exist_ok=True)
    
    # Check if pdfs.txt exists
    if not pdfs_file.exists():
        print(f"❌ Error: {pdfs_file} not found!")
        sys.exit(1)
    
    # Get unique URLs
    print("📖 Reading URLs from pdfs.txt...")
    urls = get_unique_urls(str(pdfs_file))
    print(f"📋 Found {len(urls)} unique URLs\n")
    
    if not urls:
        print("⚠️  No URLs found in pdfs.txt")
        sys.exit(0)
    
    # Download each PDF
    print(f"📥 Downloading PDFs to {output_dir}...\n")
    downloaded = 0
    failed = 0
    skipped = 0
    
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {url}")
        success, status = download_pdf(url, output_dir)
        if status == 'downloaded':
            downloaded += 1
        elif status == 'skipped':
            skipped += 1
        else:
            failed += 1
        print()  # Empty line for readability
    
    # Summary
    print("=" * 60)
    print(f"📊 Summary:")
    print(f"   ✅ Downloaded: {downloaded}")
    print(f"   ⏭️  Skipped (already exists): {skipped}")
    print(f"   ❌ Failed: {failed}")
    print(f"   📁 Output directory: {output_dir}")
    print("=" * 60)


if __name__ == '__main__':
    main()

