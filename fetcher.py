"""
Stage 1 — Article Fetcher
Fetches full article text from a URL and assigns a confidence tier.
Also extracts proper article title from page.

Tiers:
  full     — 300+ words  — deep dive mode
  partial  — 80-299 words — honest summary mode
  headline — under 80 words — quick mention mode
"""

import requests
import trafilatura
import json
import re
from dataclasses import dataclass


@dataclass
class FetchedArticle:
    url: str
    title: str
    text: str
    word_count: int
    tier: str


def extract_title_from_html(html: str) -> str:
    """
    Tries multiple ways to extract article title from HTML.
    """
    if not html:
        return ""

    # Try og:title first (most reliable for articles)
    og_title = re.search(
        r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']',
        html, re.IGNORECASE
    )
    if og_title:
        return og_title.group(1).strip()

    # Try twitter:title
    tw_title = re.search(
        r'<meta[^>]*name=["\']twitter:title["\'][^>]*content=["\']([^"\']+)["\']',
        html, re.IGNORECASE
    )
    if tw_title:
        return tw_title.group(1).strip()

    # Try <title> tag
    title_tag = re.search(
        r'<title[^>]*>([^<]+)</title>',
        html, re.IGNORECASE
    )
    if title_tag:
        title = title_tag.group(1).strip()
        # Remove site name suffix like "Article Title | Site Name"
        if " | " in title:
            title = title.split(" | ")[0].strip()
        if " - " in title:
            title = title.split(" - ")[0].strip()
        return title

    return ""


def fetch_article(url: str) -> FetchedArticle:
    """
    Fetches full article text from a URL.
    Falls back gracefully if paywall or fetch fails.
    Never skips — always returns something.
    """

    print(f"\nFetching: {url}")

    text = ""
    title = ""
    raw_html = ""

    # Step 1: Try trafilatura first
    try:
        downloaded = trafilatura.fetch_url(url)

        if downloaded:
            raw_html = downloaded
            text = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=True,
                no_fallback=False
            ) or ""

            # Try trafilatura JSON metadata for title
            metadata = trafilatura.extract(
                downloaded,
                output_format="json",
                include_comments=False
            )
            if metadata:
                try:
                    meta = json.loads(metadata)
                    title = meta.get("title", "") or ""
                except Exception:
                    pass

            # If no title from trafilatura, try HTML extraction
            if not title:
                title = extract_title_from_html(downloaded)

    except Exception as e:
        print(f"  trafilatura error: {e}")

    # Step 2: If trafilatura got nothing, try plain requests
    if not text:
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            raw_html = response.text

            text = trafilatura.extract(response.text) or ""

            if not title:
                title = extract_title_from_html(response.text)

        except Exception as e:
            print(f"  requests fallback error: {e}")

    # Step 3: Clean up
    text = text.strip() if text else ""
    word_count = len(text.split()) if text else 0

    # Step 4: Assign confidence tier
    if word_count >= 300:
        tier = "full"
        tier_label = "FULL ARTICLE"
    elif word_count >= 80:
        tier = "partial"
        tier_label = "PARTIAL (paywall likely)"
    else:
        tier = "headline"
        tier_label = "HEADLINE ONLY"

    # Clean up title
    title = title.strip() if title else ""
    # Remove HTML entities
    title = title.replace("&amp;", "&").replace(
        "&quot;", '"').replace("&#39;", "'")

    print(f"  Title : {title or 'Not found'}")
    print(f"  Words : {word_count}")
    print(f"  Tier  : {tier_label}")

    return FetchedArticle(
        url=url,
        title=title if title else url,
        text=text,
        word_count=word_count,
        tier=tier
    )


def fetch_multiple(urls: list) -> list:
    """
    Fetches multiple URLs and returns all results.
    Never skips — even headline tier articles are kept.
    """
    results = []
    seen_urls = set()

    for url in urls:
        if url in seen_urls:
            print(f"\nSkipping duplicate: {url}")
            continue
        seen_urls.add(url)

        article = fetch_article(url)
        results.append(article)

    print("\n" + "="*50)
    print("FETCH SUMMARY")
    print("="*50)
    full     = [a for a in results if a.tier == "full"]
    partial  = [a for a in results if a.tier == "partial"]
    headline = [a for a in results if a.tier == "headline"]
    print(f"  Full articles : {len(full)}")
    print(f"  Partial       : {len(partial)}")
    print(f"  Headline only : {len(headline)}")
    print(f"  Total         : {len(results)}")
    print("="*50)

    return results


if __name__ == "__main__":
    test_urls = [
        "https://techcrunch.com/2026/04/21/openai-launches-codex",
        "https://arstechnica.com",
    ]

    print("Testing article fetcher...")
    print("="*50)

    articles = fetch_multiple(test_urls)

    print("\nDETAILED RESULTS:")
    for i, article in enumerate(articles, 1):
        print(f"\n--- Article {i} ---")
        print(f"Title : {article.title}")
        print(f"Tier  : {article.tier}")
        print(f"Words : {article.word_count}")
        if article.text:
            print(f"Preview: {article.text[:200]}...")
        else:
            print("No text retrieved")
