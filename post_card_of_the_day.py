"""Posts a random Magic: The Gathering "Card of the Day" to a Discord webhook.

Fetches a random legal, non-token, non-joke card from Scryfall, avoids
repeating any card posted within the last REPEAT_WINDOW_DAYS days (tracked
in LOG_FILE), and posts it to Discord as two separate messages: a greeting,
followed by the card's Scryfall page URL (which Discord auto-embeds).
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

SCRIPT_DIR = Path(__file__).resolve().parent
LOG_FILE = SCRIPT_DIR / "posted_cards.json"
RUN_LOG_FILE = SCRIPT_DIR / "run.log"

SCRYFALL_RANDOM_URL = "https://api.scryfall.com/cards/random"
# Excludes joke cards / Un-sets (is:funny) and tokens (t:token).
SCRYFALL_QUERY = "-is:funny -t:token"
# Scryfall rejects requests with a default HTTP-library User-Agent.
REQUEST_HEADERS = {
    "User-Agent": "magic-card-of-the-day/1.0 (+https://github.com/)",
    "Accept": "application/json",
}

REPEAT_WINDOW_DAYS = int(os.environ.get("CARD_REPEAT_WINDOW_DAYS", "60"))
MAX_FETCH_ATTEMPTS = 10
API_RETRY_DELAY_SECONDS = 3
WEBHOOK_RETRY_DELAY_SECONDS = 3

GREETING_MESSAGE = (
    "This is Today's Magic Card of the Day!!! Enjoy fellow Spellcasters :man_mage:"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(RUN_LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def load_posted_cards() -> list[dict]:
    if not LOG_FILE.exists():
        return []
    try:
        with LOG_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        log.error("Could not read %s (%s); treating log as empty.", LOG_FILE, exc)
        return []


def save_posted_card(card_name: str) -> None:
    entries = load_posted_cards()
    entries.append({"name": card_name, "date": datetime.now(timezone.utc).date().isoformat()})
    with LOG_FILE.open("w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


def was_recently_posted(card_name: str, entries: list[dict]) -> bool:
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=REPEAT_WINDOW_DAYS)
    for entry in entries:
        if entry.get("name") == card_name:
            try:
                posted_date = datetime.fromisoformat(entry["date"]).date()
            except (KeyError, ValueError):
                continue
            if posted_date >= cutoff:
                return True
    return False


def fetch_random_card_once() -> dict | None:
    try:
        response = requests.get(
            SCRYFALL_RANDOM_URL,
            params={"q": SCRYFALL_QUERY},
            headers=REQUEST_HEADERS,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        log.warning("Scryfall request failed: %s", exc)
        return None


def fetch_random_card_with_retry() -> dict | None:
    card = fetch_random_card_once()
    if card is not None:
        return card
    log.info("Retrying Scryfall request once after a short delay...")
    time.sleep(API_RETRY_DELAY_SECONDS)
    return fetch_random_card_once()


def fetch_unposted_card() -> dict | None:
    posted_entries = load_posted_cards()
    for attempt in range(1, MAX_FETCH_ATTEMPTS + 1):
        card = fetch_random_card_with_retry()
        if card is None:
            log.error("Scryfall API call failed on attempt %d after retry.", attempt)
            return None

        card_name = card.get("name")
        if not card_name or not card.get("scryfall_uri"):
            log.warning("Scryfall response missing a card name or URL; skipping.")
            continue

        if was_recently_posted(card_name, posted_entries):
            log.info(
                "Attempt %d/%d: '%s' was posted within the last %d days; drawing again.",
                attempt,
                MAX_FETCH_ATTEMPTS,
                card_name,
                REPEAT_WINDOW_DAYS,
            )
            continue

        return card

    log.error(
        "Exhausted %d attempts without finding a card unposted in the last %d days.",
        MAX_FETCH_ATTEMPTS,
        REPEAT_WINDOW_DAYS,
    )
    return None


def post_to_discord(webhook_url: str, message: str) -> bool:
    payload = {"content": message}

    for attempt in (1, 2):
        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
            if response.status_code in (200, 204):
                return True
            log.warning(
                "Discord webhook returned status %d on attempt %d: %s",
                response.status_code,
                attempt,
                response.text,
            )
        except requests.RequestException as exc:
            log.warning("Discord webhook request failed on attempt %d: %s", attempt, exc)

        if attempt == 1:
            log.info("Retrying Discord post once after a short delay...")
            time.sleep(WEBHOOK_RETRY_DELAY_SECONDS)

    return False


def main() -> int:
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        log.error("DISCORD_WEBHOOK_URL environment variable is not set.")
        return 1

    card = fetch_unposted_card()
    if card is None:
        log.error("Could not obtain a fresh card to post today. Giving up.")
        return 1

    card_name = card["name"]
    card_url = card["scryfall_uri"]

    if not post_to_discord(webhook_url, GREETING_MESSAGE):
        log.error("Failed to post greeting message to Discord after retry.")
        return 1

    if not post_to_discord(webhook_url, card_url):
        log.error(
            "Greeting posted, but failed to post '%s' card URL to Discord after retry.",
            card_name,
        )
        return 1

    save_posted_card(card_name)
    log.info("Posted '%s' to Discord and updated %s.", card_name, LOG_FILE.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
