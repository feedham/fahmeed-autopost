# Facebook Page auto-poster — setup guide

Every morning at **9:00 AM Pakistan time** this posts 1 image from the
Fahmeed Shaukat Ansari set to your Page, with its caption and hashtags. The 30-day schedule starts on
**24 October 2026** and repeats after day 30.

It runs free on GitHub, so your computer does not need to be on.
One-time setup takes about 30–45 minutes.

---

## Step 1 — Create a Meta developer app

1. Go to **developers.facebook.com** and log in with the Facebook account that is an admin of your Page.
2. Click **My Apps → Create App**.
3. Pick the **Business** type (or the option for managing Pages/content), name it e.g. "Good Morning Poster", and create it.
4. In the app's **App settings → Basic**, add a **Privacy Policy URL** (any simple page you own, or a free privacy-policy page) and save.
5. Switch the app from **Development** to **Live** mode (toggle at the top). Posts made by an app still in Development mode may be visible only to you.

## Step 2 — Get a Page token that doesn't expire

1. Open **developers.facebook.com/tools/explorer** (Graph API Explorer).
2. Choose your app at the top right.
3. Under **Permissions**, add: `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`.
4. Click **Generate Access Token** and approve, selecting your Page.
5. Copy the token, open **developers.facebook.com/tools/debug/accesstoken**, paste it, click **Debug**, then **Extend Access Token** at the bottom. Copy the new long-lived token.
6. Back in Graph API Explorer, paste the long-lived token into the token box and run a GET request for: `me/accounts`
7. The result lists your Pages. For your Page, copy:
   - `id` → this is your **FB_PAGE_ID**
   - `access_token` → this is your **FB_PAGE_TOKEN** (a Page token from a long-lived user token does not expire)

Keep the token private — anyone who has it can post to your Page.

## Step 3 — Put the files on GitHub

1. Create a free account at **github.com** if you don't have one.
2. Click **New repository**, name it `fb-autopost`, choose **Private**, and create it.
3. Click **uploading an existing file** and drag in **everything inside this folder**
   (`post.py`, `schedule.json`, `SETUP.md`, the `posts` folder and the `.github` folder). Commit.
   - The `.github` folder is hidden on some computers. If you can't see it, create the file on GitHub instead:
     **Add file → Create new file**, name it `.github/workflows/daily-post.yml`, and paste the contents of that file.
4. Go to the repo's **Settings → Secrets and variables → Actions → New repository secret** and add:
   - `FB_PAGE_ID` = your Page ID
   - `FB_PAGE_TOKEN` = your Page token

## Step 4 — Test it

1. Open the repo's **Actions** tab (enable workflows if asked).
2. Click **Daily Facebook good-morning posts → Run workflow**.
3. Leave `dry_run = true` and run. Open the run log: it should list the image and caption.
4. To post for real once, run it again with `dry_run = false`, `day = 1`, `no_wait = true`. Check your Page.

After that, nothing else is needed — it runs by itself every day at 9:00.

---

## Changing things later

- **Start date / time:** edit `start_date` or `post_time` in `schedule.json`.
- **Captions:** each day's captions are in `schedule.json` and can be edited directly on GitHub.
- **Stop posting:** Actions tab → the workflow → **⋯ → Disable workflow**.

## Troubleshooting

- **Error 190 / token expired:** repeat Step 2 and update the `FB_PAGE_TOKEN` secret.
- **Error 200 / permission:** make sure the token has `pages_manage_posts` and you're an admin of the Page.
- **Post not visible to others:** switch the app to **Live** mode (Step 1.5).
- **Posted a few minutes late:** GitHub occasionally starts scheduled jobs late. The job starts at 8:30 and waits until 9:00 to absorb most delays.
