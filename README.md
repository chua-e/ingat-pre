# ingat, pre

_ingat ingat lng sa shabu..._

Mock website for PhoCA named IngatRX

## Running

The site is fully static and runs on GitHub Pages. Search happens in the browser: `ph_GenBrn.csv` is transcribed to Filipino IPA and scored with [pho](https://github.com/Mango-Cats/pho)'s ALINE, compiled to WebAssembly with the weights in `src/scripts/py/phoc_configs/aline_cangu.toml`.

To preview it, serve the repo root with any static server (`python -m http.server`) and open http://127.0.0.1:8000.

After changing the weights or updating `vendor/pho`, rebuild `src/scripts/wasm/aline.wasm` (needs [Rust](https://rust-lang.org/tools/install/)):

```bash
git submodule update --init
rustup target add wasm32-unknown-unknown
cd src/scripts/wasm
cargo build --release --target wasm32-unknown-unknown
cp target/wasm32-unknown-unknown/release/aline_wasm.wasm aline.wasm
```

The Python FastAPI backend is still in `src/scripts/py`, and needs [uv](https://docs.astral.sh/uv/) and the `phoc` CLI, but the page no longer calls it.

- **Windows:** double-click `run.bat`
- **Any terminal:** `cd src/scripts/py && uv run main.py` (or `npm start` if you have Node)

Then open http://127.0.0.1:8000. The server serves both the page and the search API, and reloads when Python files change.

To rebuild the frontend after editing `src/scripts/ts/main.ts` (needs Node): `npm install` once, then `npm run build` (or `npm run watch`).
