import os
from fastapi import FastAPI, Query, HTTPException
import httpx
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from google import genai
from google.genai.types import GenerateContentConfig
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Gemini Configuration and Helper Functions ---
try:
    client = genai.Client()
    MODEL_NAME = "gemini-2.5-flash"
except Exception as e:
    print(f"Error initializing Gemini client: {e}")
    client = None


# Pydantic Model for Search Parameters
class PropertySearchParams(BaseModel):
    """Parameters extracted from natural language query"""

    city: str = Field(default="Seattle", description="City name")
    state: str = Field(default="WA", description="State code (e.g., 'WA')")
    country: str = Field(default="USA", description="Country name")
    min_price: Optional[int] = Field(None, description="Minimum price filter")
    max_price: Optional[int] = Field(None, description="Maximum price filter")


async def extract_search_params(query: str) -> PropertySearchParams:
    """Extract property search parameters from natural language query using Gemini's Structured Output."""
    if client is None:
        return PropertySearchParams()

    try:
        # Define the configuration for structured output
        config = GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=PropertySearchParams,
        )

        # The prompt is simplified because the schema now enforces the output structure
        prompt = f"""Extract the following information from this property search query: city, state, country, min_price, max_price.
        Use these default values if not specified: city: Seattle, state: WA, country: USA. Set min_price/max_price to null if not specified.
        
        Query: {query}"""

        # Get response from Gemini
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[prompt],
            config=config,
        )

        if hasattr(response, "parsed") and response.parsed is not None:
            return response.parsed
        else:
            print(
                f"Warning: Structured output parsing failed. Raw text: {response.text}"
            )
            return PropertySearchParams()

    except Exception as e:
        print(f"Error extracting parameters from Gemini: {str(e)}")
        return PropertySearchParams()


# --- FastAPI Application ---

app = FastAPI(title="Property API", version="1.0.0")
BASE_URL = "https://mz5wkrw9e4.execute-api.us-east-1.amazonaws.com/property_listing_service/prod/public/tenant/shopprop"


async def fetch_properties(
    payload: Optional[Dict[str, Any]] = None, city: str = "seattle", state: str = "wa"
) -> Dict[str, Any]:
    """Fetch properties from the API with the given payload (Function body kept for completeness)"""
    headers = {
        "apikey": os.getenv("API_KEY"),
        "authorization": "",
        "company": "shopprop",
        "tenant": "shopprop",
        "Content-Type": "application/json",
        "user": "test",
    }

    api_url = f"{BASE_URL}/city/{city.lower()}/state/{state.lower()}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                api_url, headers=headers, json=payload, timeout=30.0
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
    query: str = Query(None, description="Natural language query for property search"),
    city: str = Query(None, description="City name to search for properties"),
    state: str = Query(None, description="State code (e.g., 'WA')"),
    country: str = Query(None, description="Country name"),
    min_price: Optional[int] = Query(None, description="Minimum price filter"),
    max_price: Optional[int] = Query(None, description="Maximum price filter"),
):
    """Get properties with optional filtering by location and price range"""

    params = PropertySearchParams(
        city="Seattle", state="WA", country="USA", min_price=None, max_price=None
    )

    if query:
        try:
            llm_params = await extract_search_params(query)
            print(f"Extracted Params: {llm_params.model_dump()}")
            # Use LLM-extracted values as a base
            params = llm_params
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error processing LLM query: {str(e)}"
            )

    if city is not None:
        params.city = city
    if state is not None:
        params.state = state
    if country is not None:
        params.country = country
    if min_price is not None:
        params.min_price = min_price
    if max_price is not None:
        params.max_price = max_price

    try:
        # Build the payload with the determined parameters
        payload: Dict[str, Any] = {
            "sort_by": "last_updated_time",
            "order_by": "desc",
            "searched_address_formatted": f"{params.city}, {params.state}, {params.country}",
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
            "image_count": 0,
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

        # Add price filters only if they have a value (None will be excluded by default
        # if using model_dump, but explicitly checking handles the API payload structure)
        if params.min_price is not None:
            payload["min_price"] = params.min_price

        if params.max_price is not None:
            payload["max_price"] = params.max_price

        # Fetch properties with the filtered payload
        response = await fetch_properties(payload, params.city, params.state)
        properties = response.get("data", [])
        print(f"Fetched Properties: {len(properties)}")

        # Return response with length and properties
        # return response.get("data", [])
        return {"length": len(properties), "properties": properties}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing properties: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn

    # Make sure to set GOOGLE_API_KEY environment variable before running
    uvicorn.run(app, host="0.0.0.0", port=8000)
