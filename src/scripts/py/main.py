from pathlib import Path
import csv
import sys

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ALGO_DIR = Path(__file__).parent / "algos"
sys.path.insert(0, str(ALGO_DIR))

from search import lev_search, prepare_candidates, search_drugs

DATA_DIR = Path(__file__).parent / "data"

with (DATA_DIR / "drugs.csv").open(encoding="utf-8", newline="") as file:
    transcription_rows = list(csv.DictReader(file))

prepared_candidates = prepare_candidates(transcription_rows)
if not prepared_candidates:
    raise RuntimeError(
        "No valid rows found in the saved transcription CSV. "
        "Expected non-empty name, eng_ipa, and fil_ipa columns."
    )
print(
    f"Loaded {len(prepared_candidates)} drug transcriptions "
    f"from {DATA_DIR / 'drugs.csv'}."
)
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
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