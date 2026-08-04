# Magic Card of the Day

Posts a random Magic: The Gathering card to a Discord channel once a day, using
a webhook. Excludes tokens, Un-sets, and joke cards, and won't repeat a card
that was posted within the last 60 days.

## How it works

1. Calls the Scryfall random-card endpoint with a query that excludes joke
   cards / Un-sets (`-is:funny`) and tokens (`-t:token`).
2. Checks `posted_cards.json` for that card name within the repeat window. If
   it's a repeat, it draws again (up to 10 attempts) before giving up and
   logging an error.
3. Posts to Discord as two separate messages (two separate webhook calls):

   ```
   This is Today's Magic Card of the Day!!! Enjoy fellow Spellcasters :man_mage:
   ```

   ```
   https://scryfall.com/card/...
   ```

   The second message is the card's `scryfall_uri` straight from the API
   response — Discord's own link preview renders the card image, no bot
   syntax needed.
4. On a successful post, appends `{"name": ..., "date": ...}` to
   `posted_cards.json`.

## Configuring the webhook

The script reads the webhook URL from the `DISCORD_WEBHOOK_URL` environment
variable. It is never hardcoded in the script and `.env` is git-ignored.

- **Local testing:** copy `.env.example` to `.env` and fill in your webhook
  URL. `.env` is already in `.gitignore`.
- **GitHub Actions:** the webhook is stored as an encrypted repository secret
  named `DISCORD_WEBHOOK_URL` (Settings → Secrets and variables → Actions).
  The workflow injects it as an env var at run time; it never appears in
  logs or code.

Optional: set `CARD_REPEAT_WINDOW_DAYS` to change the 60-day repeat window
(also settable as a repo variable/secret if you want it configurable in CI).

## Duplicate-avoidance log

`posted_cards.json` is a simple JSON array of `{"name", "date"}` entries. It's
committed to the repo (not git-ignored) so the history persists across runs.
Because GitHub Actions runners are ephemeral, the workflow's last step commits
and pushes the updated `posted_cards.json` back to the repo after each
successful post — so the next day's run sees the full history.

## Schedule

Runs via GitHub Actions on a daily cron schedule, defined in
[`.github/workflows/daily-card.yml`](.github/workflows/daily-card.yml):

```yaml
schedule:
  - cron: "0 15 * * *"  # 15:00 UTC daily
```

- Edit the cron expression to change the time (GitHub Actions schedules are
  always in UTC).
- You can also trigger a run manually from the Actions tab (or `gh workflow
  run daily-card.yml`) thanks to the `workflow_dispatch` trigger — handy for
  testing.
- Note: GitHub may delay scheduled workflow runs by a few minutes during
  periods of high load; it's not guaranteed to the second.

## Error handling

- Scryfall API failures: retried once after a short delay, then logged as an
  error (no post is made).
- Discord webhook failures: retried once after a short delay, then logged as
  an error. The card is only appended to `posted_cards.json` after a
  confirmed successful post.
- Both the console and `run.log` (git-ignored, local only) capture timestamped
  log output. In GitHub Actions, this shows up directly in the workflow run
  logs.

## Running locally

```bash
pip install -r requirements.txt
python post_card_of_the_day.py
```
