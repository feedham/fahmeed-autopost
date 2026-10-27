"""Post today's good-morning image to a Facebook Page and its Instagram account.

Runs from GitHub Actions every morning. Reads schedule.json, works out which
of the 30 days it is (repeating after day 30), waits until the post time
(09:00 Pakistan time by default) and publishes each image with its caption.

Environment variables (set as GitHub secrets):
  FB_PAGE_ID     numeric ID of the Facebook Page
  FB_PAGE_TOKEN  Page access token with pages_manage_posts, instagram_basic,
                 instagram_content_publish permissions
  IG_USER_ID     Instagram professional account ID linked to the Page
                 (optional - leave unset to post on Facebook only)
Optional:
  GRAPH_VERSION  Graph API version, default v26.0
  DRY_RUN        "true" to only print what would be posted
  FORCE_DAY      1-30, post that day's set instead of today's
  NO_WAIT        "true" to post immediately instead of waiting for 09:00
"""
import json, os, sys, time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

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

page_id = os.getenv("FB_PAGE_ID", "").strip()
token = os.getenv("FB_PAGE_TOKEN", "").strip()
ig_id = os.getenv("IG_USER_ID", "").strip()
version = os.getenv("GRAPH_VERSION", "v26.0")
graph = f"https://graph.facebook.com/{version}"
repo = os.getenv("GITHUB_REPOSITORY", "feedham/fahmeed-autopost")
branch = os.getenv("GITHUB_REF_NAME", "main")
if not dry and not (page_id and token):
    sys.exit("FB_PAGE_ID and FB_PAGE_TOKEN secrets are missing. "
             "Add them in Settings > Secrets and variables > Actions.")


def post_instagram(image_rel, caption):
    """Instagram needs a public image URL; the repo is public, so use the raw GitHub link."""
    url = f"https://raw.githubusercontent.com/{repo}/{branch}/{quote(image_rel)}"
    r = requests.post(f"{graph}/{ig_id}/media",
                      data={"image_url": url, "caption": caption, "access_token": token}, timeout=120)
    if not r.ok:
        return False, r.text
    cid = r.json()["id"]
    for _ in range(24):  # wait up to 2 minutes for Instagram to process the image
        s = requests.get(f"{graph}/{cid}", params={"fields": "status_code", "access_token": token}, timeout=60)
        status = s.json().get("status_code")
        if status == "FINISHED":
            break
        if status == "ERROR":
            return False, s.text
        time.sleep(5)
    r = requests.post(f"{graph}/{ig_id}/media_publish",
                      data={"creation_id": cid, "access_token": token}, timeout=120)
    return r.ok, r.text


failed = 0
for n, post in enumerate(posts):
    path = os.path.join(ROOT, post["image"])
    print(f"\n--- {post['image']} ---\n{post['caption']}\n")
    if dry:
        continue
    with open(path, "rb") as fh:
        r = requests.post(
            f"{graph}/{page_id}/photos",
            data={"message": post["caption"], "published": "true", "access_token": token},
            files={"source": (os.path.basename(path), fh, "image/jpeg")},
            timeout=120,
        )
    if r.ok:
        print("Facebook posted:", r.json())
    else:
        failed += 1
        print("Facebook FAILED:", r.status_code, r.text)
    if ig_id:
        ok, info = post_instagram(post["image"], post["caption"])
        print("Instagram posted:" if ok else "Instagram FAILED:", info)
        failed += 0 if ok else 1
    if n < len(posts) - 1:
        time.sleep(cfg.get("seconds_between_posts", 20))

sys.exit(1 if failed else 0)
