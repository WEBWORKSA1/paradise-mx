#!/usr/bin/env python3
"""Paradise.mx auto-refresh.

Pulls fresh exchange rates, travel news, optional YouTube channel uploads and (monthly)
climate normals, then rebuilds every page. Designed for the GitHub Actions schedule in
.github/workflows/refresh.yml, but safe to run locally. Every source fails soft: if a
service is down, the previous data file is kept.
"""
import datetime as dt
import email.utils
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
UA = {"User-Agent": "Mozilla/5.0 (compatible; ParadiseMxRefresh/1.0; +https://paradise.mx)"}
NOW = dt.datetime.now(dt.timezone.utc)


def get(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def get_json(url, timeout=30):
    return json.loads(get(url, timeout).decode("utf-8"))


def save(name, obj):
    (DATA / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load(name, default):
    p = DATA / name
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


# ------------------------------------------------------------------ exchange rates
def refresh_fx():
    sources = [
        ("frankfurter", "https://api.frankfurter.dev/v1/latest?base=USD&symbols=MXN,CAD,EUR,GBP",
         lambda j: (j["rates"], j.get("date"))),
        ("frankfurter", "https://api.frankfurter.app/latest?from=USD&to=MXN,CAD,EUR,GBP",
         lambda j: (j["rates"], j.get("date"))),
        ("open.er-api.com", "https://open.er-api.com/v6/latest/USD",
         lambda j: ({k: j["rates"][k] for k in ("MXN", "CAD", "EUR", "GBP")}, j.get("time_last_update_utc", "")[:16])),
    ]
    for name, url, parse in sources:
        try:
            rates, date = parse(get_json(url))
            if not rates.get("MXN"):
                continue
            save("fx.json", {"base": "USD", "date": NOW.strftime("%d %b %Y"), "source": name,
                             "rates": {k: round(float(v), 4) for k, v in rates.items()}})
            print(f"fx: {rates['MXN']:.3f} MXN per USD from {name}")
            return
        except Exception as e:  # noqa: BLE001
            print(f"fx: {name} failed: {e}", file=sys.stderr)


# ------------------------------------------------------------------ news (Google News RSS)
NEWS_QUERIES = [
    'Mexico travel tourists',
    'Cancun OR Tulum OR "Playa del Carmen" OR Cozumel tourism',
    '"Los Cabos" OR "Puerto Vallarta" OR "Riviera Nayarit" tourism',
    'sargassum Quintana Roo',
    'Visitax OR "Mexico tourist tax"',
    'Oaxaca OR Huatulco OR Holbox OR Bacalar travel',
]
BLOCK = re.compile(r"\b(murder|killed|shooting|cartel|kidnap|dead body|bodies|massacre)\b", re.I)


def refresh_news():
    items, seen = [], set()
    for q in NEWS_QUERIES:
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q + " when:30d", "hl": "en-US", "gl": "US", "ceid": "US:en"})
        try:
            root = ET.fromstring(get(url))
        except Exception as e:  # noqa: BLE001
            print(f"news: query failed ({q}): {e}", file=sys.stderr)
            continue
        for it in root.iter("item"):
            title = html.unescape((it.findtext("title") or "").strip())
            link = (it.findtext("link") or "").strip()
            src_el = it.find("source")
            source = (src_el.text or "").strip() if src_el is not None else ""
            if source and title.endswith(" - " + source):
                title = title[: -len(source) - 3]
            key = re.sub(r"\W+", "", title.lower())[:80]
            if not title or not link or key in seen or BLOCK.search(title):
                continue
            seen.add(key)
            try:
                pub = email.utils.parsedate_to_datetime(it.findtext("pubDate"))
            except Exception:  # noqa: BLE001
                pub = NOW
            if (NOW - pub).days > 45:
                continue
            items.append({"title": title, "link": link, "source": source or "News", "date": pub.strftime("%d %b %Y"), "_ts": pub.timestamp()})
        time.sleep(1)
    if len(items) >= 5:
        items.sort(key=lambda x: -x["_ts"])
        for x in items:
            x.pop("_ts", None)
        save("news.json", {"updated": NOW.strftime("%d %B %Y, %H:%M UTC"), "items": items[:40]})
        print(f"news: {len(items[:40])} headlines")
    else:
        print("news: too few results, keeping previous file", file=sys.stderr)


# ------------------------------------------------------------------ videos (optional channel feeds)
def refresh_videos():
    vids = load("videos.json", {"items": []})
    channels = load("video_channels.json", {"channels": []}).get("channels", [])
    curated = [v for v in vids.get("items", []) if not v.get("auto")]
    ids = {v["id"] for v in curated}
    fresh = []
    ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
    for ch in channels:
        try:
            root = ET.fromstring(get("https://www.youtube.com/feeds/videos.xml?channel_id=" + ch["channel_id"]))
        except Exception as e:  # noqa: BLE001
            print(f"videos: {ch.get('name')} failed: {e}", file=sys.stderr)
            continue
        for en in root.findall("a:entry", ns)[: ch.get("max", 3)]:
            vid = en.findtext("yt:videoId", namespaces=ns)
            title = en.findtext("a:title", namespaces=ns) or ""
            kw = [k.lower() for k in ch.get("must_include", [])]
            if not vid or vid in ids or (kw and not any(k in title.lower() for k in kw)):
                continue
            ids.add(vid)
            fresh.append({"id": vid, "title": title, "channel": ch.get("name"), "dest": ch.get("dest"), "auto": True,
                          "published": en.findtext("a:published", namespaces=ns)})
    fresh.sort(key=lambda v: v.get("published") or "", reverse=True)
    vids["items"] = fresh[:12] + curated
    vids["updated"] = NOW.strftime("%d %B %Y")
    save("videos.json", vids)
    print(f"videos: {len(fresh)} new from feeds, {len(curated)} curated")


# ------------------------------------------------------------------ climate normals (monthly)
def refresh_normals(force=False, budget_s=360):
    """Recompute per-destination climate normals, a few at a time.

    Each destination is refreshed at most every 30 days. Work stops after `budget_s`
    seconds and the partial result is saved, so the next scheduled run continues where
    this one stopped and a slow archive service can never block the other refreshes.
    """
    normals = load("normals.json", {})
    dests = load("destinations.json", [])
    climate = load("climate.json", {})
    start, end = f"{NOW.year - 8}-01-01", f"{NOW.year - 1}-12-31"
    t0, ok, tried = time.time(), 0, 0
    out = dict(normals)
    for d in dests:
        prev = normals.get(d["slug"]) or {}
        at = prev.get("at")
        if at and not force and (NOW - dt.datetime.fromisoformat(at)).days < 30:
            continue
        if time.time() - t0 > budget_s:
            print("normals: time budget reached; continuing next run")
            break
        tried += 1
        url = ("https://archive-api.open-meteo.com/v1/archive?" + urllib.parse.urlencode({
            "latitude": d["lat"], "longitude": d["lon"], "start_date": start, "end_date": end,
            "daily": "temperature_2m_max,precipitation_sum", "timezone": "auto"}))
        try:
            j = get_json(url, timeout=40)
            days, tmax, prcp = j["daily"]["time"], j["daily"]["temperature_2m_max"], j["daily"]["precipitation_sum"]
        except Exception as e:  # noqa: BLE001
            print(f"normals: {d['slug']} failed: {e}", file=sys.stderr)
            continue
        hi_sum, hi_n, wet = [0.0] * 12, [0] * 12, [0] * 12
        years = set()
        for t, h, p in zip(days, tmax, prcp):
            m = int(t[5:7]) - 1
            years.add(t[:4])
            if h is not None:
                hi_sum[m] += h; hi_n[m] += 1
            if p is not None and p >= 2.5:  # reanalysis drizzle bias: count meaningful rain only
                wet[m] += 1
        ny = max(1, len(years))
        base = climate["zones"][d["zone"]]
        # Reanalysis grid cells smooth coastal heat and over-count light rain, so each value is
        # blended 50/50 with the curated zone baseline: local detail without the model bias.
        hi = [round((hi_sum[m] / hi_n[m] + base["hi"][m]) / 2) if hi_n[m] else base["hi"][m] for m in range(12)]
        rain = [round((wet[m] / ny + base["rain"][m]) / 2) for m in range(12)]
        out[d["slug"]] = {"hi": hi, "rain": rain, "at": NOW.isoformat()}
        ok += 1
        time.sleep(0.5)
    if ok:
        out["_source"] = "Open-Meteo historical weather API (ERA5), " + start[:4] + "-" + end[:4]
        out.pop("_computed", None)
        save("normals.json", out)
    print(f"normals: {ok} of {tried} attempted destinations updated")


def main():
    force = "--force-normals" in sys.argv
    for step in (refresh_fx, refresh_news, refresh_videos, lambda: refresh_normals(force)):
        try:
            step()
        except Exception as e:  # noqa: BLE001
            print(f"step failed: {e}", file=sys.stderr)
    sys.path.insert(0, str(ROOT / "scripts"))
    import build  # noqa: E402  (imported late so it reads the refreshed data)
    build.build()


if __name__ == "__main__":
    main()
