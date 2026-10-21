from pathlib import Path
import csv

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from search import search_drugs

DATA_FILE = Path(__file__).parent/"data"/"ph_fda.csv"

with DATA_FILE.open(encoding="utf-8", newline="") as file:
    drugs = list(csv.DictReader(file))

app = FastAPI()

class SearchRequest(BaseModel):
    query: str = Field(min_length=1)


@app.post("/api/search")
def search(request: SearchRequest):
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Enter a drug name.")
    
    return search_drugs(request.query, drugs)