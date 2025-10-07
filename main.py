import json
from fastapi import FastAPI, Query, HTTPException

# Load data from JSON file
with open("data.json", "r") as f:
    properties = json.load(f)

app = FastAPI(title="Property API", version="1.0.0")


@app.get("/properties")
async def get_properties(
    city: str | None = Query(None),
    min_price: int | None = Query(None),
    max_price: int | None = Query(None)
):
    results = properties
    if city:
        results = [p for p in results if p["address"]["city"].lower() == city.lower()]
    if min_price:
        results = [p for p in results if p["price"]["current"] >= min_price]
    if max_price:
        results = [p for p in results if p["price"]["current"] <= max_price]
    return results


@app.get("/properties/{property_id}")
async def get_property(property_id: str):
    for p in properties:
        if p["property_descriptor"]["id"] == property_id:
            return p
    raise HTTPException(status_code=404, detail="Property not found")
