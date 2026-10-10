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
