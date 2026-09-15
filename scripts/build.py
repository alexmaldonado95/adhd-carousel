"""Fetch yesterday's Threads posts, render the carousel, write a manifest.

    python scripts/build.py [--day YYYY-MM-DD] [--limit 6] [--outdir slides]

Writes slides/<pacific-date>/slide-NN.jpg plus manifest.json next to them.
Exits non-zero with a clear reason if there is nothing worth posting — a silent
empty carousel is worse than a failed run.
"""

import argparse
import json
import pathlib
import sys
from datetime import date, datetime

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import ledger
import metricool
import render
from brand import HANDLE

MIN_POSTS = 3  # fewer than this and the "ranked countdown" framing falls apart


def caption(day, posts):
    top = posts[0]
    lines = [
        f"Yesterday on Threads, ranked by views.",
        "",
        f'"{top["text"]}" took the top spot with {top["views"]:,} views.',
        "",
        f"Swipe for the full countdown. I post these every day — @{HANDLE}",
        "",
        "#ADHD #ADHDawareness #Neurodivergent #ADHDinAdults #ADHDbrain "
        "#MentalHealth #ADHDsupport #ActuallyADHD",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", help="Pacific date YYYY-MM-DD (default: yesterday)")
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--outdir", default="slides")
    args = ap.parse_args()

    day = date.fromisoformat(args.day) if args.day else None
    # Over-fetch so the ledger can veto some without starving the countdown,
    # then trim back to --limit after the filter.
    day, posts = metricool.top_threads_posts(day=day, limit=args.limit * 3)

    used_keys, _, _ = ledger.load()
    ledger.check_key_drift(used_keys)
    if used_keys:
        fresh, reused = [], []
        for p in posts:
            (reused if ledger.is_used(p["text"], used_keys) else fresh).append(p)
        for p in reused:
            print(f"[build] already used by the 6pm carousel: {p['text'][:60]!r}")

        # Both pipelines draw on the same ~6 posts a day while the 6pm one alone
        # consumes ~12, so on most days strict dedupe leaves too little to build
        # a countdown from. Failing the run over that would just trade duplicate
        # posts for no post at all, so top back up from the highest-ranked
        # reused ones and say plainly that is what happened.
        posts = fresh
        if len(posts) < MIN_POSTS and reused:
            topup = reused[:MIN_POSTS - len(posts)]
            print(f"[build] only {len(fresh)} unused post(s) - topping up with "
                  f"{len(topup)} the 6pm carousel has already run. They WILL be "
                  f"duplicates. Both pipelines are competing for one pool.")
            posts = posts + topup
    posts = posts[:args.limit]

    print(f"[build] Pacific day {day} — {len(posts)} usable post(s)")
    for i, p in enumerate(posts, 1):
        print(f"  {i}. {p['views']:>6} views  {p['pacific']:%H:%M}  {p['text'][:64]!r}")

    if len(posts) < MIN_POSTS:
        sys.exit(f"[build] only {len(posts)} post(s) for {day}; need {MIN_POSTS}. "
                 "Nothing rendered, nothing scheduled.")

    day_label = day.strftime("%A, %b %-d, %Y")
    total = sum(1 for _ in posts)
    n = len(posts) + 2  # cover + posts + cta

    pages = [render.cover_slide(day_label, total, posts[0]["views"], 0, n)]
    pages += [render.post_slide(r, p, r, n) for r, p in enumerate(posts, 1)]
    pages.append(render.cta_slide(n - 1, n))

    outdir = pathlib.Path(args.outdir) / day.isoformat()
    written = render.render_all(pages, outdir)
    print(f"[build] rendered {len(written)} slides -> {outdir}")

    manifest = {
        "day": day.isoformat(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "handle": HANDLE,
        "slide_count": len(written),
        "slides": [p.name for p in written],
        "caption": caption(day, posts),
        "posts": [{
            "rank": i,
            "views": p["views"], "likes": p["likes"], "replies": p["replies"],
            "permalink": p["permalink"],
            "published_pacific": p["pacific"].isoformat(),
            "text": p["text"],
        } for i, p in enumerate(posts, 1)],
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"[build] manifest -> {outdir/'manifest.json'}")
    print("BUILD_DAY=" + day.isoformat())


if __name__ == "__main__":
    main()
