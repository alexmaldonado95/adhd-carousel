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
    day, posts = metricool.top_threads_posts(day=day, limit=args.limit)

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
