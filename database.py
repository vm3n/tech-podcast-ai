"""
Database — SQLite tracker
Tracks processed URLs, episodes, and article history.
Prevents duplicate articles across episodes.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


DB_PATH = "podcast.db"


def get_connection():
    """Returns a database connection."""
    return sqlite3.connect(DB_PATH)


def setup_database():
    """
    Creates all tables if they don't exist.
    Run this once at the start of every pipeline run.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Track every URL we have ever processed
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processed_urls (
            url TEXT PRIMARY KEY,
            title TEXT,
            tier TEXT,
            word_count INTEGER,
            processed_at TEXT,
            episode_date TEXT
        )
    """)

    # Track every episode we have generated
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS episodes (
            date TEXT PRIMARY KEY,
            mp3_path TEXT,
            script_path TEXT,
            article_count INTEGER,
            total_words INTEGER,
            created_at TEXT
        )
    """)

    # Track article titles to catch same story
    # from different URLs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS article_titles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            url TEXT,
            episode_date TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()
    print("  Database ready: podcast.db")


def is_url_seen(url: str, days: int = 7) -> bool:
    """
    Returns True if this URL was processed
    in the last N days.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    cursor.execute(
        """SELECT url FROM processed_urls
           WHERE url = ? AND processed_at > ?""",
        (url, cutoff)
    )
    result = cursor.fetchone()
    conn.close()
    return result is not None


def is_title_seen(title: str, days: int = 7) -> bool:
    """
    Returns True if a very similar title was
    already covered in the last N days.
    Catches same story from different URLs.
    """
    if not title or title.startswith("http"):
        return False

    conn = get_connection()
    cursor = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    # Get recent titles
    cursor.execute(
        """SELECT title FROM article_titles
           WHERE created_at > ?""",
        (cutoff,)
    )
    recent_titles = [row[0].lower() for row in cursor.fetchall()]
    conn.close()

    # Simple similarity check
    # If 3+ words match it is probably the same story
    title_words = set(title.lower().split())
    for seen_title in recent_titles:
        seen_words = set(seen_title.lower().split())
        common = title_words & seen_words
        # Remove common short words
        common -= {"the", "a", "an", "is", "in", "of",
                   "to", "and", "for", "how", "why",
                   "what", "new", "with"}
        if len(common) >= 3:
            return True

    return False


def mark_url_processed(url: str, title: str = "",
                       tier: str = "", word_count: int = 0,
                       episode_date: str = ""):
    """Marks a URL as processed in the database."""
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    cursor.execute(
        """INSERT OR REPLACE INTO processed_urls
           (url, title, tier, word_count, processed_at, episode_date)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (url, title, tier, word_count, now, episode_date)
    )

    # Also track title for duplicate story detection
    if title and not title.startswith("http"):
        cursor.execute(
            """INSERT INTO article_titles
               (title, url, episode_date, created_at)
               VALUES (?, ?, ?, ?)""",
            (title, url, episode_date, now)
        )

    conn.commit()
    conn.close()


def save_episode(date: str, mp3_path: str,
                 script_path: str, article_count: int,
                 total_words: int):
    """Saves episode metadata to database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT OR REPLACE INTO episodes
           (date, mp3_path, script_path, article_count,
            total_words, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (date, mp3_path, script_path, article_count,
         total_words, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    print(f"  Episode saved to database: {date}")


def cleanup_old_episodes(days: int = 14):
    """
    Deletes episode MP3 files older than N days
    to keep storage clean.
    Keeps database records for dedup history.
    """
    import os
    conn = get_connection()
    cursor = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    cursor.execute(
        "SELECT mp3_path FROM episodes WHERE created_at < ?",
        (cutoff,)
    )
    old_episodes = cursor.fetchall()

    deleted = 0
    for (mp3_path,) in old_episodes:
        if mp3_path and os.path.exists(mp3_path):
            os.remove(mp3_path)
            deleted += 1
            print(f"  Deleted old episode: {mp3_path}")

    conn.close()
    print(f"  Cleaned up {deleted} old episode files")


def get_stats():
    """Prints database stats."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM processed_urls")
    url_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM episodes")
    episode_count = cursor.fetchone()[0]

    cursor.execute(
        """SELECT date, article_count, total_words
           FROM episodes ORDER BY date DESC LIMIT 5"""
    )
    recent = cursor.fetchall()

    conn.close()

    print("\n" + "="*50)
    print("DATABASE STATS")
    print("="*50)
    print(f"  Total URLs processed : {url_count}")
    print(f"  Total episodes       : {episode_count}")
    print("\n  Recent episodes:")
    for date, articles, words in recent:
        print(f"    {date} — {articles} articles, {words} words")
    print("="*50)


if __name__ == "__main__":
    setup_database()
    get_stats()
