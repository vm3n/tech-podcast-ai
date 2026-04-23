"""
Main Pipeline — Tech Podcast Generator
Generates one podcast episode per newsletter category.
First 6 articles get deep dive treatment.
Remaining articles get headline mentions.
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
                 article_titles: list, category: str):
    """Generates RSS feed for a specific category."""
    try:
        from feedgen.feed import FeedGenerator

        rss_path = f"feed_{category}.xml"

        fg = FeedGenerator()
        fg.load_extension("podcast")
        fg.id(
            f"https://vm3n.github.io/tech-podcast-ai/"
            f"feed_{category}.xml"
        )
        fg.title(f"Daily {category.upper()} Briefing with Herlin")
        fg.author({"name": "Herlin"})
        fg.link(
            href="https://vm3n.github.io/tech-podcast-ai/",
            rel="alternate"
        )
        fg.subtitle(
            f"Your daily {category} tech briefing"
        )
        fg.language("en")
        fg.podcast.itunes_category("Technology")

        fe = fg.add_entry()
        fe.id(
            f"https://vm3n.github.io/tech-podcast-ai/"
            f"episodes/{date_str}/{category}"
        )
        fe.title(
            f"{category.upper()} Briefing — {date_str}"
        )
        fe.description(
            f"Today's {category} stories: " +
            " | ".join(article_titles[:5])
        )
        fe.enclosure(
            f"https://vm3n.github.io/tech-podcast-ai/"
            f"episodes/{date_str}/{category}.mp3",
            0,
            "audio/mpeg"
        )
        fe.pubDate(
            datetime.now().strftime(
                "%a, %d %b %Y %H:%M:%S +0000"
            )
        )

        fg.rss_str(pretty=True)
        fg.rss_file(rss_path)
        print(f"  RSS feed updated: {rss_path}")
        return True

    except Exception as e:
        print(f"  RSS error: {e}")
        return False


def process_category(category: str, urls: list,
                     date_str: str):
    """
    Runs the full pipeline for one category.
    First 6 articles get deep dive narration.
    Remaining articles get headline mentions.
    """

    print(f"\n{'='*50}")
    print(f"PROCESSING CATEGORY: {category.upper()}")
    print(f"{'='*50}")

    # Create date/category folder structure
    Path(f"episodes/{date_str}").mkdir(
        parents=True, exist_ok=True
    )
    Path(f"scripts/{date_str}").mkdir(
        parents=True, exist_ok=True
    )

    # Top 6 deep dives + up to 4 headlines = max 10
    urls = urls[:15]
    print(f"Processing {len(urls)} articles")
    print(f"  Deep dives : {min(6, len(urls))}")
    print(f"  Headlines  : {max(0, len(urls) - 6)}")

    # Fetch full article content
    print(f"\nFetching articles...")
    articles = fetch_multiple(urls)

    if not articles:
        print(f"No articles fetched for {category}")
        return

    # Three layer dedup
    print(f"\nRunning dedup...")
    unique_articles = full_dedup(articles, date_str)

    if not unique_articles:
        print(f"All {category} articles already covered")
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

    # Generate podcast script
    # First 6 = deep dive, rest = headlines
    print(f"\nGenerating {category} script...")
    episode_script = generate_episode_script(unique_articles)

    # Save script
    script_path = f"scripts/{date_str}/{category}.txt"
    with open(script_path, "w") as f:
        f.write(episode_script)
    print(f"  Script saved: {script_path}")

    # Generate audio
    print(f"\nGenerating {category} audio...")
    episode_path = generate_episode(
        episode_script,
        date_str,
        category=category
    )

    if not episode_path:
        print(f"Audio generation failed for {category}")
        return

    # Save to database
    save_episode(
        date=f"{category}_{date_str}",
        mp3_path=episode_path,
        script_path=script_path,
        article_count=len(unique_articles),
        total_words=len(episode_script.split())
    )

    # Update RSS feed
    article_titles = [a.title for a in unique_articles]
    generate_rss(
        episode_path, date_str,
        article_titles, category
    )

    print(f"\n  {category.upper()} episode ready:")
    print(f"  {episode_path}")


def push_to_github():
    """Auto pushes all new episodes to GitHub Pages."""
    import subprocess
    print("\nPushing to GitHub...")
    try:
        subprocess.run(
            ["git", "add", "episodes/", "scripts/",
             "feed_*.xml"],
            cwd=os.path.expanduser("~/tech-podcast-ai")
        )
        subprocess.run(
            ["git", "commit", "-m",
             f"episodes {datetime.now().strftime('%Y-%m-%d')}"],
            cwd=os.path.expanduser("~/tech-podcast-ai")
        )
        subprocess.run(
            ["git", "push"],
            cwd=os.path.expanduser("~/tech-podcast-ai")
        )
        print("Pushed successfully")
    except Exception as e:
        print(f"Push error: {e}")


def run_pipeline(test_mode: bool = False):
    date_str = datetime.now().strftime("%Y-%m-%d")

    print("\n" + "="*50)
    print(f"TECH PODCAST PIPELINE")
    print(f"Date: {date_str}")
    print("="*50)

    # Setup database
    setup_database()

    # Cleanup old episodes
    print("\nCleaning up old episodes...")
    cleanup_old_episodes(days=3)

    # Get links per category
    if test_mode:
        print("\nTEST MODE — using hardcoded categories")
        category_links = {
            "tech": ["https://arstechnica.com"],
            "ai": ["https://techcrunch.com"],
        }
    else:
        print("\nFetching newsletter links from Gmail...")
        category_links = fetch_newsletter_links()

    if not category_links:
        print("No new links found today. Exiting.")
        return

    print(f"\nCategories to process: {list(category_links.keys())}")

    # Process each category separately
    for category, urls in category_links.items():
        process_category(category, urls, date_str)

    # Push everything to GitHub
    push_to_github()

    print("\n" + "="*50)
    print("ALL CATEGORIES COMPLETE")
    print("="*50)
    get_stats()


if __name__ == "__main__":
    test_mode = (
        len(sys.argv) > 1 and sys.argv[1] == "test"
    )
    reset_mode = "--reset" in sys.argv

    if reset_mode:
        print("Resetting todays URLs from database...")
        from database import get_connection
        today = datetime.now().strftime("%Y-%m-%d")
        conn = get_connection()
        conn.execute(
            "DELETE FROM processed_urls WHERE episode_date = ?",
            (today,)
        )
        conn.execute(
            "DELETE FROM processed_urls WHERE processed_at LIKE ?",
            (f"{today}%",)
        )
        conn.execute(
            "DELETE FROM article_titles WHERE episode_date = ?",
            (today,)
        )
        conn.execute(
            "DELETE FROM episodes WHERE date LIKE ?",
            (f"%{today}",)
        )
        conn.commit()
        conn.close()
        print(f"Reset complete — cleared all URLs processed on {today}")

    run_pipeline(test_mode=test_mode)
