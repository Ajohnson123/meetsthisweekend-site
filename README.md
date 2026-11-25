# meetsthisweekend-site

The public website for Meets This Weekend (meetsthisweekend.com): one page per city, listing the car meets that shipped in Thursday's Instagram post.

## The three layers

The table is the source of truth. Every surface (the Instagram carousel, the phone page, this website) is a different view of the same rows. Three things change independently:

| Layer | What it is | Where it lives |
|---|---|---|
| DATA | The rows: meets, photos, cities | `data/<city>/meets.json`, `data/<city>/photos.json`, `cities.json` |
| VIEW | Which rows, in what order, which components | `build.py` (small functions: `meet_card`, `wall_tile`, `chip`, `shooter_pill`, `event_jsonld`, one per piece of page) |
| SKIN | Colors, type, spacing | `assets/site.css` (one file) |

`assets/site.js` only toggles the scene and day filter chips. No framework, no npm, no build tools beyond Python 3 (standard library only). The output is plain static HTML, which is what Google reads best.

Private things (notes, sources, people, unverified rows) stay in the private record repo `meets-this-weekend`. This repo is public, so only rows that shipped (`in_carousel=yes` and `adrian_verified=yes`) are ever exported into it.

## Build

```
python build.py
```

Renders from `cities.json` and `data/` into the repo root: `san-antonio/index.html`, `sa/index.html` (redirect), `index.html` (redirect while there is one city, a city picker when there are two or more), `404.html`, plus `CNAME` and `.nojekyll`. Never hand-edit the built HTML. Edit the data or `build.py`, then rebuild.

## The Thursday flow

1. The meets are verified and the final slides render (`mtw-setup ship`).
2. Export the shipped rows for that weekend and rebuild:
   ```
   python build.py --export --record ~/Documents/GitHub/meets-this-weekend --weekend YYYY-MM-DD
   ```
   `YYYY-MM-DD` is the Friday. It reads the record repo's `data/meets.csv` and keeps only that weekend's rows with `in_carousel=yes` AND `adrian_verified=yes`. It prints the list so it can be checked against the shipping rows.
3. Look at `san-antonio/index.html` (or serve it: `python -m http.server 8000 --bind 127.0.0.1`).
4. Commit and push this repo. GitHub Pages publishes it. This happens under the same yes as the slides.

The seed file `data/san-antonio/meets.json` carries `"_mock": true` (eight placeholder meets from the design). The first export overwrites it. While `_mock` is true, no Event structured data is written, so Google never sees placeholder meets.

### Column mapping (record repo `data/meets.csv`)

`name`, `date`, `day`, `start`, `end`, `venue`, `address`, `organizer`, `handle`, `type` (becomes the scene chip), `source_url`, `status`. The status mapping is documented at the top of `build.py`.

### TODO: `source_url` is not always a real post

Each meet's "Checked · source" link should go to the host's own post. `meets.csv` already has a `source_url` column, but many rows hold an aggregator page (getoutgarage, happeningnext) or a note like `instagram (found by Adrian)`. The export keeps only values that are real http(s) links and falls back to the host's Instagram profile (from `handle`). The real fix is a dedicated column in `meets.csv` for the host's original post, filled during Thursday verification (this repo does not edit `meets.csv`). If there is no link and no handle, the status shows as plain text.

Also: `meets.csv` has no site-city column, so the export assumes every row belongs to the city passed with `--city` (default `san-antonio`). Add a `market` column before the second city.

## Test mode

`site.json` holds `{"test_mode": true}`. While it is true, the build makes a sample site: every host and photographer handle is replaced with `@sample_host_N` / `@sample_photographer_N` (the hero credit too), no link goes to a real Instagram profile (only MTW's own `@meetsthisweekendsa` account stays), every "Checked" link points back to the meet list, a "Sample site" banner shows at the top, `noindex` keeps search engines out, and no Event structured data is written.

Note: the raw files in `data/` still hold the original mock handles, so they are visible in the public repo's source even though the pages do not show them. Turn it off by setting `test_mode` to `false` in `site.json` and rebuilding. Do that only once a real Thursday export has replaced the mock meets.

## Add a city

1. Add an entry to `cities.json`: `slug`, `name`, `aliases`, `timezone`, `instagram`, `hero` (`img`, `alt`, `credit`).
2. Add `data/<slug>/meets.json` and `data/<slug>/photos.json`, and the hero image under `assets/img/`.
3. `python build.py`. With two or more cities, `/` automatically becomes the "pick your city" page and each city page gets a "Change city" link. No code change.

## Photos

The photos on the wall and the hero are stock placeholders from Wikimedia Commons (CC BY / CC BY-SA / CC0), not the credited photographers' work. Their license, author and source page are in `data/san-antonio/photos.json` and `cities.json`. Real photos need the photographer's yes first (open question, tracked in the vault).

## GitHub Pages and GoDaddy DNS

1. On GitHub, create the public repo `Ajohnson123/meetsthisweekend-site` and push this folder to `main`.
2. In GitHub, go to Settings > Pages (profile-level: Settings > Pages > Verified domains), add `meetsthisweekend.com`, and copy the verification TXT record it shows.
3. In GoDaddy (DNS for meetsthisweekend.com):
   - Delete the "Parked" A record on `@` and any conflicting `www` record.
   - Add four A records on `@` (apex): `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`.
   - Add a CNAME: `www` -> `ajohnson123.github.io`.
   - Add the GitHub domain-verification TXT record exactly as GitHub shows it.
4. Repo Settings > Pages: source = deploy from branch `main`, folder `/ (root)`. Set custom domain to `meetsthisweekend.com` (the `CNAME` file in this repo already says so).
5. Wait for DNS and the certificate, then tick Enforce HTTPS.

Check: `https://meetsthisweekend.com/` should land on `/san-antonio/`, and `/sa/` should too.
