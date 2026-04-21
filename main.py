"""
Main Pipeline — Tech Podcast Generator
Complete pipeline with full three layer dedup,
database tracking, cleanup, and RSS generation.
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from database import (
    setup_database,
    save_episode,
    cleanup_old_episodes,
    mark_url_processed,
    get_stats
)
from gmail_fetcher import fetch_newsletter_links
from fetcher import fetch_multiple
from narrator import generate_episode_script
from tts import generate_episode
from dedup import full_dedup

load_dotenv()


def generate_rss(episode_path: str, date_str: str,
                 article_titles: list):
    try:
        from feedgen.feed import FeedGenerator

        fg = FeedGenerator()
        fg.load_extension("podcast")
        fg.id(
            "https://your-username.github.io/"
            "tech-podcast/feed.xml"
        )
        fg.title("My Daily Tech Briefing")
        fg.author({"name": "Nova", "email": "your@gmail.com"})
        fg.link(
            href="https://your-username.github.io/tech-podcast/",
            rel="alternate"
        )
        fg.subtitle("Your personal AI-powered daily tech podcast")
        fg.language("en")
        fg.podcast.itunes_category("Technology")

        fe = fg.add_entry()
        fe.id(
            f"https://your-username.github.io/"
            f"tech-podcast/{date_str}"
        )
        fe.title(f"Tech Briefing — {date_str}")
        fe.description(
            "Today's stories: " +
            " | ".join(article_titles[:5])
        )
        fe.enclosure(
            f"https://your-username.github.io/tech-podcast/"
            f"episodes/{date_str}.mp3",
            0,
            "audio/mpeg"
        )
        fe.pubDate(
            datetime.now().strftime(
                "%a, %d %b %Y %H:%M:%S +0000"
            )
        )

        fg.rss_str(pretty=True)
        fg.rss_file("feed.xml")
        print(f"  RSS feed updated: feed.xml")
        return True

    except Exception as e:
        print(f"  RSS error: {e}")
        return False


def run_pipeline(test_mode: bool = False):
    date_str = datetime.now().strftime("%Y-%m-%d")

    print("\n" + "="*50)
    print(f"TECH PODCAST PIPELINE")
    print(f"Date: {date_str}")
    print("="*50)

    # Setup database
    setup_database()

    # Cleanup old episodes first
    print("\nCleaning up old episodes...")
    cleanup_old_episodes(days=14)

    # ----------------------------------------
    # Step 1 — Get article links
    # ----------------------------------------
    if test_mode:
        print("\nTEST MODE — using hardcoded URLs")
        urls = [
            "https://arstechnica.com",
            "https://techcrunch.com",
        ]
    else:
        print("\nStep 1 — Fetching links from Gmail Podcasts label...")
        urls = fetch_newsletter_links()

    if not urls:
        print("No new links found today. Exiting.")
        return

    # Limit to 8 articles max
    urls = urls[:8]
    print(f"\nTotal links to process: {len(urls)}")

    # ----------------------------------------
    # Step 2 — Fetch full article content
    # ----------------------------------------
    print("\nStep 2 — Fetching full article content...")
    articles = fetch_multiple(urls)

    if not articles:
        print("No articles fetched. Exiting.")
        return

    # ----------------------------------------
    # Step 3 — Three layer dedup
    # ----------------------------------------
    print("\nStep 3 — Running dedup checks...")
    unique_articles = full_dedup(articles, date_str)

    if not unique_articles:
        print("All articles already covered recently. Exiting.")
        return

    # Mark all unique articles as processed
    for article in unique_articles:
        mark_url_processed(
            url=article.url,
            title=article.title,
            tier=article.tier,
            word_count=article.word_count,
            episode_date=date_str
        )

    # ----------------------------------------
    # Step 4 — Generate podcast script via Groq
    # ----------------------------------------
    print("\nStep 4 — Generating podcast script with Groq...")
    episode_script = generate_episode_script(unique_articles)

    Path("scripts").mkdir(exist_ok=True)
    script_path = f"scripts/{date_str}.txt"
    with open(script_path, "w") as f:
        f.write(episode_script)
    print(f"  Script saved: {script_path}")

    # ----------------------------------------
    # Step 5 — Generate TTS audio
    # ----------------------------------------
    print("\nStep 5 — Generating audio with Kokoro TTS...")
    episode_path = generate_episode(episode_script, date_str)

    if not episode_path:
        print("Audio generation failed. Exiting.")
        return

    # ----------------------------------------
    # Step 6 — Save episode to database
    # ----------------------------------------
    save_episode(
        date=date_str,
        mp3_path=episode_path,
        script_path=script_path,
        article_count=len(unique_articles),
        total_words=len(episode_script.split())
    )

    # ----------------------------------------
    # Step 7 — Update RSS feed
    # ----------------------------------------
    print("\nStep 7 — Updating RSS feed...")
    article_titles = [a.title for a in unique_articles]
    generate_rss(episode_path, date_str, article_titles)

    # ----------------------------------------
    # Done
    # ----------------------------------------
    print("\n" + "="*50)
    print("PIPELINE COMPLETE")
    print("="*50)
    print(f"  Episode  : {episode_path}")
    print(f"  Script   : {script_path}")
    print(f"  RSS      : feed.xml")
    print(f"\nListen:")
    print(f"  open {episode_path}")
    print("="*50)

    get_stats()


if __name__ == "__main__":
    test_mode = (
        len(sys.argv) > 1 and sys.argv[1] == "test"
    )
    run_pipeline(test_mode=test_mode)
