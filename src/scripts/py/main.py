from pathlib import Path
import os
import sys

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from supabase import create_client

ROOT_DIR = Path(__file__).parents[3]
load_dotenv(ROOT_DIR / ".env")

ALGO_DIR = Path(__file__).parent / "algos"
sys.path.insert(0, str(ALGO_DIR))

from search import lev_search, prepare_candidates, search_drugs

def load_transcription_rows() -> list[dict[str, str]]:
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_PUBLISHABLE_KEY") or os.environ.get("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        raise RuntimeError(
            "Set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY "
            "(or SUPABASE_KEY) in the .env file."
        )

    client = create_client(supabase_url, supabase_key)
    rows: list[dict[str, str]] = []
    page_size = 1000
    offset = 0

    while True:
        response = (
            client.table("drug-db")
            .select("id,name,eng_ipa,fil_ipa,source")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        page = response.data
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size

    return rows

transcription_rows = load_transcription_rows()
prepared_candidates = prepare_candidates(transcription_rows)
if not prepared_candidates:
    raise RuntimeError(
        "Supabase returned no valid drug rows. "
        "Check that drug-db has non-empty name and eng_ipa columns."
    )
print(
    f"Loaded {len(prepared_candidates)} drug transcriptions "
    "from Supabase."
)
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "https://chua-e.github.io",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)

class SearchRequest(BaseModel):
    query: str = Field(min_length=1)


@app.post("/api/search")
def search(request: SearchRequest):
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Enter a drug name.")

    try:
        return search_drugs(query, prepared_candidates)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

# Serve the frontend from the same server so one command runs everything.
@app.get("/", include_in_schema=False)
def index():
    return FileResponse(ROOT_DIR / "index.html")


app.mount("/src", StaticFiles(directory=ROOT_DIR / "src"), name="src")


if __name__ == "__main__":
    import uvicorn

    print("IngatRX running at http://127.0.0.1:8000")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
