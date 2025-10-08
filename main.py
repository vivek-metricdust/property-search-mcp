import os
import asyncio
import httpx
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# --- FastMCP Imports ---
from fastmcp import FastMCP

# Load environment variables (API_KEY)
load_dotenv()

# --- FastMCP Server Initialization ---
mcp = FastMCP("property-search-mcp")


# --- Pydantic Model for API Call (Still useful!) ---
class PropertySearchParams(BaseModel):
    """Parameters for the property search tool."""

    city: str = Field(description="City name to search in (e.g., 'Seattle')")
    state: str = Field(description="State code (e.g., 'WA')")
    min_price: Optional[int] = Field(None, description="Minimum property price")
    max_price: Optional[int] = Field(None, description="Maximum property price")


# --- Helper Function to Fetch Properties (Unchanged) ---
async def fetch_properties_from_api(params: PropertySearchParams) -> dict:
    """Fetches properties from the external property API."""
    api_key = os.getenv("API_KEY")
    tenant = os.getenv("TENANT")
    if not api_key:
        return {"error": "API_KEY environment variable not set on the server."}

    headers = {
        "apikey": api_key,
        "authorization": "",
        "company": tenant,
        "tenant": tenant,
        "Content-Type": "application/json",
        "user": "test",
    }

    BASE_URL = "https://mz5wkrw9e4.execute-api.us-east-1.amazonaws.com/property_listing_service/prod/public/tenant/shopprop"
    api_url = f"{BASE_URL}/city/{params.city.lower()}/state/{params.state.lower()}"

    payload = {
        "sort_by": "last_updated_time",
        "order_by": "desc",
        "searched_address_formatted": f"{params.city}, {params.state}, USA",
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
        "size": 10,
        "allowed_mls": ["NWMLS", "shopprop"],
        "cursor": None,
    }

    if params.min_price is not None:
        payload["min_price"] = params.min_price
    if params.max_price is not None:
        payload["max_price"] = params.max_price

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                api_url, headers=headers, json=payload, timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        return {"error": f"API Error: {e.response.status_code} - {e.response.text}"}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {str(e)}"}


# --- FastMCP Tool Definition ---
@mcp.tool()
async def search_properties(
    city: str,
    state: str,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
) -> str:
    """
    Searches for real estate property listings for sale in a specific city and state.
    You can filter by minimum and maximum price.
    """
    # Create the params object to call our helper function
    params = PropertySearchParams(
        city=city, state=state, min_price=min_price, max_price=max_price
    )

    # Fetch data from the external API
    response_data = await fetch_properties_from_api(params)

    # Handle errors from the API call
    if "error" in response_data:
        return f"Failed to fetch properties: {response_data['error']}"

    properties = response_data.get("data", [])
    if not properties:
        return f"No properties found in {params.city}, {params.state} matching your criteria."

    # Format the results into a readable string for the AI
    result_string = (
        f"Found {len(properties)} properties in {params.city}, {params.state}:\n\n"
    )
    for prop in properties:
        price_val = prop.get("price")
        formatted_price = (
            f"${price_val:,}" if isinstance(price_val, (int, float)) else "N/A"
        )

        result_string += (
            f"- **{prop.get('address', 'N/A')}**\n"
            f"  - Price: {formatted_price}\n"
            f"  - Beds: {prop.get('bedroom', 'N/A')} | Baths: {prop.get('bathroom', 'N/A')}\n"
            f"  - Area: {prop.get('area', 'N/A')} sqft\n"
            f"  - Description: {prop.get('property_descriptor', 'N/A')}\n\n"
        )

    return result_string


# --- Main Execution ---
if __name__ == "__main__":
    # The run() method handles all the stdio setup and server lifecycle
    mcp.run()
