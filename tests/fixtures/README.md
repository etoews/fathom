# Test fixtures

Two trees under `tests/fixtures/`:

- `videos/` — public-domain / CC0 clips, committed to the repo. Anyone cloning the repo gets these.
- `private/` — your own dive footage. Gitignored. Drop clips here for manual visual validation; tests should treat its presence as optional.

## What each public fixture needs to be

Each clip needs to be a real underwater video (not synthetic), 30-60 seconds, under ~10 MB. Resolution doesn't matter much — 720p is fine. The point of these fixtures is to validate the heuristic on representative content, not to look pretty.

| File | What it must contain | What it validates |
|---|---|---|
| `empty-water.mp4` | Mostly empty blue/green water. Camera slowly drifting. Optional: faint distant silhouettes. Should score *low* on the heuristic. | The heuristic rejects boring frames. Used by event-clustering tests to verify "no events above floor" → 0 exports. |
| `fish-swim-by.mp4` | One or more fish (or other marine life) appearing distinctly. Should produce 1-3 Events. | The heuristic finds Subjects. Used by scoring tests to verify Score is higher than `empty-water.mp4`. |
| `multiple-events.mp4` | Several distinct wildlife moments separated by spans of empty water. Should produce 4-6 Events. | Event clustering. Used to verify "events are correctly separated", "up to 6 cap is respected", "ranking-by-best-frame works". |
| `known-exif.mp4` | Any short clip with intact EXIF metadata: `DateTimeOriginal`, ideally `GPS*`, `Make`, `Model`. Easiest source: a 5-second clip from your own camera with GPS on (drop in `private/` is fine too, but a committed one means CI can verify EXIF copy works). | The exiftool subprocess wiring. Used by EXIF tests to assert tags propagate from video to exported JPG. |
| `corrupt.mp4` | A non-video file with `.mp4` extension. Already committed; created by `echo "not a video" > corrupt.mp4`. | Failure-handling. Used by tests to verify ffmpeg errors are caught, logged, and don't crash the run. |

## Where to get the public clips

**Pexels** (CC0, no attribution required, dive cameras of real divers):
- https://www.pexels.com/search/videos/scuba%20diving/
- https://www.pexels.com/search/videos/underwater/

Navigate in a browser, find a clip matching the spec above, click "Free download", pick the smallest resolution that's still visually clear (typically 720p or 1080p), save to `tests/fixtures/videos/<name>.mp4`. Cloudflare blocks automated curl, so this is a manual step.

**NOAA Ocean Exploration** (public domain, deep-sea ROV footage):
- https://oceanexplorer.noaa.gov/video_playlist.html
- https://www.ncei.noaa.gov/access/ocean-exploration/video/

ROV footage is excellent for `multiple-events.mp4` because deep-sea dives have long stretches of empty water punctuated by genuine wildlife encounters. Download links are on each clip's detail page; the H.264 .mp4 "low resolution" version is right for fixtures.

**Your own camera** (best for `known-exif.mp4`):
A 5-second clip from your own GoPro / Olympus TG / Paralenz with GPS enabled. Strip identifying location if you're paranoid (exiftool can edit GPS), but for a dive site you've posted publicly elsewhere it's probably fine.

## Trimming to size

If a clip you want is longer than 60s or bigger than ~10 MB:

```sh
ffmpeg -i input.mp4 -ss 00:00:05 -t 30 -c copy fixtures/videos/fish-swim-by.mp4
```

`-c copy` skips re-encoding so EXIF stays intact and the trim is fast. `-ss` is the start time, `-t` is the duration.

## After you add a clip

Bump this README with the source URL and the credit (e.g. NOAA Ocean Exploration / public domain). Keeps the fixtures from becoming mystery files.
