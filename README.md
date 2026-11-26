# Mogboard

A swing-trading board styled after PSL and looksmaxxing culture. It rates every open position, every closed trade and the portfolio as a whole on the PSL scale (1–8, from "It's over" up to "PSL God").

## Features

- **Portfolio PSL rating**: a radar of five "facial features": Jawline (win rate), Eye area (average R), Midface (profit factor), Skin (open heat, called "Cortisol") and Frame (streak of trades that respected the stop). It names your weakest feature and how to fix it.
- **The Lineup**: open positions with a PSL tier by unrealized R, a status (Mogging, Ascending, Mid, Frauding, It's over) and a stop → entry → target bar. Edit the last price and the stop in place.
- **Frame Calculator**: sizes a position from the stop, with Softmaxx 0.5%, Mewing 1% and Hardmaxx 2% presets and a "canthal tilt" reward-to-risk verdict.
- **Hunter Eyes**: a watchlist showing how far each setup is from its trigger. One click loads a setup into the calculator.
- **Ascension Log**: closed trades with verdicts, an equity curve and an R-per-trade chart.
- **Looksmax Protocol**: a daily discipline checklist.
- **PSL Dictionary**: the slang, translated to trading.

## Running it

It's one self-contained HTML file. Open `index.html` in a browser.

There is no live price feed: you type in prices yourself. Saving uses the Claude artifact data store, so when you open the file outside Claude it runs as an example board that resets on reload.

Not financial advice.

## Autopilot (`autopilot/`)

A companion daily dashboard that mirrors famous public portfolios — Berkshire Hathaway, ARK, Renaissance, Scion (Michael Burry), Pershing Square, Citadel, Two Sigma, Tiger Global, Coatue, Soros, Third Point, Greenlight, Appaloosa and the Gates Foundation Trust. It diffs each manager's two most recent SEC 13F filings into NEW / EXIT / INCREASED / REDUCED signals, ranks consensus buys and sells across the group, and sizes every position for your own portfolio value.

Run it (Python 3, no dependencies):

```bash
cd autopilot
python3 app.py
# open http://127.0.0.1:8000
```

Data comes straight from SEC EDGAR, is cached in `autopilot/data/`, and refreshes every 12 hours (or on the Refresh button). See `autopilot/README.md` for details and limitations (13F data is quarterly with a 45-day lag). Educational tool, not financial advice.
