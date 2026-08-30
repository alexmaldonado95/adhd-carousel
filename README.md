# adhd-carousel

Daily Instagram carousel for **@the.alexmaldonado** (ADHD brand), built from the
previous day's Threads posts and scheduled through Metricool.

## How it works

1. `scripts/build.py` pulls the previous Pacific day's Threads posts from
   Metricool analytics, ranks them by views, and renders 1080x1350 slides
   (cover + up to 6 post cards + CTA) with headless Chromium.
2. The workflow commits `slides/<date>/*.jpg` to this repo and pushes.
3. `scripts/schedule_post.py` polls every slide URL on
   `raw.githubusercontent.com` until it returns a real HTTP 200, then schedules
   the carousel to Metricool.

## Why the repo must stay public

The Metricool API has **no media-upload endpoint**. Media must be supplied as
public, non-expiring URLs, which Metricool fetches anonymously. A private repo
makes every `raw.githubusercontent.com` URL 404 and the post publishes with
missing images — silently. Do not flip this repo to private.

`saveExternalMediaFiles: true` in the payload makes Metricool copy the images to
its own CDN at schedule time, so the post survives later repo changes. Keep it.

## Running it

Manual draft run (nothing publishes):

```bash
gh workflow run "Daily ADHD carousel" -f draft=true
```

The scheduled run is `0 15 * * *` UTC — 8am Pacific in summer, 7am in winter.

## Draft vs live

Every path defaults to **draft**. It publishes for real only when:

- a manual run passes `-f draft=false`, or
- the repo variable `AUTOPUBLISH` is set to `true` (this is the switch for the
  daily cron): `gh variable set AUTOPUBLISH --body true`

## Configuration

| Name | Kind | Purpose |
|---|---|---|
| `METRICOOL_TOKEN` | secret | Metricool API key (`X-Mc-Auth`) |
| `AUTOPUBLISH` | variable | `true` lets the cron publish live; anything else = draft |

Brand: blogId `5333281`, userId `2761513`, timezone `America/Los_Angeles`.

## Gotchas encoded in the code

- Metricool's Threads analytics returns `publishedDate` in the **account's
  reporting timezone (`Europe/Madrid`)**, not UTC and not Pacific. `metricool.py`
  converts it. Rendering the raw string mislabels roughly a third of the slides.
- `providers` entries are objects (`{"network": "instagram"}`), not strings.
- Instagram carousels cap at 10 images; `schedule_post.py` trims.
- A day with fewer than 3 usable posts fails the build instead of shipping a
  thin carousel.

## Slide design

The palette and layout in `scripts/brand.py` are **approved (2026-08-30)**. Brand
5333281 has no design system in Metricool to inherit from, so this file is the
ADHD visual identity. Don't restyle it as a side effect of another change.
