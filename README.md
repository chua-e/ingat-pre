# ingat, pre

_ingat ingat lng sa shabu..._

Mock website for PhoCA named IngatRX

## Running

Requires [uv](https://docs.astral.sh/uv/). The first run installs Python dependencies automatically.

- **Windows:** double-click `run.bat`
- **Any terminal:** `cd src/scripts/py && uv run main.py` (or `npm start` if you have Node)

Then open http://127.0.0.1:8000. The server serves both the page and the search API, and reloads when Python files change.

To rebuild the frontend after editing `src/scripts/ts/main.ts` (needs Node): `npm install` once, then `npm run build` (or `npm run watch`).
