import json
from fastapi import FastAPI, Query, HTTPException
import httpx
from fastapi.responses import JSONResponse

app = FastAPI(title="Property API", version="1.0.0")
API_URL = "https://mz5wkrw9e4.execute-api.us-east-1.amazonaws.com/property_listing_service/prod/public/tenant/shopprop/city/seattle/state/wa"

async def fetch_properties():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(API_URL, timeout=30.0)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Error fetching properties: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred: {str(e)}"
        )

@app.get("/properties")
async def get_properties(
    city: str | None = Query(None),
    min_price: int | None = Query(None),
    max_price: int | None = Query(None)
):
    properties = await fetch_properties()
    results = properties
    if city:
        results = [p for p in results if p.get("address", {}).get("city", "").lower() == city.lower()]
    if min_price is not None:
        results = [p for p in results if p.get("price", {}).get("current", 0) >= min_price]
    if max_price is not None:
        results = [p for p in results if p.get("price", {}).get("current", float('inf')) <= max_price]
    return results

@app.get("/properties/{property_id}")
async def get_property(property_id: str):
    properties = await fetch_properties()
    for p in properties:
        if p.get("property_descriptor", {}).get("id") == property_id:
            return p
    raise HTTPException(status_code=404, detail="Property not found")
