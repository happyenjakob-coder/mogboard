# Portfolio Autopilot

A zero-dependency, locally-run web dashboard you check each day. It mirrors the
portfolios of famous public investors — Berkshire Hathaway, ARK, Renaissance,
Scion (Michael Burry), Pershing Square, Citadel, Two Sigma, Tiger Global, Coatue,
Soros, Third Point, Greenlight, Appaloosa, and the Gates Foundation Trust — by
diffing each manager's two most recent SEC 13F filings and turning the changes
into plain-English trade signals.

## What you get

- **Consensus moves** — where the tracked group added or removed money on net,
  ranked by dollar change, with the number of managers acting.
- **Your copy** — enter your portfolio size and every position shows what your
  slice would be if you mirrored the managers equally (average weight x size).
- **By manager** — each manager's top holdings with weights, plus NEW / EXIT /
  INCREASED / REDUCED signals versus their previous filing.
- **Stale handling** — managers who stopped filing (e.g. Appaloosa) are flagged
  and excluded from consensus.

## Run it

```bash
python3 app.py
# open http://127.0.0.1:8000
```

No dependencies beyond the Python standard library. Data is cached in
`data/cache.json` and refreshed automatically every 12 hours; hit the
**Refresh data** button (or `POST /api/refresh`) for an immediate pull.

Set your own contact for SEC fair-access compliance:

```bash
AUTOPILOT_SEC_UA="Portfolio-Autopilot/1.0 (me@mydomain.com)" python3 app.py
```

## How it works

1. Fetches the filing index for each manager from SEC EDGAR
   (`data.sec.gov/submissions/CIK*.json`).
2. Downloads the two most recent 13F-HR filings (using amendments when newer),
   parses the information-table XML, and aggregates rows per CUSIP.
3. Diffs current vs previous quarter: share counts changing by >= 5% produce
   INCREASED/REDUCED; new CUSIPs are NEW; dropped CUSIPs are EXIT.
4. Aggregates per-CUSIP dollar changes across managers into the consensus view,
   resolving issuer names to tickers via SEC's company ticker dataset.

## Honest limitations

- 13F data is **quarterly** with up to a 45-day filing lag; it shows positioning,
  not live trades.
- 13F reports long US-listed positions only (no shorts, futures, or foreign
  listings), so "EXIT" can sometimes be a conversion into another instrument.
- This is an educational tool, not financial advice. Nothing here is a
  recommendation; you alone are responsible for any trades you place.

## Customizing

Edit `MANAGERS` in `engine.py` — each entry is `{"cik": "...", "name": "..."}`.
Find any 13F filer's CIK with EDGAR full-text search
(https://efts.sec.gov/LATEST/search-index?q=... ) or the company browse page.
