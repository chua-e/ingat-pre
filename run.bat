@echo off
if not exist "%~dp0vendor\pho\target\release\phoc.exe" (
    git -C "%~dp0." submodule update --init
    cargo build --release --bin phoc --manifest-path "%~dp0vendor\pho\Cargo.toml"
)
cd /d "%~dp0src\scripts\py"
uv run main.py
pause
