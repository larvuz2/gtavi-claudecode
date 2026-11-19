"""Viral radar: the most-viewed Twitch clips of a game, ranked by views per hour.

Other viewers already clipped and upvoted these moments, so the view count is a ready-made virality signal.
No Twitch account or key needed. Writes clips.md + clips.json.

usage: python clips.py [--game "Grand Theft Auto VI"] [--period LAST_DAY|LAST_WEEK] [--limit 40] [--lang en] [--out clips.md]
next:  python moments.py <clip url>   then   python cut.py jobs/<id> --layout focus|react ...
"""
import argparse, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from twitch import gql, started_ts

_Q = """query($name:String!,$n:Int!,$p:ClipsPeriod!){ game(name:$name){ displayName clips(first:$n, criteria:{period:$p, sort:VIEWS_DESC}){
 edges{ node{ slug title viewCount durationSeconds createdAt language url broadcaster{ login displayName } curator{ login } } } } } }"""


def top_clips(game="Grand Theft Auto VI", period="LAST_DAY", limit=40):
    d = gql(_Q, {"name": game, "n": int(limit), "p": period})
    if d.get("errors"):
        sys.exit(f"twitch: {d['errors'][0].get('message')}")
    g = (d.get("data") or {}).get("game")
    if not g:
        sys.exit(f'twitch: no category named "{game}"')
    now, rows = time.time(), []
    for e in g["clips"]["edges"]:
        n = e["node"]; b = n.get("broadcaster") or {}
        age = max(0.25, (now - (started_ts(n["createdAt"]) or now)) / 3600)
        rows.append({"views": n["viewCount"], "views_per_h": round(n["viewCount"] / age), "age_h": round(age, 1),
                     "seconds": n["durationSeconds"], "lang": (n.get("language") or "").lower(), "streamer": b.get("displayName") or b.get("login"),
                     "login": b.get("login"), "clipped_by": (n.get("curator") or {}).get("login"), "title": n["title"], "url": n["url"]})
    return sorted(rows, key=lambda r: r["views_per_h"], reverse=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default="Grand Theft Auto VI"); ap.add_argument("--period", default="LAST_DAY")
    ap.add_argument("--limit", type=int, default=40); ap.add_argument("--lang", default="", help="keep one language, e.g. en")
    ap.add_argument("--out", default="clips.md")
    a = ap.parse_args()
    rows = [r for r in top_clips(a.game, a.period, a.limit) if not a.lang or r["lang"] == a.lang.lower()]
    md = [f"# Viral radar: top Twitch clips, {a.game}, {a.period} ({time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())})", "",
          "| # | views/h | views | age h | sec | lang | streamer | title | link |", "|---|---|---|---|---|---|---|---|---|"]
    for k, r in enumerate(rows, 1):
        md.append(f"| {k} | {r['views_per_h']:,} | {r['views']:,} | {r['age_h']} | {r['seconds']} | {r['lang']} | {r['streamer']} | {r['title'][:60].replace('|', '/')} | {r['url']} |")
    Path(a.out).write_text("\n".join(md) + "\n", encoding="utf-8")
    Path(a.out).with_suffix(".json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(md[:24])); print(f"... {len(rows)} clips -> {a.out}")


if __name__ == "__main__":
    main()
