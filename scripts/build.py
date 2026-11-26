#!/usr/bin/env python3
"""Paradise.mx static site generator.

Renders every page from templates/ + data/ into the repository root so GitHub Pages
can serve it straight from the main branch. Run:  python3 scripts/build.py
"""
import datetime as dt
import hashlib
import json
import math
import os
import random
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TPL = ROOT / "templates"
BASE_URL = "https://paradise.mx"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTHS_LONG = ["January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December"]
REGIONS = ["Caribbean", "Yucatán", "Pacific", "Oaxaca coast", "Baja", "Highlands"]
REGION_LABEL = {"Caribbean": "Mexican Caribbean", "Yucatán": "Yucatán & Campeche", "Pacific": "Banderas Bay & Riviera Nayarit",
                "Oaxaca coast": "Oaxaca coast", "Baja": "Baja & Sea of Cortez", "Highlands": "Highland cities"}
VIBES = ["beach", "island", "cenotes", "reef", "diving", "surf", "wildlife", "family", "romance", "luxury", "nightlife",
         "culture", "food", "wellness", "adventure", "quiet", "budget", "golf", "wine", "retire"]


def load(name, default=None):
    p = DATA / name
    if not p.exists():
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


DESTS = load("destinations.json")
CLIMATE = load("climate.json")
NORMALS = load("normals.json", {}) or {}
NEWS = load("news.json", {"updated": None, "items": []})
VIDEOS = load("videos.json", {"updated": None, "items": []})
FX = load("fx.json", {})
BY_SLUG = {d["slug"]: d for d in DESTS}


# ---------------------------------------------------------------- scoring (mirrors assets/js/site.js)
def beachy(d):
    return d["type"] in ("beach", "island", "lagoon")


def month_data(d, m):
    z = CLIMATE["zones"][d["zone"]]
    n = NORMALS.get(d["slug"]) or {}
    hi = n.get("hi", z["hi"])[m] if n.get("hi") else z["hi"][m]
    rain = n.get("rain", z["rain"])[m] if n.get("rain") else z["rain"][m]
    sea = z["sea"][m]
    sarg = CLIMATE["sargassum"]["levels"][m] * d.get("sargassum", 0)
    hur = CLIMATE["hurricane"][z["basin"]][m]
    ev = [e for e in d.get("events", []) if (m + 1) in CLIMATE["events"][e]["months"]]
    return {"hi": hi, "rain": rain, "sea": sea, "sarg": sarg, "hur": hur, "ev": ev}


def clamp(v, a, b):
    return max(a, min(b, v))


def js_round(x):
    return int(math.floor(x + 0.5))


def score(d, m):
    x = month_data(d, m)
    b = beachy(d)
    if b:
        air = 100 - 6 * max(0, 27 - x["hi"]) - 7 * max(0, x["hi"] - 31)
    else:
        air = 100 - 6 * max(0, 21 - x["hi"]) - 7 * max(0, x["hi"] - 27)
    air = clamp(air, 0, 100)
    rain = clamp(100 - 4.5 * x["rain"], 0, 100)
    if x["sea"] is None:
        sea = 70
    else:
        sea = 100 if x["sea"] >= 27 else clamp(100 - (27 - x["sea"]) * 9, 0, 100)
    base = air * 0.38 + rain * 0.34 + sea * 0.28 if b else air * 0.5 + rain * 0.5
    pen = 6 * x["sarg"] + (4 if b else 2) * x["hur"]
    bonus = min(8, 4 * len(x["ev"]))
    return int(clamp(js_round(base - pen + bonus), 0, 100))


def score_color(s):
    if s >= 85: return ("#0E4D5C", "#fff")
    if s >= 75: return ("#19B5A6", "#04302B")
    if s >= 65: return ("#9FE0D7", "#0E4D5C")
    if s >= 55: return ("#FFE3A3", "#5A3B00")
    return ("#F6D3DC", "#7A1C3A")


def month_ranges(ms):
    """[0,1,2,10,11] -> 'November to March' style text (handles wrap)."""
    if not ms:
        return ""
    s = sorted(set(ms))
    if len(s) == 12:
        return "all year"
    runs, cur = [], [s[0]]
    for a in s[1:]:
        if a == cur[-1] + 1:
            cur.append(a)
        else:
            runs.append(cur); cur = [a]
    runs.append(cur)
    if len(runs) > 1 and runs[0][0] == 0 and runs[-1][-1] == 11:
        runs[0] = runs[-1] + runs[0]; runs.pop()
    out = []
    for r in runs:
        out.append(MONTHS_LONG[r[0]] if len(r) == 1 else f"{MONTHS_LONG[r[0]]} to {MONTHS_LONG[r[-1]]}")
    return " and ".join(out) if len(out) <= 2 else ", ".join(out[:-1]) + " and " + out[-1]


def enrich(d):
    sc = [score(d, m) for m in range(12)]
    top = max(sc)
    best = [m for m, s in enumerate(sc) if s >= top - 5]
    worst = [m for m, s in enumerate(sc) if s <= min(sc) + 4]
    md = [month_data(d, m) for m in range(12)]
    e = dict(d)
    e.update({
        "scores": sc, "best": best, "best_text": month_ranges(best), "worst_text": month_ranges(worst),
        "md": md, "top": top, "colors": [score_color(s) for s in sc],
        "budget_str": "$" * d["budget"],
        "region_label": REGION_LABEL[d["region"]],
        "zone_label": CLIMATE["zones"][d["zone"]]["label"],
        "basin": CLIMATE["zones"][d["zone"]]["basin"],
        "events_full": [dict(CLIMATE["events"][x], id=x, months_text=month_ranges([mm - 1 for mm in CLIMATE["events"][x]["months"]])) for x in d.get("events", [])],
        "sarg_months": month_ranges([m for m in range(12) if CLIMATE["sargassum"]["levels"][m] * d.get("sargassum", 0) >= 1.2]),
        "beachy": beachy(d),
        "sea_range": None,
    })
    seas = [x for x in CLIMATE["zones"][d["zone"]]["sea"] if x is not None]
    if seas and beachy(d):
        e["sea_range"] = (min(seas), max(seas))
    his = [x["hi"] for x in md]
    e["hi_range"] = (min(his), max(his))
    e["wettest"] = month_ranges([m for m in range(12) if md[m]["rain"] >= 10])
    return e


ENRICHED = [enrich(d) for d in DESTS]
EBY = {d["slug"]: d for d in ENRICHED}


# ---------------------------------------------------------------- original SVG postcards
def _rng(slug):
    return random.Random(int(hashlib.md5(slug.encode()).hexdigest()[:8], 16))


SKIES = [("#FFD6A5", "#FF8FA3", "#FFF1D2"), ("#8EE3F5", "#E7FBFF", "#FFF6CC"), ("#FF9E6D", "#FFD166", "#FFF4D6"),
         ("#5B7FD6", "#F7A6C1", "#FFE9B0"), ("#B8F0E6", "#FFFFFF", "#FFF2C2"), ("#F28C8C", "#FFC59E", "#FFF0D9")]


def palm(x, y, s, flip, color="#0E3A40"):
    k = -1 if flip else 1
    trunk = f'<path d="M{x} {y} q{12*k*s} {-60*s} {4*k*s} {-120*s}" stroke="{color}" stroke-width="{7*s:.1f}" fill="none" stroke-linecap="round"/>'
    tx, ty = x + 4 * k * s, y - 120 * s
    fronds = ""
    for ang, ln in ((-160, 62), (-120, 58), (-70, 60), (-25, 56), (15, 46), (-200, 44)):
        a = math.radians(ang if not flip else 180 - ang)
        ex, ey = tx + math.cos(a) * ln * s, ty + math.sin(a) * ln * s
        cx, cy = tx + math.cos(a) * ln * s * 0.5, ty + math.sin(a) * ln * s * 0.5 - 18 * s
        fronds += f'<path d="M{tx:.1f} {ty:.1f} Q{cx:.1f} {cy:.1f} {ex:.1f} {ey:.1f}" stroke="{color}" stroke-width="{9*s:.1f}" fill="none" stroke-linecap="round"/>'
    return trunk + fronds


def cactus(x, y, s, color="#1E5B3A"):
    return (f'<g fill="{color}"><rect x="{x-7*s:.1f}" y="{y-90*s:.1f}" width="{14*s:.1f}" height="{90*s:.1f}" rx="{7*s:.1f}"/>'
            f'<rect x="{x-27*s:.1f}" y="{y-62*s:.1f}" width="{11*s:.1f}" height="{36*s:.1f}" rx="{5.5*s:.1f}"/>'
            f'<rect x="{x-27*s:.1f}" y="{y-34*s:.1f}" width="{24*s:.1f}" height="{10*s:.1f}" rx="5"/>'
            f'<rect x="{x+16*s:.1f}" y="{y-72*s:.1f}" width="{11*s:.1f}" height="{40*s:.1f}" rx="{5.5*s:.1f}"/>'
            f'<rect x="{x+3*s:.1f}" y="{y-40*s:.1f}" width="{24*s:.1f}" height="{10*s:.1f}" rx="5"/></g>')


def pyramid(x, y, s, color="#7A5C3E"):
    pts, w, h = [], 120 * s, 0
    out = ""
    for i in range(5):
        ww = w - i * 22 * s
        out += f'<rect x="{x-ww/2:.1f}" y="{y-(i+1)*14*s:.1f}" width="{ww:.1f}" height="{14*s:.1f}" fill="{color}" opacity="{0.92 - i*0.04:.2f}"/>'
    out += f'<rect x="{x-14*s:.1f}" y="{y-92*s:.1f}" width="{28*s:.1f}" height="{22*s:.1f}" fill="{color}"/>'
    out += f'<rect x="{x-6*s:.1f}" y="{y-70*s:.1f}" width="{12*s:.1f}" height="{70*s:.1f}" fill="#5A4129" opacity=".55"/>'
    return out


def church(x, y, s, color="#C2255C"):
    return (f'<g fill="{color}"><rect x="{x-40*s:.1f}" y="{y-60*s:.1f}" width="{80*s:.1f}" height="{60*s:.1f}"/>'
            f'<rect x="{x-58*s:.1f}" y="{y-120*s:.1f}" width="{26*s:.1f}" height="{120*s:.1f}"/>'
            f'<path d="M{x-58*s:.1f} {y-120*s:.1f} L{x-45*s:.1f} {y-150*s:.1f} L{x-32*s:.1f} {y-120*s:.1f}Z"/>'
            f'<path d="M{x-34*s:.1f} {y-60*s:.1f} A{34*s:.1f} {34*s:.1f} 0 0 1 {x+34*s:.1f} {y-60*s:.1f}Z"/>'
            f'<rect x="{x-3*s:.1f}" y="{y-108*s:.1f}" width="{6*s:.1f}" height="{16*s:.1f}"/>'
            f'<rect x="{x-9*s:.1f}" y="{y-103*s:.1f}" width="{18*s:.1f}" height="{5*s:.1f}"/></g>'
            f'<rect x="{x-10*s:.1f}" y="{y-30*s:.1f}" width="{20*s:.1f}" height="{30*s:.1f}" rx="{10*s:.1f}" fill="#fff" opacity=".35"/>')


def postcard(d):
    r = _rng(d["slug"])
    W, H = 400, 300
    s1, s2, sun = SKIES[r.randrange(len(SKIES))]
    sx, sy, sr = r.randint(70, 330), r.randint(55, 110), r.randint(26, 40)
    horizon = r.randint(150, 175)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="Illustration of {d["name"]}">',
             f'<defs><linearGradient id="sk" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{s1}"/><stop offset="1" stop-color="{s2}"/></linearGradient>'
             f'<linearGradient id="se" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#19B5A6"/><stop offset="1" stop-color="#0E4D5C"/></linearGradient>'
             f'<linearGradient id="la" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#6FE3D6"/><stop offset=".5" stop-color="#2BB9E0"/><stop offset="1" stop-color="#1B6FA8"/></linearGradient></defs>',
             f'<rect width="{W}" height="{H}" fill="url(#sk)"/>',
             f'<circle cx="{sx}" cy="{sy}" r="{sr}" fill="{sun}"/><circle cx="{sx}" cy="{sy}" r="{sr+14}" fill="{sun}" opacity=".25"/>']
    region, typ = d["region"], d["type"]
    # background relief
    if region in ("Pacific", "Oaxaca coast", "Highlands", "Baja"):
        col = "#2F6B5E" if region in ("Pacific", "Oaxaca coast") else ("#8C6A4F" if region == "Baja" else "#4E6E7A")
        pts = f"0,{horizon} "
        x = 0
        while x <= W:
            pts += f"{x},{horizon - r.randint(25, 80)} "
            x += r.randint(40, 80)
        pts += f"{W},{horizon} {W},{H} 0,{H}"
        parts.append(f'<polygon points="{pts}" fill="{col}" opacity=".55"/>')
    if typ in ("beach", "island", "lagoon"):
        fill = "url(#la)" if typ == "lagoon" else "url(#se)"
        parts.append(f'<rect y="{horizon}" width="{W}" height="{H-horizon}" fill="{fill}"/>')
        for i in range(4):
            yy = horizon + 18 + i * 22 + r.randint(-4, 4)
            x0 = r.randint(10, 200)
            parts.append(f'<path d="M{x0} {yy} q15 -6 30 0 t30 0" stroke="#fff" stroke-opacity=".45" stroke-width="2" fill="none"/>')
        if typ == "island":
            ix = r.randint(230, 330)
            parts.append(f'<ellipse cx="{ix}" cy="{horizon+4}" rx="{r.randint(40,70)}" ry="12" fill="#1E6B4F"/>')
        # sand
        sand_y = H - r.randint(55, 75)
        parts.append(f'<path d="M0 {sand_y} Q{W*0.45:.0f} {sand_y-30} {W} {sand_y+10} L{W} {H} L0 {H}Z" fill="#F7E3B5"/>')
        ground = sand_y + 8
    else:
        parts.append(f'<rect y="{horizon}" width="{W}" height="{H-horizon}" fill="#E9D7B8"/>')
        parts.append(f'<rect y="{horizon}" width="{W}" height="12" fill="#D8C29A"/>')
        ground = H - 40
    # foreground icon by character
    flip = r.random() < 0.5
    px = r.randint(60, 120) if not flip else r.randint(280, 340)
    if region == "Baja" and d["slug"] not in ("la-paz",):
        parts.append(cactus(W - px, ground + 6, 0.9))
    if region in ("Caribbean", "Pacific", "Oaxaca coast") or d["slug"] in ("la-paz", "los-cabos", "celestun", "el-cuyo"):
        if typ in ("beach", "island", "lagoon"):
            parts.append(palm(px, ground + 10, 0.95, flip))
    if d["slug"] in ("tulum", "valladolid", "campeche", "merida"):
        parts.append(pyramid(W - px if typ != "beach" else (330 if not flip else 80), horizon + (12 if typ == "beach" else 40), 0.75, "#8A6A48"))
    if region == "Highlands" or d["slug"] in ("loreto", "todos-santos", "valle-de-guadalupe"):
        cc = ["#C2255C", "#F2A007", "#E76F51", "#B5651D"][r.randrange(4)]
        parts.append(church(r.randint(150, 260), ground + 20, 0.8, cc))
    if "wildlife" in d["vibes"] and typ in ("beach", "island") and r.random() < 0.7:
        bx = r.randint(150, 300)
        parts.append(f'<path d="M{bx} 70 q8 -8 16 0 q8 -8 16 0" stroke="#10232A" stroke-width="2.5" fill="none"/>')
    parts.append("</svg>")
    return "".join(parts)


LOGO = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="31" fill="#0E4D5C"/>'
        '<circle cx="32" cy="28" r="11" fill="#F2A007"/><path d="M6 38c6-4 10-4 16 0s10 4 16 0 10-4 16 0 6 3 6 3v6c0 9-12 17-28 17S4 56 4 47v-6s1-1 2-3z" fill="#19B5A6"/>'
        '<path d="M8 46c6-4 10-4 16 0s10 4 16 0 10-4 16 0" stroke="#fff" stroke-width="2.4" fill="none" opacity=".8"/></svg>')


# ---------------------------------------------------------------- guides registry
GUIDES = [
    {"slug": "best-time-to-visit-mexico", "title": "The best time to visit Mexico's beaches, month by month",
     "desc": "Which Mexican coast is at its best in each month, with weather, sea temperature, rain, hurricane season and sargassum explained."},
    {"slug": "sargassum-season-guide", "title": "Sargassum in Mexico: when, where and how to avoid it",
     "desc": "What the seaweed is, which Caribbean beaches get it, the months it peaks, and the seaweed-free alternatives."},
    {"slug": "mexico-entry-requirements", "title": "Mexico entry requirements and tourist fees, explained",
     "desc": "Passports, the FMM tourist permit, customs, travelling with children and Quintana Roo's Visitax, step by step."},
    {"slug": "caribbean-vs-pacific", "title": "Caribbean or Pacific? Choosing your Mexican coast",
     "desc": "Water, sunsets, seasons, flights, prices and vibe compared, so you can pick the right side of Mexico."},
    {"slug": "cenotes-guide", "title": "A first-timer's guide to cenotes",
     "desc": "Types of cenotes, where the best ones are, entry fees, etiquette and safety in the Yucatán Peninsula's sinkholes."},
    {"slug": "whale-watching-mexico", "title": "Whale watching in Mexico: species, seasons and best spots",
     "desc": "Humpbacks, gray whales, blue whales and whale sharks: when and where to see them responsibly."},
    {"slug": "all-inclusive-vs-villa", "title": "All-inclusive resort or villa? A cost-and-fit decision guide",
     "desc": "A practical way to decide between an all-inclusive, a boutique hotel and a rental, with worked numbers."},
    {"slug": "mexico-travel-safety", "title": "Practical travel safety in Mexico's beach destinations",
     "desc": "Reading official advisories, getting around, money, water, ocean safety and the common tourist scams."},
]


# ---------------------------------------------------------------- page registry
def pdata(compact=True):
    keep = ["slug", "name", "state", "region", "zone", "type", "vibes", "budget", "sargassum", "events", "airport", "tagline"]
    return json.dumps({"d": [{k: d[k] for k in keep} for d in DESTS], "c": {k: CLIMATE[k] for k in ("zones", "sargassum", "hurricane", "events")},
                       "n": NORMALS}, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def cal_months():
    """Season & festival calendar by month."""
    fixed = {
        0: ["Peak dry season on the Caribbean and Pacific coasts", "Gray whales arrive in Baja's lagoons"],
        1: ["Carnival season (dates follow Easter); Mazatlán and Veracruz host the biggest", "Blue whale sightings build off Loreto"],
        2: ["Spring equinox at Chichén Itzá (around 20-21 March)", "Spring-break crowds in Cancún and Los Cabos"],
        3: ["Semana Santa (Holy Week) moves between March and April; national holiday crowds", "Last month of whale season in Los Cabos"],
        4: ["Start of Caribbean sea-turtle nesting", "Hottest month inland in Yucatán; eastern Pacific hurricane season opens on 15 May"],
        5: ["Atlantic hurricane season opens on 1 June", "Whale sharks arrive off Holbox and Isla Mujeres"],
        6: ["Guelaguetza dance festival in Oaxaca", "Rainy season brings green landscapes inland"],
        7: ["Wine harvest festivals in Valle de Guadalupe", "Mexican school holidays fill domestic resorts"],
        8: ["Independence Day celebrations on 15-16 September", "Peak hurricane month on both coasts"],
        9: ["Festival Internacional Cervantino in Guanajuato", "Marlin season peaks in Los Cabos"],
        10: ["Day of the Dead (31 October-2 November), biggest in Oaxaca, Mexico City and Mérida", "Dry season returns to the beaches"],
        11: ["Humpback whales return to Banderas Bay and Los Cabos", "Posadas and Christmas markets (16-24 December)"],
    }
    out = []
    for m in range(12):
        evs = [v["name"] + ": " + v["note"] for k, v in CLIMATE["events"].items() if (m + 1) in v["months"]]
        tops = sorted([d for d in ENRICHED if d["beachy"]], key=lambda d: -d["scores"][m])[:4]
        out.append({"m": m, "name": MONTHS_LONG[m], "fixed": fixed[m], "events": evs, "tops": tops})
    return out


def build():
    env = Environment(loader=FileSystemLoader(str(TPL)), autoescape=select_autoescape(["html", "j2"]), trim_blocks=True, lstrip_blocks=True)
    now = dt.datetime.now(dt.timezone.utc)
    common = {
        "MONTHS": MONTHS, "MONTHS_LONG": MONTHS_LONG, "REGIONS": REGIONS, "REGION_LABEL": REGION_LABEL, "VIBES": VIBES,
        "dests": ENRICHED, "by_slug": EBY, "guides": GUIDES, "climate": CLIMATE, "news": NEWS, "videos": VIDEOS, "fx": FX,
        "built": now.strftime("%d %B %Y, %H:%M UTC"), "built_date": now.strftime("%Y-%m-%d"), "year": now.year,
        "logo": LOGO, "base_url": BASE_URL, "score_color": score_color, "month_now": now.month - 1,
    }
    pages = []

    def render(tpl, out, **ctx):
        depth = out.count("/")
        root = "../" * depth if depth else "./"
        path = "" if out == "index.html" else out.replace("index.html", "")
        html = env.get_template(tpl).render(root=root, path=path, canonical=f"{BASE_URL}/{path}", **common, **ctx)
        p = ROOT / out
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(html, encoding="utf-8")
        if not ctx.get("noindex"):
            pages.append((path, ctx.get("priority", "0.6")))

    # postcards
    pc_dir = ROOT / "assets" / "img" / "postcards"
    pc_dir.mkdir(parents=True, exist_ok=True)
    for d in DESTS:
        (pc_dir / f"{d['slug']}.svg").write_text(postcard(d), encoding="utf-8")
    (ROOT / "assets" / "img" / "logo.svg").write_text(LOGO, encoding="utf-8")
    (ROOT / "favicon.svg").write_text(LOGO, encoding="utf-8")

    pd = pdata()
    now_m = now.month - 1
    pool = sorted([d for d in ENRICHED if d["beachy"]], key=lambda d: -d["scores"][now_m])
    picks_now, per_zone, rest = [], {}, []
    for d in pool:  # mirror of the Finder's two-per-climate-zone diversity rule
        per_zone[d["zone"]] = per_zone.get(d["zone"], 0) + 1
        (picks_now if per_zone[d["zone"]] <= 2 and len(picks_now) < 8 else rest).append(d)
    picks_now = sorted(picks_now + rest[:max(0, 8 - len(picks_now))], key=lambda d: -d["scores"][now_m])
    render("home.html.j2", "index.html", title="Paradise.mx — Where is Mexico paradise this month?",
           desc="Rank Mexico's 38 best beaches, islands, cenotes and paradise towns for any month by weather, sea temperature, rain, storms and sargassum. Then plan the trip for free.",
           pdata=pd, picks_now=picks_now, priority="1.0")
    render("destinations.html.j2", "destinations/index.html", title="Mexico destinations explorer: 38 paradise places, ranked by month",
           desc="Filter Mexico's beaches, islands and paradise towns by month, region, vibe and budget, sorted by the Paradise score.", pdata=pd, priority="0.9")
    for d in ENRICHED:
        same = sorted([x for x in ENRICHED if x["region"] == d["region"] and x["slug"] != d["slug"]], key=lambda x: -x["top"])[:4]
        if len(same) < 4:
            same += [x for x in sorted(ENRICHED, key=lambda x: -x["scores"][d["best"][0]]) if x["slug"] != d["slug"] and x not in same][:4 - len(same)]
        render("destination.html.j2", f"destinations/{d['slug']}/index.html", d=d, similar=same,
               title=f"{d['name']}, Mexico: best time to visit, where to stay and live weather",
               desc=f"{d['name']} ({d['state']}): {d['tagline']} Best months: {d['best_text']}. Climate by month, where to stay, live weather and a free trip plan.",
               priority="0.8", og_image=f"assets/img/postcards/{d['slug']}.svg")
    render("best-time.html.j2", "best-time/index.html", title="Best time to visit Mexico: the 38-destination month-by-month matrix",
           desc="One table that scores 38 Mexican beaches, islands and towns for every month of the year, with the method explained.", priority="0.9")
    render("plan.html.j2", "plan/index.html", title="Plan my Mexico trip — free personalised shortlist",
           desc="Tell us where, when and how you like to travel. Get a free, no-obligation shortlist of stays and ideas for Mexico from vetted travel partners.", priority="0.9")
    render("weddings.html.j2", "weddings/index.html", title="Destination weddings and honeymoons in Mexico",
           desc="Where and when to marry in Mexico, legal vs symbolic ceremonies, guest logistics and a free planning request.", priority="0.8")
    render("live.html.j2", "live/index.html", title="Live in paradise: retiring, relocating and buying property in Mexico",
           desc="Residency basics, buying in the coastal restricted zone, healthcare and costs, plus a free relocation and property request.", priority="0.8")
    render("tools.html.j2", "tools/index.html", title="Mexico trip tools: cost estimator, currency, compare, packing, sargassum",
           desc="Free tools for planning a Mexico beach trip.", priority="0.7")
    render("tool-cost.html.j2", "tools/trip-cost/index.html", title="Mexico trip cost estimator", desc="Estimate the cost of a trip to 38 Mexican destinations by travel style, nights and group size.", pdata=pd)
    render("tool-currency.html.j2", "tools/currency/index.html", title="Mexican peso converter with live rates", desc="Convert US dollars, Canadian dollars, euros and pounds to Mexican pesos with a live rate.")
    render("tool-compare.html.j2", "tools/compare/index.html", title="Compare Mexican destinations month by month", desc="Put up to three Mexican destinations side by side for every month of the year.", pdata=pd)
    render("tool-packing.html.j2", "tools/packing/index.html", title="Mexico packing list generator", desc="A printable packing list for beaches, cenotes, cities and weddings in Mexico.")
    render("tool-sargassum.html.j2", "tools/sargassum/index.html", title="Sargassum outlook and seaweed-free alternatives", desc="Typical sargassum exposure for Caribbean Mexico by month, and the best seaweed-free beaches instead.", pdata=pd)
    render("guides.html.j2", "guides/index.html", title="Mexico travel guides", desc="Original, practical guides for planning a Mexico beach trip.", priority="0.8")
    for g in GUIDES:
        render(f"guides/{g['slug']}.html.j2", f"guides/{g['slug']}/index.html", g=g, title=g["title"], desc=g["desc"], priority="0.8", article=True)
    render("videos.html.j2", "videos/index.html", title="Mexico travel videos", desc="Hand-picked video guides to Mexico's beaches, islands and cities.")
    render("news.html.j2", "news/index.html", title="Mexico travel news", desc="Fresh headlines for travellers heading to Mexico's beach destinations, refreshed automatically.")
    render("calendar.html.j2", "calendar/index.html", title="Mexico seasons and festivals calendar", desc="Whale seasons, turtle releases, festivals, storm season and the best beaches for each month.", cal=cal_months())
    render("contests.html.j2", "contests/index.html", title="Paradise Lens photo contest", desc="Enter the monthly Paradise Lens photo contest. Free to enter.", theme_month=MONTHS_LONG[now_m])
    render("support.html.j2", "support/index.html", title="Support Paradise.mx", desc="Help keep Paradise.mx free and independent.")
    render("advertise.html.j2", "advertise/index.html", title="Advertise, sponsor or partner with Paradise.mx", desc="Sponsorships, featured listings, newsletter placements and lead partnerships.")
    render("careers.html.j2", "careers/index.html", title="Work with Paradise.mx", desc="Freelance and part-time roles for writers, video creators, travel advisors and partnership leads.")
    render("about.html.j2", "about/index.html", title="About Paradise.mx", desc="Who we are, how the Paradise score works and our editorial standards.")
    render("contact.html.j2", "contact/index.html", title="Contact Paradise.mx", desc="Send us a message.")
    render("privacy.html.j2", "privacy/index.html", title="Privacy policy", desc="How Paradise.mx handles personal data, cookies and advertising.", priority="0.3")
    render("terms.html.j2", "terms/index.html", title="Terms of use", desc="Terms for using Paradise.mx.", priority="0.3")
    render("disclaimer.html.j2", "disclaimer/index.html", title="Disclaimer, trademark and copyright notice", desc="Independence, trademark, copyright and advertising disclosures.", priority="0.3")
    render("404.html.j2", "404.html", title="Page not found", desc="This page does not exist.", noindex=True)

    # sitemap
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, pr in pages:
        sm.append(f"  <url><loc>{BASE_URL}/{path}</loc><lastmod>{now.strftime('%Y-%m-%d')}</lastmod><priority>{pr}</priority></url>")
    sm.append("</urlset>")
    (ROOT / "sitemap.xml").write_text("\n".join(sm) + "\n", encoding="utf-8")
    (ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {BASE_URL}/sitemap.xml\n", encoding="utf-8")
    (ROOT / "ads.txt").write_text("google.com, pub-6620975821265271, DIRECT, f08c47fec0942fa0\n", encoding="utf-8")
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")
    manifest = {"name": "Paradise.mx", "short_name": "Paradise", "start_url": "./", "display": "standalone",
                "background_color": "#ffffff", "theme_color": "#0E4D5C",
                "icons": [{"src": "favicon.svg", "sizes": "any", "type": "image/svg+xml"}]}
    (ROOT / "manifest.webmanifest").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Built {len(pages)} indexable pages + 404 at {common['built']}")


if __name__ == "__main__":
    build()
