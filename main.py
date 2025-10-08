# main.py - A simpler version for use with clients like mcp-use

import os
import asyncio
import httpx
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field
import sys
from pathlib import Path

# --- FastMCP Imports ---
from fastmcp import FastMCP

sys.path.append(str(Path(__file__).parent))
os.chdir(Path(__file__).parent)

# Load environment variables (API_KEY)
load_dotenv()

# --- FastMCP Server Initialization ---
mcp = FastMCP("property-search-mcp")


# --- Helper Function to Fetch Properties (Unchanged) ---
async def fetch_properties_from_api(
    city: str,
    state: str,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
) -> dict:
    """Fetches properties from the external property API."""
    api_key = os.getenv("API_KEY")
    tenant = os.getenv("TENANT")
    if not api_key:
        return {"error": "API_KEY environment variable not set on the server."}

    headers = {
        "apikey": api_key,
        "authorization": "",
        "company": "shopprop",
        "tenant": "shopprop",
        "Content-Type": "application/json",
        "user": "test",
    }

    BASE_URL = "https://mz5wkrw9e4.execute-api.us-east-1.amazonaws.com/property_listing_service/prod/public"
    api_url = f"{BASE_URL}/tenant/{tenant}/city/{city.lower()}/state/{state.lower()}"

    payload = {
        "sort_by": "last_updated_time",
        "order_by": "desc",
        "searched_address_formatted": f"{city}, {state}, USA",
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

    if min_price is not None:
        payload["min_price"] = min_price
    if max_price is not None:
        payload["max_price"] = max_price

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
    response_data = await fetch_properties_from_api(city, state, min_price, max_price)

    if "error" in response_data:
        return f"Failed to fetch properties: {response_data['error']}"

    properties = response_data.get("data", [])
    if not properties:
        return f"No properties found in {city}, {state} matching your criteria."

    result_string = f"Found {len(properties)} properties in {city}, {state}:\n\n"
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
    mcp.run()
