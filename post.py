"""Post today's good-morning image to a Facebook Page.

Runs from GitHub Actions every morning. Reads schedule.json, works out which
of the 30 days it is (repeating after day 30), waits until the post time
(09:00 Pakistan time by default) and publishes each image with its caption.

Environment variables (set as GitHub secrets):
  FB_PAGE_ID     numeric ID of the Facebook Page
  FB_PAGE_TOKEN  Page access token with pages_manage_posts permission
Optional:
  GRAPH_VERSION  Graph API version, default v26.0
  DRY_RUN        "true" to only print what would be posted
  FORCE_DAY      1-30, post that day's set instead of today's
  NO_WAIT        "true" to post immediately instead of waiting for 09:00
"""
import json, os, sys, time
from datetime import datetime, timedelta, timezone

import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
cfg = json.load(open(os.path.join(ROOT, "schedule.json"), encoding="utf-8"))
tz = timezone(timedelta(hours=cfg["timezone_offset_hours"]))
now = datetime.now(tz)

dry = os.getenv("DRY_RUN", "").lower() == "true"
force = os.getenv("FORCE_DAY", "").strip()
if force:
    idx = int(force) - 1
else:
    start = datetime.strptime(cfg["start_date"], "%Y-%m-%d").date()
    delta = (now.date() - start).days
    if delta < 0:
        print(f"Schedule starts on {start}; nothing to post today."); sys.exit(0)
    idx = delta % len(cfg["days"])
posts = cfg["days"][idx]
print(f"{now:%Y-%m-%d %H:%M} PKT -> day {idx + 1} ({len(posts)} posts)")

# Wait for the exact post time if the runner started early.
hh, mm = map(int, cfg["post_time"].split(":"))
target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
if not dry and os.getenv("NO_WAIT", "").lower() != "true" and timedelta(0) < target - now < timedelta(hours=2):
    wait = (target - now).total_seconds()
    print(f"Waiting {wait / 60:.1f} min until {cfg['post_time']}…"); sys.stdout.flush()
    time.sleep(wait)

page_id = os.getenv("FB_PAGE_ID", "")
token = os.getenv("FB_PAGE_TOKEN", "")
version = os.getenv("GRAPH_VERSION", "v26.0")
if not dry and not (page_id and token):
    sys.exit("FB_PAGE_ID and FB_PAGE_TOKEN secrets are missing.")

failed = 0
for n, post in enumerate(posts):
    path = os.path.join(ROOT, post["image"])
    print(f"\n--- {post['image']} ---\n{post['caption']}\n")
    if dry:
        continue
    with open(path, "rb") as fh:
        r = requests.post(
            f"https://graph.facebook.com/{version}/{page_id}/photos",
            data={"message": post["caption"], "published": "true", "access_token": token},
            files={"source": (os.path.basename(path), fh, "image/jpeg")},
            timeout=120,
        )
    if r.ok:
        print("Posted:", r.json())
    else:
        failed += 1
        print("FAILED:", r.status_code, r.text)
    if n < len(posts) - 1:
        time.sleep(cfg.get("seconds_between_posts", 20))

sys.exit(1 if failed else 0)
