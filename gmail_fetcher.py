"""
Stage 3 — Gmail Fetcher (updated)
Reads emails tagged with 'Podcasts' label.
Uses database for proper dedup.
"""

import os
import base64
import re
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from database import setup_database, is_url_seen, mark_url_processed

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_gmail_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file(
            "token.json", SCOPES
        )
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def extract_links_from_email(body: str) -> list:
    urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', body)

    skip_keywords = [
        "unsubscribe", "optout", "opt-out", "tracking",
        "click.convertkit", "link.mail", "mailchimp",
        "sendgrid", "mandrillapp", "list-manage",
        ".png", ".jpg", ".gif", ".ico", "utm_",
        "pstmrk", "track.", "aweber", "w3.org",
        "open?m=", "ea.pstmrk", "confirm",
        "subscription", "email/unsubscribe"
    ]

    clean_urls = []
    seen = set()
    for url in urls:
        url = url.rstrip(".,;:)")
        if any(kw in url.lower() for kw in skip_keywords):
            continue
        if url in seen:
            continue
        seen.add(url)
        clean_urls.append(url)

    return clean_urls


def get_email_body(service, msg_id: str) -> str:
    try:
        message = service.users().messages().get(
            userId="me",
            id=msg_id,
            format="full"
        ).execute()

        payload = message.get("payload", {})
        parts = payload.get("parts", [])
        body = ""

        if parts:
            for part in parts:
                if part.get("mimeType") == "text/html":
                    data = part.get("body", {}).get("data", "")
                    if data:
                        body = base64.urlsafe_b64decode(
                            data
                        ).decode("utf-8", errors="ignore")
                        break
            if not body:
                for part in parts:
                    if part.get("mimeType") == "text/plain":
                        data = part.get("body", {}).get("data", "")
                        if data:
                            body = base64.urlsafe_b64decode(
                                data
                            ).decode("utf-8", errors="ignore")
                            break
        else:
            data = payload.get("body", {}).get("data", "")
            if data:
                body = base64.urlsafe_b64decode(
                    data
                ).decode("utf-8", errors="ignore")

        return body
    except Exception as e:
        print(f"  Error getting email body: {e}")
        return ""


def fetch_newsletter_links(hours_back: int = 24) -> list:
    print("\n" + "="*50)
    print("GMAIL INGESTION")
    print("="*50)

    # Setup database first
    setup_database()

    service = get_gmail_service()

    # Search ONLY emails with Podcasts label
    # This is the tag system we set up in Gmail
    query = "label:Podcasts newer_than:1d"
    print(f"\nSearching Gmail label:Podcasts...")

    try:
        results = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=50
        ).execute()
        messages = results.get("messages", [])
        print(f"Found {len(messages)} tagged newsletter emails")

    except Exception as e:
        print(f"Gmail API error: {e}")
        return []

    all_links = []
    newsletter_count = 0
    today = datetime.now().strftime("%Y-%m-%d")

    for msg in messages:
        try:
            meta = service.users().messages().get(
                userId="me",
                id=msg["id"],
                format="metadata",
                metadataHeaders=["From", "Subject"]
            ).execute()

            headers = meta.get("payload", {}).get("headers", [])
            sender = ""
            subject = ""

            for header in headers:
                if header["name"] == "From":
                    sender = header["value"].lower()
                if header["name"] == "Subject":
                    subject = header["value"]

            newsletter_count += 1
            print(f"\n  Newsletter : {subject[:50]}")
            print(f"  From       : {sender[:50]}")

            body = get_email_body(service, msg["id"])
            if not body:
                continue

            links = extract_links_from_email(body)
            print(f"  Links found: {len(links)}")

            # Filter already processed URLs using database
            new_links = []
            for link in links:
                if not is_url_seen(link, days=7):
                    new_links.append(link)
                    # Mark as processed with episode date
                    mark_url_processed(
                        url=link,
                        episode_date=today
                    )

            print(f"  New links  : {len(new_links)}")
            all_links.extend(new_links)

        except Exception as e:
            print(f"  Error processing email: {e}")
            continue

    print(f"\n{'='*50}")
    print(f"INGESTION SUMMARY")
    print(f"{'='*50}")
    print(f"  Newsletters found : {newsletter_count}")
    print(f"  Total new links   : {len(all_links)}")
    print(f"{'='*50}")

    return all_links


if __name__ == "__main__":
    links = fetch_newsletter_links()
    print("\nLinks collected:")
    for i, link in enumerate(links[:10], 1):
        print(f"  {i}. {link}")
