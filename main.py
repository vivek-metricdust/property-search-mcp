import json
from fastapi import FastAPI, Query, HTTPException
import httpx
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any

app = FastAPI(title="Property API", version="1.0.0")
API_URL = "https://mz5wkrw9e4.execute-api.us-east-1.amazonaws.com/property_listing_service/prod/public/tenant/shopprop/city/seattle/state/wa"


async def fetch_properties(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Fetch properties from the API with the given payload"""
    headers = {
        "apikey": "59d02ffe-07c6-4823-99bd-f003fe5119de",
        "authorization": "",
        "company": "shopprop",
        "tenant": "shopprop",
        "Content-Type": "application/json",
        "user": "test",
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                API_URL, headers=headers, json=payload, timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Error fetching properties: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


@app.get("/properties")
async def get_properties(
    city: str = Query("Seattle", description="City name to search for properties"),
    state: str = Query("WA", description="State code (e.g., 'WA')"),
    country: str = Query("USA", description="Country name"),
    min_price: int = Query(25000, description="Minimum price filter"),
    max_price: Optional[int] = Query(None, description="Maximum price filter"),
):
    """Get properties with optional filtering by location and price range"""
    try:
        # Build the payload with default values
        payload = {
            "sort_by": "last_updated_time",
            "order_by": "desc",
            "searched_address_formatted": f"{city}, {state}, {country}",
            "property_status": "SALE",
            "min_price": min_price,
            "output": [
                "area",
                "price",
                "bedroom",
                "bathroom",
                "property_descriptor",
                "location",
                "has_open_house",
                "virtual_url",
                "address",
                "status",
                "openhouse_latest_value",
            ],
            "image_count": 2,
            "size": 100,
            "allowed_mls": [
                "ARMLS",
                "ACTRISMLS",
                "BAREISMLS",
                "CRMLS",
                "CENTRALMLS",
                "MLSLISTINGS",
                "NWMLS",
                "NTREISMLS",
                "shopprop",
            ],
            "cursor": None,
        }

        # Apply max_price filter if provided
        if max_price is not None:
            payload["max_price"] = max_price

        # Fetch properties with the filtered payload
        response = await fetch_properties(payload)
        return response.get("data", [])

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing properties: {str(e)}"
        )


@app.get("/properties/{property_id}")
async def get_property(property_id: str):
    """Get a single property by ID"""
    try:
        # First, get the property details
        payload = {
            "property_status": "SALE",
            "output": [
                "area",
                "price",
                "bedroom",
                "bathroom",
                "property_descriptor",
                "location",
                "has_open_house",
                "virtual_url",
                "address",
                "status",
                "openhouse_latest_value",
            ],
            "property_id": property_id,
        }

        response = await fetch_properties(payload)
        properties = response.get("data", [])

        if not properties:
            raise HTTPException(status_code=404, detail="Property not found")

        return properties[0]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching property: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
