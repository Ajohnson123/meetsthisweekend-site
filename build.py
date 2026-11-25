#!/usr/bin/env python3
"""Meets This Weekend site builder. Python 3, standard library only.

One table, many views. DATA lives in data/<city>/*.json, VIEW lives in this file
(small component functions, one per piece of the page), SKIN lives in assets/site.css.

    python build.py                       render the whole site into this folder
    python build.py --export --record ~/Documents/GitHub/meets-this-weekend \
                    --weekend 2026-11-27 [--city san-antonio]
                                          first export that weekend's shipped rows from
                                          the record repo, then render

STATUS VOCABULARY (record repo data/meets.csv -> site)
  The export only takes rows with in_carousel=yes AND adrian_verified=yes, so every
  exported row has been checked by Adrian. Mapping of the csv `status` column:
    csv status "moved"                      -> site "moved"       "Moved · see update"
    csv status "unconfirmed" or "candidate" -> site "unconfirmed" "Not confirmed · see post"
    anything else (shipping, verified, ...) -> site "verified"    "Checked · source"
  "checking" ("Checking") exists only for hand-written rows. The site never invents a status.

CSV COLUMNS USED (header of meets.csv, read 2026-11-24)
  id, weekend, date, day, name, organizer, handle, start, end, venue, address, type,
  source_url, status, adrian_verified, in_carousel. `type` becomes the scene chip.
  `weekend` is the Friday date; the export is keyed on it.
"""
import argparse
import csv
import html
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE_URL = "https://meetsthisweekend.com"
BRAND = "Meets This Weekend"

DAY_ORDER = ["Fri", "Sat", "Sun"]
DAY_LONG = {"Fri": "Friday", "Sat": "Saturday", "Sun": "Sunday"}
STATUS = {  # key: (label, css class)
    "verified": ("Checked · source", "status-verified"),
    "unconfirmed": ("Not confirmed · see post", "status-unconfirmed"),
    "checking": ("Checking", "status-checking"),
    "moved": ("Moved · see update", "status-moved"),
}
SCENE_LABEL = {  # csv `type` -> chip label
    "cars-and-coffee": "Cars & coffee", "car-show": "Show", "show": "Show",
    "cruise": "Cruise", "meet": "Meet", "track": "Track", "autocross": "Autocross",
    "unclear": "Other",
}
TZ_OFFSETS = {"America/Chicago": (-6, -5)}  # (standard, daylight)


# ---------------------------------------------------------------- helpers

def esc(s):
    return html.escape(str(s), quote=True)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def ig_url(handle):
    h = (handle or "").strip().lstrip("@")
    if not h or h.startswith("sample_"):
        return ""  # test mode: sample handles never link to a real profile
    return f"https://www.instagram.com/{h}/"


def is_url(s):
    return bool(s) and s.startswith(("http://", "https://"))


def t12(hhmm):
    h, m = [int(x) for x in hhmm.split(":")]
    ap = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return (f"{h12}:{m:02d}" if m else str(h12)), ap


def time_label(start, end):
    if not start:
        return "Time to be announced"
    s, sap = t12(start)
    if not end:
        return f"From {s} {sap}"
    e, eap = t12(end)
    return f"{s} to {e} {eap}" if sap == eap else f"{s} {sap} to {e} {eap}"


def expand_days(day):
    """'Sat' -> ['Sat']; 'Fri-Sun' -> ['Fri','Sat','Sun']."""
    parts = [p.strip() for p in (day or "").split("-") if p.strip()]
    if len(parts) == 2 and parts[0] in DAY_ORDER and parts[1] in DAY_ORDER:
        return DAY_ORDER[DAY_ORDER.index(parts[0]):DAY_ORDER.index(parts[1]) + 1]
    return [p for p in parts if p in DAY_ORDER]


def day_label(day):
    days = expand_days(day)
    if not days:
        return ""
    if len(days) == 1:
        return DAY_LONG[days[0]]
    return f"{DAY_LONG[days[0]]} to {DAY_LONG[days[-1]]}"


def weekend_label(friday):
    fri = date.fromisoformat(friday)
    sun = fri + timedelta(days=2)
    if fri.month == sun.month:
        return f"Friday {fri.day} to Sunday {sun.day} {fri.strftime('%B')}"
    return f"Friday {fri.day} {fri.strftime('%B')} to Sunday {sun.day} {sun.strftime('%B')}"


def nth_sunday(year, month, n):
    d = date(year, month, 1)
    d += timedelta(days=(6 - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def tz_offset(tz, d):
    if tz not in TZ_OFFSETS:
        return ""
    std, dst = TZ_OFFSETS[tz]
    off = dst if nth_sunday(d.year, 3, 2) <= d < nth_sunday(d.year, 11, 1) else std
    return f"{off:+03d}:00"


# ---------------------------------------------------------------- components
# Each one renders one piece of the page from one row.

def chip(label, group, value, pressed):
    return (f'<button type="button" class="chip" data-group="{esc(group)}" data-value="{esc(value)}" '
            f'aria-pressed="{"true" if pressed else "false"}">{esc(label)}</button>')


def meet_card(row):
    days = expand_days(row.get("day", ""))
    scene = row.get("scene", "")
    host = (row.get("handle") or row.get("organizer") or "").strip()
    host_url = ig_url(row.get("handle"))
    src = row.get("src", "")
    if not is_url(src) and not src.startswith("#"):
        src = host_url  # no source_url yet: the host's own profile (see README TODO)
    status = row.get("status", "checking")
    label, cls = STATUS.get(status, STATUS["checking"])
    badge = (f'<a class="badge {cls}" href="{esc(src)}" rel="noopener">{esc(label)}</a>' if src
             else f'<span class="badge {cls}">{esc(label)}</span>')
    if host:
        host_html = (f'<a href="{esc(host_url)}" rel="noopener">{esc(host)}</a>' if host_url else esc(host))
        hosted = f'<span class="muted">Hosted by {host_html}</span>'
    else:
        hosted = "<span></span>"
    venue = esc(row.get("venue", ""))
    if row.get("address"):
        venue += f' <span class="addr">{esc(row["address"])}</span>'
    return (
        f'<article class="meet" data-scene="{esc(scene)}" data-days="{esc(" ".join(days))}">\n'
        f'<div class="meet-top"><span class="when">{esc(day_label(row.get("day", "")))} · '
        f'{esc(time_label(row.get("start"), row.get("end")))}</span>'
        f'<span class="muted">{esc(scene)}</span></div>\n'
        f'<h3>{esc(row["name"])}</h3>\n'
        f'<p class="venue">{venue}</p>\n'
        f'<div class="meet-foot">{hosted}{badge}</div>\n'
        f'</article>')


def wall_tile(photo):
    span = photo.get("span", "")
    cls = ("tile " + span).strip()
    url = ig_url(photo["handle"]) or "#wall"
    return (f'<a class="{cls}" href="{esc(url)}" rel="noopener">'
            f'<img src="/{esc(photo["img"])}" alt="{esc(photo["alt"])}" loading="lazy">'
            f'<span class="shade" aria-hidden="true"></span>'
            f'<span class="tile-handle">{esc(photo["handle"])}</span>'
            f'<span class="tile-meet">{esc(photo["meet"])}</span></a>')


def shooter_pill(handle):
    return (f'<a class="pill" href="{esc(ig_url(handle) or "#wall")}" rel="noopener">{esc(handle)} '
            f'<span class="amber">Follow</span></a>')


def event_jsonld(row, tz):
    """schema.org Event from real fields only. Returns a dict or None."""
    if not row.get("date") or not row.get("name"):
        return None
    d = date.fromisoformat(row["date"])
    off = tz_offset(tz, d)
    days = expand_days(row.get("day", ""))
    end_date = d + timedelta(days=len(days) - 1) if len(days) > 1 else d

    def stamp(day, hhmm):
        return f"{day.isoformat()}T{hhmm}:00{off}" if hhmm else day.isoformat()

    ev = {"@context": "https://schema.org", "@type": "Event", "name": row["name"],
          "startDate": stamp(d, row.get("start"))}
    if row.get("end"):
        ev["endDate"] = stamp(end_date, row["end"])
    venue = row.get("venue", "")
    if venue and not venue.startswith("["):
        place = {"@type": "Place", "name": venue}
        if row.get("address"):
            place["address"] = row["address"]
        ev["location"] = place
    host = row.get("organizer") or ""
    if host:
        ev["organizer"] = {"@type": "Organization", "name": host}
    return ev


def head(title, desc, canonical, og_image=None, extra=""):
    og = f'<meta property="og:image" content="{esc(og_image)}">\n' if og_image else ""
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<title>{esc(title)}</title>\n<meta name="description" content="{esc(desc)}">\n'
        f'<link rel="canonical" href="{esc(canonical)}">\n'
        f'<meta property="og:title" content="{esc(title)}">\n'
        f'<meta property="og:description" content="{esc(desc)}">\n'
        f'<meta property="og:url" content="{esc(canonical)}">\n<meta property="og:type" content="website">\n'
        f'{og}<meta name="theme-color" content="#0A0A0B">\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&amp;'
        'family=Inter:wght@400;500;600&amp;display=swap" rel="stylesheet">\n'
        '<link rel="stylesheet" href="/assets/site.css">\n'
        f'{extra}</head>\n')


def header(city, multi):
    switch = '<a href="/">Change city</a>' if multi else ""
    return (
        '<header class="top">\n'
        f'<span class="brand">{esc(BRAND)} <em>{esc(city["name"])}</em></span>\n'
        '<nav aria-label="Main"><a href="#meets">This weekend</a><a href="#wall">The wall</a>'
        f'<a href="#host">List a meet</a>{switch}</nav>\n</header>\n')


# ---------------------------------------------------------------- pages

def site_settings():
    """site.json holds site-wide switches. test_mode: true = sample site (see apply_test_mode)."""
    p = ROOT / "site.json"
    return load_json(p) if p.exists() else {"test_mode": False}


def apply_test_mode(meets, photos, hero):
    """Same rows, same design, but every real handle becomes a sample one and no link
    reaches a real profile. Turn off with "test_mode": false in site.json."""
    hosts, shooters = {}, {}

    def host_alias(key):
        return hosts.setdefault(key, f"@sample_host_{len(hosts) + 1}")

    def shooter_alias(key):
        return shooters.setdefault(key, f"@sample_photographer_{len(shooters) + 1}")

    # Scrub names, places and handles: nothing real (business, venue, person) reaches the page.
    meets = [dict(m, name=f"Sample {m.get('scene') or 'Car'} Meet {i}", venue=f"[Sample venue {i}]", address="",
                  handle=host_alias(m.get("handle") or m.get("organizer")) if (m.get("handle") or m.get("organizer")) else "",
                  organizer="", src="#meets") for i, m in enumerate(meets, 1)]
    photos = [dict(p, handle=shooter_alias(p["handle"]), meet="Sample meet") for p in photos]
    hero = dict(hero, credit=shooter_alias(hero.get("credit", "")))
    return meets, photos, hero


def render_city(city, cities, out_root):
    slug = city["slug"]
    ddir = ROOT / "data" / slug
    mdata = load_json(ddir / "meets.json")
    pdata = load_json(ddir / "photos.json")
    meets = mdata["meets"]
    photos = pdata["photos"]
    hero = city["hero"]
    multi = len(cities) > 1
    test = bool(site_settings().get("test_mode"))
    mock = bool(mdata.get("_mock")) or test
    if test:
        meets, photos, hero = apply_test_mode(meets, photos, hero)

    scenes = sorted({m["scene"] for m in meets if m.get("scene")})
    days = [d for d in DAY_ORDER if any(d in expand_days(m.get("day", "")) for m in meets)]
    scene_chips = chip("All scenes", "scene", "all", True) + "".join(chip(s, "scene", s, False) for s in scenes)
    day_chips = chip("All weekend", "day", "all", True) + "".join(chip(DAY_LONG[d], "day", d, False) for d in days)
    cards = "\n".join(meet_card(m) for m in meets)
    tiles = "\n".join(wall_tile(p) for p in photos)
    shooters = "\n".join(shooter_pill(h) for h in dict.fromkeys(p["handle"] for p in photos))
    n = len(meets)
    count = f"{n} meet" if n == 1 else f"{n} meets"
    label = weekend_label(mdata["weekend"])
    url = f"{SITE_URL}/{slug}/"
    ig = f'https://www.instagram.com/{city["instagram"]}/'

    ld = [] if mock else [e for e in (event_jsonld(m, city["timezone"]) for m in meets) if e]
    ld_html = ""
    if ld:
        ld_html = ('<script type="application/ld+json">' +
                   json.dumps(ld, ensure_ascii=False).replace("</", "<\\/") + "</script>\n")

    title = f"Car meets in {city['name']} this weekend | {BRAND}"
    desc = (f"A verified list of {city['name']} car meets, posted every Thursday at 9 PM. "
            "Every meet checked against the host's own post.")
    footer_note = ("Photos on this page are stock placeholders from Wikimedia Commons "
                   "(CC BY / CC BY-SA), not the credited photographers' work." if pdata.get("_mock") else "")
    sponsor = city.get("sponsor")
    sponsor_html = f"This weekend presented by {esc(sponsor)}. Organizers never pay." if sponsor else "Organizers never pay."

    banner = ('<p class="test-banner">Sample site. Listings and handles are examples while we set up. '
              'The real list drops Thursday at 9 PM.</p>\n') if test else ""
    body = (
        '<body>\n<div class="page">\n' + banner + header(city, multi) +
        '<section class="wrap">\n<div class="hero">\n'
        f'<img src="/{esc(hero["img"])}" alt="{esc(hero["alt"])}">\n<div class="hero-shade" aria-hidden="true"></div>\n'
        '<div class="hero-copy"><div class="hero-text">\n'
        f'<p class="eyebrow">{esc(label)}</p>\n'
        '<h1>Where the cars are <em>this weekend.</em></h1>\n</div>\n'
        f'<a class="hero-credit" href="{esc(ig_url(hero["credit"]) or "#")}" rel="noopener">Photo: {esc(hero["credit"])} · Follow</a>\n'
        '</div>\n</div>\n</section>\n'
        '<section id="meets" class="wrap meets-head">\n<div class="stack">\n<h2>The weekend</h2>\n'
        f'<p class="muted"><span id="count">{esc(count)}</span>. Each one checked Thursday night against the host\'s own post. Tap "Checked" to see it.</p>\n</div>\n'
        '<div class="filters">\n'
        f'<div class="chips" role="group" aria-label="Filter by scene">{scene_chips}</div>\n'
        f'<div class="chips" role="group" aria-label="Filter by day">{day_chips}</div>\n</div>\n</section>\n'
        f'<section class="wrap meets-list"><div class="grid" id="meet-grid">\n{cards}\n</div>\n'
        '<p id="empty" class="muted" hidden>No meets match that filter.</p></section>\n'
        '<section id="wall" class="wall"><div class="wrap wall-inner">\n'
        '<div class="wall-head"><h2>Last weekend, <em>as they saw it.</em></h2>\n'
        '<p class="muted">Every frame belongs to the photographer who shot it. Tap a photo to follow them.</p></div>\n'
        f'<div class="mosaic">\n{tiles}\n</div>\n'
        f'<div class="follow"><p class="follow-title">Follow the people who shot it.</p><div class="pills">\n{shooters}\n</div></div>\n'
        '</div></section>\n'
        '<section id="host" class="wrap host">\n<h2>Hosting a meet?</h2>\n<div class="stack">\n'
        '<p class="lead">Send the flyer. It goes on Thursday\'s list, free, with your name on it.</p>\n'
        f'<a class="cta" href="{esc(ig)}" rel="noopener">DM FLYER to @{esc(city["instagram"])}</a>\n</div>\n</section>\n'
        '<footer><div class="wrap foot">\n'
        f'<span>{sponsor_html}</span><span>Respect the spot. No takeovers.</span>\n'
        + (f'<span class="fine">{esc(footer_note)}</span>\n' if footer_note else "") +
        '</div></footer>\n</div>\n<script src="/assets/site.js"></script>\n</body>\n</html>\n')

    noindex = '<meta name="robots" content="noindex">\n' if test else ""
    page = head(title, desc, url, f"{SITE_URL}/{hero['img']}", noindex + ld_html) + body
    write(out_root / slug / "index.html", page)


def render_redirect(target_path, canonical_path, name):
    target = f"{SITE_URL}{canonical_path}"
    page = (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<title>{esc(BRAND)}</title>\n'
        f'<link rel="canonical" href="{esc(target)}">\n'
        f'<meta http-equiv="refresh" content="0; url={esc(canonical_path)}">\n'
        '<meta name="robots" content="noindex">\n</head>\n'
        f'<body style="background:#0A0A0B;color:#EDEBE6;font-family:system-ui,sans-serif;padding:24px">\n'
        f'<p>Going to <a style="color:#E8B04B" href="{esc(canonical_path)}">{esc(name)}</a>.</p>\n'
        f'<script>location.replace({json.dumps(canonical_path)});</script>\n</body>\n</html>\n')
    write(target_path, page)


def render_picker(cities, out_root):
    cards = "\n".join(
        f'<a class="city-card" href="/{esc(c["slug"])}/"><span>{esc(c["name"])}</span>'
        f'<span class="amber">See this weekend</span></a>' for c in cities)
    body = ('<body>\n<div class="page">\n<header class="top"><span class="brand">' + esc(BRAND) + '</span></header>\n'
            '<section class="wrap picker"><p class="eyebrow">Pick your city</p>\n'
            '<h1>Where are you <em>looking?</em></h1>\n'
            f'<div class="city-grid">\n{cards}\n</div></section>\n</div>\n</body>\n</html>\n')
    page = head(f"{BRAND} | pick your city", "A verified list of car meets, every Thursday, for each city we cover.",
                f"{SITE_URL}/") + body
    write(out_root / "index.html", page)


def render_404(cities, out_root):
    links = " ".join(f'<a href="/{esc(c["slug"])}/">{esc(c["name"])}</a>' for c in cities)
    body = ('<body>\n<div class="page">\n<header class="top"><span class="brand">' + esc(BRAND) + '</span></header>\n'
            '<section class="wrap picker"><p class="eyebrow">404</p>\n<h1>Nothing parked <em>here.</em></h1>\n'
            f'<p class="lead">Try a city page: {links}</p></section>\n</div>\n</body>\n</html>\n')
    write(out_root / "404.html", head(f"Not found | {BRAND}", "Page not found.", f"{SITE_URL}/404.html") + body)


def render_all(cities):
    out = ROOT
    for c in cities:
        render_city(c, cities, out)
        for alias in c.get("aliases", []):
            render_redirect(out / alias / "index.html", f"/{c['slug']}/", c["name"])
    if len(cities) == 1:
        c = cities[0]
        render_redirect(out / "index.html", f"/{c['slug']}/", c["name"])
    else:
        render_picker(cities, out)
    render_404(cities, out)
    write(out / "CNAME", "meetsthisweekend.com\n")
    write(out / ".nojekyll", "")


# ---------------------------------------------------------------- export

def export_weekend(record, weekend, city_slug):
    csv_path = Path(record).expanduser() / "data" / "meets.csv"
    with open(csv_path, encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f)
                if r["weekend"] == weekend and r["in_carousel"] == "yes" and r["adrian_verified"] == "yes"]
    out = []
    for r in rows:
        st = r["status"]
        status = "moved" if st == "moved" else ("unconfirmed" if st in ("unconfirmed", "candidate") else "verified")
        out.append({
            "id": r["id"], "name": r["name"], "date": r["date"], "day": r["day"],
            "start": r["start"], "end": r["end"], "venue": r["venue"], "address": r["address"],
            "organizer": r["organizer"], "handle": r["handle"],
            "scene": SCENE_LABEL.get(r["type"], r["type"].replace("-", " ").title() if r["type"] else ""),
            "status": status,
            "src": r["source_url"] if is_url(r["source_url"]) else "",
        })
    out.sort(key=lambda m: (m["date"], m["start"] or "99"))
    if not out:  # never overwrite the data file with an empty weekend
        return 0
    target = ROOT / "data" / city_slug / "meets.json"
    write(target, json.dumps({"weekend": weekend, "meets": out}, indent=2, ensure_ascii=False) + "\n")
    print(f"exported {len(out)} meets for {weekend} -> {target}")
    for m in out:
        print(f"  {m['date']} {m['start']:>5} {m['name']}")
    return len(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--export", action="store_true", help="export shipped rows from the record repo first")
    ap.add_argument("--record", help="path to the record repo (meets-this-weekend)")
    ap.add_argument("--weekend", help="the Friday, YYYY-MM-DD")
    ap.add_argument("--city", default="san-antonio")
    args = ap.parse_args()
    cities = load_json(ROOT / "cities.json")
    if args.export:
        if not (args.record and args.weekend and re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.weekend)):
            sys.exit("--export needs --record <path> and --weekend YYYY-MM-DD")
        if export_weekend(args.record, args.weekend, args.city) == 0:
            sys.exit("no rows with in_carousel=yes and adrian_verified=yes for that weekend; nothing rendered")
    render_all(cities)
    print("built:", ", ".join(sorted(str(p.relative_to(ROOT)) for p in ROOT.rglob("index.html"))))


if __name__ == "__main__":
    main()
