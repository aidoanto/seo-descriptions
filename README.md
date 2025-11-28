# Lifeline Drupal Issue Audit

We’re migrating the Lifeline Australia site into Drupal. Each new page needs to be free of obvious blockers before it can go live (broken links, legacy environments, placeholder copy, etc.).  
This repo contains a CLI that crawls every URL listed in `seo-descriptions.csv` and reports any issues so the content team can fix them quickly.

## What the script checks

For every page in the CSV the CLI will:

1. Confirm the page itself does not return a 404.
2. Look for internal links that return HTTP 4xx/5xx (broken links).
3. Flag absolute links that still point at the legacy dev/prod domains:  
   `https://lla-drupal-app-prod.salmonground-819df123.australiaeast.azurecontainerapps.io`  
   `https://lla-drupal-app-uat.victoriouspond-08331c17.australiaeast.azurecontainerapps.io`
4. Flag absolute links to `https://lifeline.org.au`, `https://www.lifeline.org.au`, or `https://toolkit.lifeline.org.au` (other Lifeline subdomains such as `give.` or `fundraise.` are allowed).
5. Detect any visible text that still says “lorem ipsum” or “placeholder”.

Every issue becomes one CSV row with the page URL, the issue type, and a short snippet showing what needs attention.

> ℹ️ The crawler inspects only the content inside the page’s `<main>` tag (when present) so inline scripts, nav bars, and footer widgets won’t generate noisy findings.

## Prerequisites

1. Copy `.env.example` to `.env` and fill in:
   - `HTTP_USERNAME`
   - `HTTP_PASSWORD`
     (These are required for the Drupal Basic Auth wall.)
2. Install dependencies using [uv](https://github.com/astral-sh/uv):

   ```
   cd /home/aido/projects/seo-descriptions
   uv sync
   ```

That’s it—no LLM/API keys are needed anymore.

## Running the audit

```
uv run python main.py
```

Useful flags:

- `--limit N` – only audit the first `N` URLs (great for spot checks).
- `--concurrency N` – adjust how many pages are fetched in parallel (default 5).
- `--input /path/to/file.csv` – change the source list (defaults to `seo-descriptions.csv`).
- `--output /path/to/file.csv` – change where the issue report is written (defaults to `seo-descriptions-results.csv`).

The script overwrites the output file on each run so the report always reflects the latest crawl.

## Reading the results

`seo-descriptions-results.csv` has three columns:

| Column       | Description                                                                                                                             |
| ------------ | --------------------------------------------------------------------------------------------------------------------------------------- |
| `URL`        | The page that was audited.                                                                                                              |
| `Issue Type` | One of `Page 404`, `Fetch failed`, `Broken link`, `Absolute link to dev/prod domain`, `Link to lifeline.org.au`, or `Placeholder text`. |
| `Snippet`    | A short summary that points you to the exact problem (failing href, offending text, etc.).                                              |

Fix the issues in Drupal, re-run the CLI, and verify the CSV no longer lists them.

## Troubleshooting tips

- **401/403 errors** – double-check the Basic Auth values in `.env`.
- **Timeouts** – reduce `--concurrency` or re-run with `--limit` for a smaller batch.
- **Unexpected empty report** – confirm the CSV header contains a `link` or `url` column so the loader can find the targets.

If you need to add new health checks, `main.py` is organized so you can plug more validators into the `process_row` function without rewriting the crawler.
