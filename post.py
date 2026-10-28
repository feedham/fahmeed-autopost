"""Daily good-morning posts for a Facebook Page (and optionally its Instagram).

GitHub's scheduler often starts jobs hours late, so this script does NOT post
at run time. Instead, every run it hands the next posts to Facebook as
*scheduled posts* (published=false + scheduled_publish_time), and Facebook
itself publishes them at exactly 09:00 Pakistan time. Dates already handed over
are recorded in state.json so nothing is scheduled twice.

Instagram's API has no scheduling, so Instagram (if IG_USER_ID is set) is
posted by the first run on or after 09:00 each day.

Secrets: FB_PAGE_ID, FB_PAGE_TOKEN (pages_manage_posts, pages_read_engagement;
plus instagram_basic, instagram_content_publish for Instagram), IG_USER_ID (optional)
Optional env: DRY_RUN=true, FORCE_DAY=1-30 with POST_NOW=true to publish now.
"""
import json, os, sys, time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
cfg = json.load(open(os.path.join(ROOT, "schedule.json"), encoding="utf-8"))
STATE = os.path.join(ROOT, "state.json")
state = json.load(open(STATE)) if os.path.exists(STATE) else {}
state.setdefault("fb_scheduled", []); state.setdefault("ig_posted", [])

tz = timezone(timedelta(hours=cfg["timezone_offset_hours"]))
now = datetime.now(tz)
hh, mm = map(int, cfg["post_time"].split(":"))
start = datetime.strptime(cfg["start_date"], "%Y-%m-%d").date()
dry = os.getenv("DRY_RUN", "").lower() == "true"
post_now = os.getenv("POST_NOW", "").lower() == "true"
force = os.getenv("FORCE_DAY", "").strip()

page_id = os.getenv("FB_PAGE_ID", "").strip()
token = os.getenv("FB_PAGE_TOKEN", "").strip()
ig_id = os.getenv("IG_USER_ID", "").strip()
graph = f"https://graph.facebook.com/{os.getenv('GRAPH_VERSION', 'v26.0')}"
repo = os.getenv("GITHUB_REPOSITORY", "feedham/fb-autopost")
branch = os.getenv("GITHUB_REF_NAME", "main")
if not dry and not (page_id and token):
    sys.exit("FB_PAGE_ID and FB_PAGE_TOKEN secrets are missing. "
             "Add them in Settings > Secrets and variables > Actions.")

def posts_for(day):
    idx = (day - start).days % len(cfg["days"])
    return idx, cfg["days"][idx]

def fb_photo(post, when=None):
    data = {"message": post["caption"], "access_token": token}
    if when:
        data.update(published="false", scheduled_publish_time=str(int(when.timestamp())))
    else:
        data["published"] = "true"
    path = os.path.join(ROOT, post["image"])
    mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
    with open(path, "rb") as fh:
        return requests.post(f"{graph}/{page_id}/photos", data=data,
                             files={"source": (os.path.basename(path), fh, mime)}, timeout=120)

def ig_photo(post):
    url = f"https://raw.githubusercontent.com/{repo}/{branch}/{quote(post['image'])}"
    r = requests.post(f"{graph}/{ig_id}/media", data={"image_url": url, "caption": post["caption"],
                      "access_token": token}, timeout=120)
    if not r.ok:
        return False, r.text
    cid = r.json()["id"]
    for _ in range(24):
        s = requests.get(f"{graph}/{cid}", params={"fields": "status_code", "access_token": token}, timeout=60).json()
        if s.get("status_code") == "FINISHED": break
        if s.get("status_code") == "ERROR": return False, s
        time.sleep(5)
    r = requests.post(f"{graph}/{ig_id}/media_publish", data={"creation_id": cid, "access_token": token}, timeout=120)
    return r.ok, r.text

failed = 0

# Manual "post this day right now" mode.
if force and post_now:
    idx, posts = int(force) - 1, cfg["days"][int(force) - 1]
    for post in posts:
        print(f"Posting now: {post['image']}")
        if dry: continue
        r = fb_photo(post); print("Facebook:", r.status_code, r.text); failed += not r.ok
        if ig_id:
            ok, info = ig_photo(post); print("Instagram:", ok, info); failed += not ok
    sys.exit(1 if failed else 0)

# 1) Facebook: schedule today (if still >15 min before post time) and the next days.
ahead = int(cfg.get("schedule_days_ahead", 2))
for d in range(0, ahead + 1):
    day = now.date() + timedelta(days=d)
    if day < start or day.isoformat() in state["fb_scheduled"]:
        continue
    when = datetime(day.year, day.month, day.day, hh, mm, tzinfo=tz)
    if when - now < timedelta(minutes=15):
        continue  # too late for Facebook scheduling; handled by the catch-up below
    idx, posts = posts_for(day)
    ok_all = True
    for post in posts:
        print(f"Schedule FB {when:%Y-%m-%d %H:%M} day {idx + 1}: {post['image']}")
        if dry: continue
        r = fb_photo(post, when)
        print("  ->", r.status_code, r.text); ok_all &= r.ok; failed += not r.ok
    if ok_all and not dry:
        state["fb_scheduled"].append(day.isoformat())

# 2) Catch-up: if today's Facebook post was never scheduled (e.g. first run after 08:45), post it now.
today = now.date()
target = datetime(today.year, today.month, today.day, hh, mm, tzinfo=tz)
if today >= start and today.isoformat() not in state["fb_scheduled"] and now >= target - timedelta(minutes=15):
    idx, posts = posts_for(today)
    if now < target and not dry:
        time.sleep((target - now).total_seconds())
    ok_all = True
    for post in posts:
        print(f"Post FB now (catch-up) day {idx + 1}: {post['image']}")
        if dry: continue
        r = fb_photo(post); print("  ->", r.status_code, r.text); ok_all &= r.ok; failed += not r.ok
    if ok_all and not dry:
        state["fb_scheduled"].append(today.isoformat())

# 3) Instagram: first run on/after post time each day.
if ig_id and today >= start and now >= target and today.isoformat() not in state["ig_posted"]:
    idx, posts = posts_for(today)
    ok_all = True
    for post in posts:
        print(f"Post Instagram day {idx + 1}: {post['image']}")
        if dry: continue
        ok, info = ig_photo(post); print("  ->", ok, info); ok_all &= ok; failed += not ok
    if ok_all and not dry:
        state["ig_posted"].append(today.isoformat())

# Keep the state file short.
for k in ("fb_scheduled", "ig_posted"):
    state[k] = sorted(set(state[k]))[-60:]
if not dry:
    json.dump(state, open(STATE, "w"), indent=1)
print("Done. Scheduled dates:", state["fb_scheduled"][-5:])
sys.exit(1 if failed else 0)
