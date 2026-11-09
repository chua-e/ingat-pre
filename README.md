# ingat, pre

_ingat ingat lng sa shabu..._

Mock website for PhoCA named IngatRX

## Running

The site is fully static and runs on GitHub Pages. Search happens in the browser: `ph_GenBrn.csv` is transcribed to Filipino IPA and scored with [pho](https://github.com/Mango-Cats/pho)'s ALINE, compiled to WebAssembly with the weights in `src/scripts/py/phoc_configs/aline_cangu.toml`. The look-alike and sound-alike columns use pho's algorithms with the configs in `src/scripts/py/classifier_configs`, and the TagaBaybay spellings and Filipino IPA come from `src/scripts/py/data/classifier_cache.csv`, which the backend writes. For a name that isn't in the drug list, the browser estimates the pronunciation, so its sound-alike score is approximate (shown with `≈`).

To preview it, serve the repo root with any static server (`python -m http.server`) and open http://127.0.0.1:8000.

After changing the weights or updating `vendor/pho`, rebuild `src/scripts/wasm/aline.wasm` (needs [Rust](https://rust-lang.org/tools/install/)):

```bash
git submodule update --init
rustup target add wasm32-unknown-unknown
cd src/scripts/wasm
cargo build --release --target wasm32-unknown-unknown
cp target/wasm32-unknown-unknown/release/aline_wasm.wasm aline.wasm
```

### Classifier backend

The Python backend in `src/scripts/py` ranks drugs with the CatBoost model `c9_catboost.joblib` instead of ALINE alone. When the page finds this backend it uses the classifier automatically; on a static host it falls back to the browser search above.

For each search, `phoc` scores the query against every drug twice, on the full names and on their core words (`names.py`), and the model combines those 25 scores into a LASA probability. The steps follow [walter](https://github.com/Mango-Cats/walter): TagaBaybay nativizes each word, then Phonetisaurus transcribes it for ALINE.

It needs:

- [uv](https://docs.astral.sh/uv/) and [Rust](https://rust-lang.org/tools/install/)
- `dist/tagalog-g2p` in a sibling `Taglog-G2P` checkout, or its path in the `TAGALOG_G2P` environment variable. It's a Linux binary, so on Windows it runs through WSL (`Ubuntu-22.04` by default; set `WSL_DISTRO` to change it)
- `phoc`, and `tbb-cli` at the TagaBaybay revision pho pins, which `run.bat` builds if they're missing

To start it:

- **Windows:** double-click `run.bat`
- **Any terminal:** `cd src/scripts/py && uv run main.py` (or `npm start` if you have Node)

Then open http://127.0.0.1:8000. The server serves both the page and the search API, and reloads when Python files change. The first start transcribes the drug list and saves it to `data/classifier_cache.csv`.

To rebuild the frontend after editing `src/scripts/ts/main.ts` (needs Node): `npm install` once, then `npm run build` (or `npm run watch`).
