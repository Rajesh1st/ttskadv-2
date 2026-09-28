# RSS Telegram Posting Bot — Advanced Rules

This version keeps the existing Sky/HDM/ExtraFlix/FilmyFly scrapers and adds a configurable posting policy layer.

## New controls

Open the Telegram admin UI with `/panel` (or `/rules`). The inline buttons can toggle each source and inspect the current rules. The same settings are available as commands:

```text
/setposts ff 5                 # maximum new source posts per check; 0 = unlimited
/setquality ff movie all       # all movie qualities
/setquality ff movie 1080p,720p
/setquality ff series all
/setquality ff series 1080p    # only one series quality
/setsize ff 4096               # maximum file size in MB; 0 = unlimited
/setzip ff 10                  # maximum ZIP size in GB; 0 = unlimited
/setgap ff post 30             # minimum gap between ordinary posts
/setgap ff quality 10          # minimum gap between quality links
/queue                         # inspect pending items
```

The commands work independently for `sky`, `hdm`, `ef`, and `ff`. Existing enable/disable, channel, extractor, caption, and source commands remain available.

### Behavior

- **Movie and series quality policies are separate.** `all` sends every extracted quality. `selected` sends only the listed qualities.
- **Unknown quality names** remain allowed by default so a scraper does not silently discard a link. Set `unknown_quality` to `reject` in `posting_rules` when strict matching is required.
- **File and ZIP limits** are evaluated before sending. FF size metadata is now preserved from the scraper; other sources can supply `size_mb`/`size_text` when available.
- **Post and quality gaps** are enforced per source/channel. A link that arrives during a gap is stored as pending and retried on the next loop.
- **Maximum posts per cycle** prevents a large RSS batch from flooding a channel.

## MongoDB

Set these variables to use MongoDB for settings, seen-post state, statistics, and the pending queue:

```env
MONGODB_URI=mongodb://user:password@host:27017/?authSource=admin
MONGODB_DB=rss_bot
```

If MongoDB is not reachable or the variables are omitted, the bot safely falls back to `config.json`, `seen_posts.json`, `stats.json`, and `queue.json`.

## Run

```bash
pip install -r requirements.txt
export BOT_TOKEN=...
export ADMIN_ID=...
export POST_CHAT_ID=-100...
python main.py
```

Docker/Render startup remains unchanged (`start.sh` runs Uvicorn on `$PORT`).

## Validation

```bash
python3 run_policy_tests.py
python3 -m compileall -q .
```
