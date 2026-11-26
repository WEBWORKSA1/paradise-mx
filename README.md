# Paradise.mx

**Where is Mexico paradise this month?** A static, self-updating guide that ranks 38 Mexican beaches, islands and paradise towns for every month (air temperature, rain, sea temperature, storm season, sargassum and wildlife), then converts visitors into trip, wedding and relocation leads.

Built for GitHub Pages (free plan, `main` branch, repository root). No server, no build step at serve time.

## What's inside

| Path | Purpose |
|---|---|
| `index.html`, `*/index.html` | Generated pages (do not edit by hand; edit `templates/` and rebuild) |
| `templates/` | Jinja2 templates for every page, including 8 long-form guides |
| `data/destinations.json` | The 38 destinations: location, airport, vibes, budget, highlights, where to stay, tips |
| `data/climate.json` | Monthly climate baselines per zone, sargassum and hurricane calendars, wildlife and festival events |
| `data/normals.json` | Per-destination climate normals recomputed monthly from Open-Meteo's archive |
| `data/fx.json`, `data/news.json`, `data/videos.json` | Live data snapshots refreshed by the workflow |
| `assets/js/site.js` | Paradise Finder, explorer, tools, live weather and FX, forms |
| `assets/js/config.js` | Site settings: AdSense client, optional ad slot IDs, optional payment links, encoded form inbox |
| `scripts/build.py` | Generates every page, postcards, sitemap, robots.txt and ads.txt |
| `scripts/update.py` | Refreshes FX, news, videos and climate normals, then rebuilds |
| `.github/workflows/refresh.yml` | Runs `update.py` every 6 hours and commits changes |
| `BUILD-PROMPT.md` | Concept, revenue model, 41-site research log and the phase-wise build prompt |

## Run locally

```bash
pip install jinja2
python3 scripts/build.py          # rebuild pages from templates + data
python3 scripts/update.py         # refresh live data, then rebuild (needs internet)
python3 -m http.server 8000       # open http://localhost:8000/
```

## Launch checklist

1. **Publish from main:** Settings → Pages → Build and deployment → Source: *Deploy from a branch* → Branch `main`, folder `/ (root)` → Save. A `gh-pages` branch is kept as an identical mirror of `main` (the refresh workflow re-syncs it every run), so the site is live and current even before this switch.
2. **Custom domain:** at the registrar for `paradise.mx`, set A records `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153` and a `www` CNAME to `webworksa1.github.io`. Then Settings → Pages → Custom domain `paradise.mx` → Save, and tick *Enforce HTTPS* once the certificate is issued. (Adding the domain in Settings creates the `CNAME` file automatically.)
3. **Forms:** submit any form once on the live site. FormSubmit sends a one-time activation email to the inbox; click *Activate*. After that, every form delivers. Optionally replace the encoded address with FormSubmit's random alias later.
4. **AdSense:** once the custom domain serves over HTTPS, add the site in AdSense, confirm `https://paradise.mx/ads.txt`, and enable Google's consent message for EEA/UK/Switzerland visitors (Privacy & messaging).
5. **In-content ad units (optional):** create display units in AdSense and paste their slot IDs into `assets/js/config.js` → `adSlots`. Auto ads work without this.
6. **Instant donations (optional):** paste Stripe Payment Links or a PayPal hosted page into `assets/js/config.js` → `pay.oneTime` / `pay.monthly`. Until then, the support page collects pledges and you send a payment link.
7. **More videos (optional):** add YouTube channel IDs to `data/video_channels.json`; the workflow will pull their latest Mexico uploads.

## Copyright

Original text, data compilations, the Paradise score, code and illustrations © Paradise.mx. All rights reserved. Fonts: Bricolage Grotesque and Source Serif 4, SIL Open Font License (see `assets/fonts/OFL.txt`).
