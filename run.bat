@echo off
if not exist "%~dp0vendor\pho\target\release\phoc.exe" (
    git -C "%~dp0." submodule update --init
    cargo build --release --bin phoc --manifest-path "%~dp0vendor\pho\Cargo.toml"
)
if not exist "%~dp0src\scripts\py\.tbb\bin\tbb-cli.exe" (
    cargo install --git https://github.com/Mango-Cats/tagabaybay --rev cf4673c7e2c00930e6361f054f8a6be16506399f --bin tbb-cli --root "%~dp0src\scripts\py\.tbb" --locked
)
cd /d "%~dp0src\scripts\py"
uv run main.py
pause
