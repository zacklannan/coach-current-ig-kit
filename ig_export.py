#!/usr/bin/env python3
"""
Coach Current — Instagram Export

Pulls your own Instagram professional-account data via the Meta API and writes a
clean export to ./export/. Then you drop that export into your Cowork project
(this folder) and the bundled `social-analyst` skill analyzes it.

One file, no AI wiring, no dashboard. It just produces the export.

Run:
    python3 ig_export.py
(or double-click run.command)
"""

import os
import sys
import csv
import json
import time
import datetime as dt
from pathlib import Path

import requests
import pandas as pd
from dotenv import load_dotenv, set_key

API_VERSION = "v23.0"
BASE = f"https://graph.instagram.com/{API_VERSION}"
ENV_PATH = Path(".env")
EXPORT = Path("export")
HISTORY = Path("history")
CACHE = Path(".cache")
TIMEOUT = 30

# Posts older than this (days) are read from cache instead of re-fetched, since
# their metrics barely change. New + recent posts are always refreshed.
REFRESH_DAYS = int(os.getenv("REFRESH_DAYS", "30") or "30")
# Longest we'll pause for a rate-limit window before stopping gracefully.
MAX_WAIT_SECONDS = int(os.getenv("MAX_WAIT_SECONDS", "120") or "120")

# Instagram error codes that mean "you're being rate limited".
RATE_LIMIT_CODES = {4, 17, 32, 613}


class RateLimited(Exception):
    def __init__(self, retry_after=None):
        self.retry_after = retry_after
        super().__init__("rate limited")


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def _estimated_wait(headers):
    """Seconds until rate-limit access is regained, from Meta's usage header."""
    raw = headers.get("X-Business-Use-Case-Usage") or headers.get("x-business-use-case-usage")
    if not raw:
        return None
    try:
        obj = json.loads(raw)
        for items in obj.values():
            for it in items:
                mins = it.get("estimated_time_to_regain_access")
                if mins:
                    return int(mins) * 60
    except (ValueError, AttributeError):
        pass
    return None


def _get(url, params, _retries=3):
    # Retry transient network hiccups (dropped connections, timeouts) instead of
    # crashing the whole run — important for big accounts on flaky Wi-Fi.
    last_err = None
    for attempt in range(_retries):
        try:
            r = requests.get(url, params=params, timeout=TIMEOUT)
            break
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_err = e
            if attempt < _retries - 1:
                time.sleep(2 * (attempt + 1))
    else:
        raise last_err  # all retries failed -> let caller handle it gracefully

    try:
        data = r.json()
    except ValueError:
        if r.status_code == 429:
            raise RateLimited(_estimated_wait(r.headers))
        r.raise_for_status()
        raise
    if isinstance(data, dict) and "error" in data:
        e = data["error"]
        if e.get("code") in RATE_LIMIT_CODES or r.status_code == 429:
            raise RateLimited(_estimated_wait(r.headers))
        raise RuntimeError(f"Graph API error {e.get('code')}: {e.get('message')}")
    if r.status_code == 429:
        raise RateLimited(_estimated_wait(r.headers))
    r.raise_for_status()
    return data


# --------------------------------------------------------------------------- #
# Cache (per-post insights + comments, keyed by post id)
# --------------------------------------------------------------------------- #
def _load_cache(name):
    p = CACHE / f"{name}.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except (ValueError, OSError):
            return {}
    return {}


def _save_cache(name, data):
    CACHE.mkdir(exist_ok=True)
    (CACHE / f"{name}.json").write_text(json.dumps(data))


def _maybe_wait(retry_after):
    """Wait out a short rate-limit window; return True if we waited."""
    if retry_after and retry_after <= MAX_WAIT_SECONDS:
        print(f"  Rate limit reached — pausing {int(retry_after)}s, then resuming...")
        time.sleep(retry_after)
        return True
    return False


def _safe(fn):
    try:
        return fn(), None
    except Exception as e:  # noqa: BLE001 - broad catch for tolerance
        return None, str(e)


# --------------------------------------------------------------------------- #
# Token (handles all three cases; persists long-lived token to .env)
# --------------------------------------------------------------------------- #
def _token_works(token):
    ok, _ = _safe(lambda: _get(f"{BASE}/me", {"fields": "id", "access_token": token}))
    return ok is not None


def ensure_token():
    long_token = os.getenv("IG_ACCESS_TOKEN", "").strip()
    secret = os.getenv("IG_APP_SECRET", "").strip()
    short = os.getenv("IG_SHORT_LIVED_TOKEN", "").strip()

    if long_token:
        try:
            print("Refreshing saved token...")
            d = _get("https://graph.instagram.com/refresh_access_token",
                     {"grant_type": "ig_refresh_token", "access_token": long_token})
            long_token = d["access_token"]
            _save_token(long_token, d.get("expires_in"))
        except RuntimeError as e:
            print(f"  (refresh skipped: {e})")
        return long_token

    if not short:
        sys.exit("No token in .env. Paste your token into IG_SHORT_LIVED_TOKEN and re-run.")

    if secret:
        try:
            print("Exchanging token for a long-lived one...")
            d = _get("https://graph.instagram.com/access_token",
                     {"grant_type": "ig_exchange_token",
                      "client_secret": secret, "access_token": short})
            long_token = d["access_token"]
            _save_token(long_token, d.get("expires_in"))
            return long_token
        except RuntimeError as e:
            print(f"  exchange not applied ({e}); using the token directly...")

    if _token_works(short):
        print("  token valid; using it directly.")
        _save_token(short, None)
        return short
    sys.exit("The token in .env was rejected by Instagram. Regenerate it and re-run.")


def _save_token(token, expires_in):
    if ENV_PATH.exists():
        set_key(str(ENV_PATH), "IG_ACCESS_TOKEN", token)
    if expires_in:
        when = dt.datetime.now() + dt.timedelta(seconds=int(expires_in))
        print(f"  token saved to .env; expires ~{when:%Y-%m-%d}")


# --------------------------------------------------------------------------- #
# Core pulls
# --------------------------------------------------------------------------- #
def get_account(token):
    return _get(f"{BASE}/me", {
        "fields": "id,username,account_type,media_count,followers_count,follows_count",
        "access_token": token})


def get_all_media(token):
    fields = ("id,caption,media_type,media_product_type,timestamp,permalink,"
              "like_count,comments_count")
    url, params = f"{BASE}/me/media", {"fields": fields, "access_token": token, "limit": 100}
    media = []
    while True:
        d = _get(url, params)
        media.extend(d.get("data", []))
        nxt = d.get("paging", {}).get("next")
        if not nxt:
            break
        url, params = nxt, {}
        time.sleep(0.3)
    print(f"  pulled {len(media)} posts")
    return media


POST_METRICS = ["reach", "views", "likes", "comments", "saved", "shares",
                "total_interactions", "profile_visits", "follows"]


def get_media_insights(token, media_id):
    metrics = list(POST_METRICS)
    while metrics:
        try:
            d = _get(f"{BASE}/{media_id}/insights",
                     {"metric": ",".join(metrics), "access_token": token})
            out = {}
            for m in d.get("data", []):
                vals = m.get("values", [])
                out[m["name"]] = vals[0].get("value") if vals else None
            return out
        except RuntimeError as e:
            dropped = [m for m in metrics if m in str(e)]
            if not dropped:
                return {}
            metrics = [m for m in metrics if m not in dropped]
    return {}


# --------------------------------------------------------------------------- #
# Enrichment (all tolerant)
# --------------------------------------------------------------------------- #
def get_demographics(token, uid):
    out = {}
    for b in ("age", "gender", "country", "city"):
        def _pull(bb=b):
            d = _get(f"{BASE}/{uid}/insights", {
                "metric": "follower_demographics", "period": "lifetime",
                "metric_type": "total_value", "timeframe": "last_30_days",
                "breakdown": bb, "access_token": token})
            tv = (d.get("data") or [{}])[0].get("total_value", {})
            res = (tv.get("breakdowns") or [{}])[0].get("results", [])
            return [{"label": "|".join(r.get("dimension_values", []) or []),
                     "value": r.get("value")} for r in res]
        val, _ = _safe(_pull)
        if val:
            out[b] = val
    return out


def get_account_engagement(token, uid):
    out = {}
    for metric in ("reach", "profile_views", "accounts_engaged", "total_interactions"):
        def _pull(m=metric):
            d = _get(f"{BASE}/{uid}/insights",
                     {"metric": m, "period": "day",
                      "metric_type": "total_value", "access_token": token})
            row = (d.get("data") or [{}])[0]
            tv = row.get("total_value")
            return tv.get("value") if tv and tv.get("value") is not None \
                else sum(v.get("value", 0) for v in row.get("values", []))
        val, _ = _safe(_pull)
        if val is not None:
            out[metric] = val
    return out


def get_stories(token, uid):
    stories, err = _safe(lambda: _get(
        f"{BASE}/{uid}/stories",
        {"fields": "id,media_type,timestamp,permalink", "access_token": token}).get("data", []))
    note = ("Stories vanish from the API ~24h after posting; run more often to catch them.")
    if stories is None:
        return [], f"{note} (fetch error: {err})"
    out = []
    for s in stories:
        ins = {}
        for ms in (["reach", "replies", "total_interactions"], ["reach", "replies"], ["reach"]):
            val, _ = _safe(lambda mm=ms, sid=s["id"]: {
                m["name"]: (m.get("values") or [{}])[0].get("value")
                for m in _get(f"{BASE}/{sid}/insights",
                              {"metric": ",".join(mm), "access_token": token}).get("data", [])})
            if val:
                ins = val
                break
        out.append({**s, "insights": ins})
    return out, note


def fetch_comments(token, media_id, max_per=25):
    """One call → a page of a single post's comments. Raises RateLimited/RuntimeError."""
    data = _get(f"{BASE}/{media_id}/comments",
                {"fields": "text,timestamp,like_count", "access_token": token})
    return [{"post_id": media_id, "text": c["text"], "likes": c.get("like_count", 0)}
            for c in data.get("data", [])[:max_per] if c.get("text")]


# --------------------------------------------------------------------------- #
# History (kept: accumulates beyond Meta's 30-day window)
# --------------------------------------------------------------------------- #
def archive_snapshot(account):
    HISTORY.mkdir(exist_ok=True)
    path = HISTORY / "account_history.csv"
    today = dt.date.today().isoformat()
    rows = []
    if path.exists():
        rows = [r for r in csv.DictReader(open(path, newline=""))
                if r.get("date") != today]
    rows.append({"date": today,
                 "followers_count": account.get("followers_count"),
                 "follows_count": account.get("follows_count"),
                 "media_count": account.get("media_count")})
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "followers_count",
                                          "follows_count", "media_count"])
        w.writeheader()
        w.writerows(rows)
    return rows


# --------------------------------------------------------------------------- #
# Build per-post table
# --------------------------------------------------------------------------- #
def build_dataframe(media, insights, followers, status=None):
    status = status or {}
    rows = []
    for m in media:
        pid = m["id"]
        ins = insights.get(pid, {})
        st = status.get(pid, "ok")
        ts = pd.to_datetime(m.get("timestamp"))
        # likes/comments come from the media list, so they're real even if insights
        # were rate-limited. Insight-derived fields stay BLANK (never 0) when missing.
        likes = m.get("like_count")
        comments = m.get("comments_count")
        if st == "missing":
            reach = saved = shares = inter = er = None
        else:
            reach = ins.get("reach")
            saved = ins.get("saved")
            shares = ins.get("shares")
            inter = ins.get("total_interactions")
            if inter is None:
                inter = (likes or 0) + (comments or 0) + (saved or 0) + (shares or 0)
            denom = reach or followers or None
            er = round(inter / denom * 100, 2) if denom else None
        rows.append({
            "date": ts.date() if pd.notna(ts) else None,
            "weekday": ts.day_name() if pd.notna(ts) else None,
            "hour": ts.hour if pd.notna(ts) else None,
            "format": m.get("media_product_type") or m.get("media_type"),
            "reach": reach, "likes": likes, "comments": comments,
            "saved": saved, "shares": shares,
            "total_interactions": inter, "engagement_rate_pct": er,
            "insights_status": st,
            "permalink": m.get("permalink"),
            "caption": (m.get("caption") or "").replace("\n", " ")[:200],
            "timestamp": ts,
        })
    return pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Export writers
# --------------------------------------------------------------------------- #
def write_posts_csv(df):
    cols = ["date", "weekday", "hour", "format", "reach", "likes", "comments",
            "saved", "shares", "total_interactions", "engagement_rate_pct",
            "insights_status", "permalink", "caption"]
    df[cols].to_csv(EXPORT / "posts.csv", index=False)


def write_audience_csv(demo):
    with open(EXPORT / "audience.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["dimension", "label", "value"])
        for dim, rows in demo.items():
            for r in sorted(rows, key=lambda x: (x.get("value") or 0), reverse=True):
                w.writerow([dim, r["label"], r["value"]])


def write_stories_csv(stories):
    with open(EXPORT / "stories.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "media_type", "reach", "replies", "total_interactions"])
        for s in stories:
            i = s.get("insights", {})
            w.writerow([s.get("timestamp"), s.get("media_type"),
                        i.get("reach"), i.get("replies"), i.get("total_interactions")])


def write_comments_csv(comments):
    with open(EXPORT / "comments.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["post_id", "likes", "text"])
        for c in comments:
            w.writerow([c["post_id"], c["likes"], c["text"]])


def _md_table(frame, index_name):
    """Render a DataFrame (with a meaningful index) as a markdown table. No deps."""
    cols = list(frame.columns)
    out = ["| " + index_name + " | " + " | ".join(str(c) for c in cols) + " |",
           "| " + " | ".join("---" for _ in range(len(cols) + 1)) + " |"]
    for idx, row in frame.iterrows():
        out.append("| " + str(idx) + " | " +
                   " | ".join("" if pd.isna(v) else str(v) for v in row) + " |")
    return "\n".join(out)


def write_summary_md(df, account, demo, engagement, stories, story_note,
                     comments, comment_note, follower_hist):
    # Analyze only posts with complete metrics; missing != zero.
    dfa = df[df["insights_status"] != "missing"] if not df.empty else df
    total = len(df)
    missing = int((df["insights_status"] == "missing").sum()) if not df.empty else 0
    complete = total - missing

    L = []
    a = L.append
    a(f"# Account summary — @{account.get('username','')}")
    a(f"_Exported {dt.datetime.now():%Y-%m-%d %H:%M}_\n")
    a("> Drop this whole `export/` folder's files into your Cowork project and ask "
      "the **social-analyst** skill to analyze them.\n")

    if missing:
        a(f"> ⚠️ **Partial data:** {complete} of {total} posts have complete metrics. "
          f"Instagram rate-limited the other {missing} this run. **Run the kit again "
          f"later and they'll fill in** (already-captured posts are skipped, so it's "
          f"quick). The analysis below uses only the {complete} complete posts; the "
          f"missing ones are excluded, not counted as zero.\n")

    a("## Snapshot")
    a(f"- Followers: {account.get('followers_count')}")
    a(f"- Account type: {account.get('account_type')}")
    a(f"- Posts: {account.get('media_count')} total · {complete} with complete metrics"
      + (f" · {missing} pending (rate-limited)" if missing else ""))
    if not dfa.empty:
        er = dfa["engagement_rate_pct"].dropna()
        if not er.empty:
            a(f"- Avg engagement rate: {er.mean():.2f}% (median {er.median():.2f}%)")
        a(f"- Date range: {dfa['date'].min()} to {dfa['date'].max()}")
        if complete < 30:
            a(f"\n> Sample note: only {complete} complete posts — treat day/hour splits "
              f"as weak hints.")
    a("")

    if not dfa.empty:
        a("## By format")
        g = dfa.groupby("format").agg(
            posts=("format", "count"), avg_reach=("reach", "mean"),
            avg_interactions=("total_interactions", "mean"),
            avg_eng_rate=("engagement_rate_pct", "mean"))
        g["posts"] = g["posts"].astype(int)
        g[["avg_reach", "avg_interactions", "avg_eng_rate"]] = \
            g[["avg_reach", "avg_interactions", "avg_eng_rate"]].round(1)
        a(_md_table(g, "format"))
        a("\n## By weekday")
        wd = dfa.dropna(subset=["engagement_rate_pct"]).groupby("weekday")[
            "engagement_rate_pct"].mean().round(2).to_frame("avg_eng_rate")
        a(_md_table(wd, "weekday"))
        a("\n## By hour")
        hr = dfa.dropna(subset=["engagement_rate_pct"]).groupby("hour")[
            "engagement_rate_pct"].mean().round(2).to_frame("avg_eng_rate")
        a(_md_table(hr, "hour"))
        a("\n## Top posts")
        for _, r in dfa.sort_values("total_interactions", ascending=False).head(5).iterrows():
            a(f"- {r['date']} · {r['format']} · reach {r['reach']} · "
              f"interactions {r['total_interactions']} — \"{r['caption'][:70]}\"")
        a("")

    if demo:
        a("## Audience")
        for dim in ("age", "gender", "country", "city"):
            if demo.get(dim):
                top = sorted(demo[dim], key=lambda x: (x.get("value") or 0), reverse=True)[:5]
                a(f"- {dim}: " + ", ".join(f"{r['label']} ({r['value']})" for r in top))
        a("")

    if engagement:
        a("## Account engagement (recent)")
        for k, v in engagement.items():
            a(f"- {k}: {v}")
        a("")

    a("## Stories")
    if stories:
        for s in stories:
            i = s.get("insights", {})
            a(f"- {s.get('timestamp')} · " + ", ".join(f"{k}={v}" for k, v in i.items()))
    else:
        a(f"- None captured. {story_note}")
    a("")

    a("## Audience voice (comments)")
    if comments:
        for c in comments[:60]:
            a(f"- {c['text']}")
    else:
        a(f"- None. {comment_note or ''}")
    a("")

    if follower_hist and len(follower_hist) > 1:
        a("## Follower history (local snapshots)")
        a(", ".join(f"{r['date']}: {r['followers_count']}" for r in follower_hist[-12:]))
        a("")

    (EXPORT / "account-summary.md").write_text("\n".join(L), encoding="utf-8")


# --------------------------------------------------------------------------- #
def main():
    load_dotenv(ENV_PATH)
    EXPORT.mkdir(exist_ok=True)
    want_comments = os.getenv("ENABLE_COMMENTS", "false").strip().lower() in ("1", "true", "yes")
    want_stories = os.getenv("ENABLE_STORIES", "true").strip().lower() in ("1", "true", "yes")

    token = ensure_token()

    print("Fetching account...")
    account = get_account(token)
    uid = account["id"]

    print("Fetching posts...")
    media = get_all_media(token)

    # Per-post insights + comments, with cache (skip old posts), rate-limit backoff,
    # and resilience to network hiccups. Progress is saved every 25 posts and in a
    # finally block, so a crash or stop never loses what was already fetched — the
    # next run resumes from the cache.
    print("Fetching per-post insights" + (" + comments" if want_comments else "") + "...")
    ins_cache = _load_cache("insights")
    com_cache = _load_cache("comments")
    insights, comments_by_post, status = {}, {}, {}
    comment_note = None if want_comments else "Comments disabled (ENABLE_COMMENTS=false)."
    limited = False
    net_fails = 0
    now = dt.datetime.now(dt.timezone.utc)

    def _persist():
        _save_cache("insights", ins_cache)
        _save_cache("comments", com_cache)

    try:
        for i, m in enumerate(media, 1):
            pid = m["id"]
            ts = pd.to_datetime(m.get("timestamp"), utc=True, errors="coerce")
            recent = pd.notna(ts) and (now - ts.to_pydatetime()).days <= REFRESH_DAYS

            # ---- insights ----
            if pid in ins_cache and not recent:
                insights[pid] = ins_cache[pid]
                status[pid] = "ok"
            elif limited:
                insights[pid] = ins_cache.get(pid, {})
                status[pid] = "ok" if pid in ins_cache else "missing"
            else:
                try:
                    insights[pid] = get_media_insights(token, pid)
                    ins_cache[pid] = insights[pid]
                    status[pid] = "ok"
                    net_fails = 0
                except RateLimited as rl:
                    if _maybe_wait(rl.retry_after):
                        try:
                            insights[pid] = get_media_insights(token, pid)
                            ins_cache[pid] = insights[pid]
                            status[pid] = "ok"
                        except Exception:
                            limited = True
                    else:
                        limited = True
                    if pid not in status:
                        insights[pid] = ins_cache.get(pid, {})
                        status[pid] = "ok" if pid in ins_cache else "missing"
                except requests.exceptions.RequestException:
                    # Transient network failure on this post: skip it, keep going.
                    net_fails += 1
                    insights[pid] = ins_cache.get(pid, {})
                    status[pid] = "ok" if pid in ins_cache else "missing"
                    if net_fails >= 5:
                        print("  Network keeps timing out — stopping here; progress is "
                              "saved. Re-run later to finish.")
                        limited = True

            # ---- comments ----
            if want_comments:
                if pid in com_cache and not recent:
                    comments_by_post[pid] = com_cache[pid]
                elif limited:
                    comments_by_post[pid] = com_cache.get(pid, [])
                else:
                    try:
                        com_cache[pid] = fetch_comments(token, pid)
                        comments_by_post[pid] = com_cache[pid]
                    except RateLimited:
                        limited = True
                        comments_by_post[pid] = com_cache.get(pid, [])
                    except requests.exceptions.RequestException:
                        comments_by_post[pid] = com_cache.get(pid, [])
                    except RuntimeError:
                        comment_note = ("Comment text needs the "
                                        "'instagram_business_manage_comments' permission, "
                                        "included in a freshly generated token.")
                        want_comments = False  # stop trying for the rest

            if i % 25 == 0:
                print(f"  {i}/{len(media)}")
                _persist()  # incremental save so progress survives a crash
            time.sleep(0.25)
    finally:
        _persist()  # always save what we have, even on error/interrupt

    comments = [c for rows in comments_by_post.values() for c in rows]

    print("Fetching demographics, engagement, stories...")
    demo = get_demographics(token, uid)
    engagement = get_account_engagement(token, uid)
    stories, story_note = get_stories(token, uid) if want_stories else ([], "Stories disabled.")

    follower_hist = archive_snapshot(account)
    df = build_dataframe(media, insights, account.get("followers_count"), status)

    # Write the export
    write_posts_csv(df)
    write_audience_csv(demo)
    write_stories_csv(stories)
    write_comments_csv(comments)
    write_summary_md(df, account, demo, engagement, stories, story_note,
                     comments, comment_note, follower_hist)

    missing = sum(1 for s in status.values() if s == "missing")
    print(f"\nDone. Export written to {EXPORT.resolve()}/")
    for f in ("account-summary.md", "posts.csv", "audience.csv", "stories.csv", "comments.csv"):
        print(f"  - {f}")
    if missing:
        print(f"\n⚠️  {missing} posts couldn't be fetched this run (rate limit or a")
        print("    network hiccup) and are marked pending. Just run the kit again later —")
        print("    it resumes from where it left off (everything fetched is cached).")
    print("\nNext: open this folder as a Cowork project and ask the social-analyst")
    print("skill to analyze the export.")


if __name__ == "__main__":
    main()
