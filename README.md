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

The workflow ([`.github/workflows/daily-card.yml`](.github/workflows/daily-card.yml))
has no built-in `schedule:` trigger — only `workflow_dispatch: {}`, which
means it only runs when triggered manually or via the GitHub REST API.
Scheduling is handled externally by [cron-job.org](https://cron-job.org),
which calls that API on a timer.

### One-time setup

1. **Create a GitHub personal access token** (Settings → Developer settings →
   Personal access tokens → Fine-grained tokens → Generate new token):
   - Resource owner: your account. Repository access: only
     `magic-card-of-the-day`.
   - Permissions: **Actions → Read and write** (this is the only permission
     needed to trigger a workflow run).
   - Set an expiration and put a reminder to renew it before it lapses,
     otherwise the scheduled runs will silently start failing.
   - Copy the token (`github_pat_...`) somewhere safe — GitHub only shows it
     once.

2. **Create a cron-job.org account** and add a new cron job:
   - **URL:** `https://api.github.com/repos/shuurit/magic-card-of-the-day/actions/workflows/daily-card.yml/dispatches`
   - **Request method:** `POST`
   - **Headers:**
     - `Authorization: Bearer <your fine-grained token>`
     - `Accept: application/vnd.github+json`
     - `Content-Type: application/json`
   - **Body:** `{"ref":"master"}`
   - **Schedule:** daily at 10:00, timezone `America/Denver`. cron-job.org's
     timezone field handles the Mountain Time / DST switch for you, so no
     manual UTC math or split cron rules are needed (unlike GitHub's native
     scheduler, which only runs in fixed UTC).
   - A successful trigger gets an HTTP `204` response with an empty body;
     cron-job.org's execution history will show this per run.

You can also still trigger a run manually any time from the repo's Actions
tab, or with `gh workflow run daily-card.yml`.

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
