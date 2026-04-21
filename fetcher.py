"""
Stage 1 — Article Fetcher
Fetches full article text from a URL and assigns a confidence tier.

Tiers:
  full     — 300+ words  — deep dive mode
  partial  — 80-299 words — honest summary mode
  headline — under 80 words — quick mention mode
"""

import requests
import trafilatura
import json
from dataclasses import dataclass


@dataclass
class FetchedArticle:
    url: str
    title: str
    text: str
    word_count: int
    tier: str


def fetch_article(url: str) -> FetchedArticle:
    print(f"\nFetching: {url}")

    text = ""
    title = ""

    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=True,
                no_fallback=False
            ) or ""

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

    except Exception as e:
        print(f"  trafilatura error: {e}")

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
            text = trafilatura.extract(response.text) or ""
        except Exception as e:
            print(f"  requests fallback error: {e}")

    text = text.strip()
    word_count = len(text.split()) if text else 0

    if word_count >= 300:
        tier = "full"
        tier_label = "FULL ARTICLE"
    elif word_count >= 80:
        tier = "partial"
        tier_label = "PARTIAL (paywall likely)"
    else:
        tier = "headline"
        tier_label = "HEADLINE ONLY"

    print(f"  Title : {title or 'Not found'}")
    print(f"  Words : {word_count}")
    print(f"  Tier  : {tier_label}")

    return FetchedArticle(
        url=url,
        title=title or url,
        text=text,
        word_count=word_count,
        tier=tier
    )


def fetch_multiple(urls: list) -> list:
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
        "https://techcrunch.com",
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
