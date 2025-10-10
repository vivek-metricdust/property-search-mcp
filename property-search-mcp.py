# property-search-mcp.py - A simpler version for use with clients like mcp-use

import os
import asyncio
import httpx
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field
import sys
from pathlib import Path
import logging
import json

# --- FastMCP Imports ---
from fastmcp import FastMCP

sys.path.append(str(Path(__file__).parent))
os.chdir(Path(__file__).parent)

# Load environment variables (API_KEY)
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- FastMCP Server Initialization ---
mcp = FastMCP("property-search-mcp")

# --- Load OpenAPI Specification ---
SCRIPT_DIR = Path(__file__).parent
SPEC_FILE_PATH = SCRIPT_DIR / "openapi.json"

try:
    with open(SPEC_FILE_PATH, "r") as f:
        openapi_spec = json.load(f)
    logger.info(f"Successfully loaded openapi.json from {SPEC_FILE_PATH}")
except FileNotFoundError:
    logger.error(
        f"FATAL: openapi.json not found at {SPEC_FILE_PATH}. Please ensure it is in the same directory as the script."
    )
    openapi_spec = None


# --- Helper Function to Fetch Properties (Unchanged) ---
async def fetch_properties_from_api(
    city: str,
    state: str,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    bedrooms: Optional[int] = None,
    bathrooms: Optional[int] = None,
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

    server_url = openapi_spec["servers"][0]["url"]
    path_template = "/tenant/{tenant}/city/{city}/state/{state}"
    api_path = path_template.format(
        tenant=tenant, city=city.lower(), state=state.lower()
    )
    full_url = f"{server_url}{api_path}"
    # logger.info(f"API URL: {full_url}")

    # payload = {
    #     "sort_by": "last_updated_time",
    #     "order_by": "desc",
    #     "searched_address_formatted": f"{city}, {state}, USA",
    #     "property_status": "SALE",
    #     "output": [
    #         "area",
    #         "price",
    #         "bedroom",
    #         "bathroom",
    #         "property_descriptor",
    #         "location",
    #         "has_open_house",
    #         "virtual_url",
    #         "address",
    #         "status",
    #         "openhouse_latest_value",
    #     ],
    #     "image_count": 0,
    #     "size": 10,
    #     "allowed_mls": [
    #         "ARMLS",
    #         "ACTRISMLS",
    #         "BAREISMLS",
    #         "CRMLS",
    #         "CENTRALMLS",
    #         "MLSLISTINGS",
    #         "NWMLS",
    #         "NTREISMLS",
    #         "shopprop",
    #     ],
    #     "cursor": None,
    # }

    path_item = openapi_spec["paths"][path_template]
    base_payload_schema = path_item["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]["properties"]

    payload = {
        key: value.get("example")
        for key, value in base_payload_schema.items()
        if key not in ["min_price", "max_price", "bedroom", "bathroom"]
    }

    payload["searched_address_formatted"] = f"{city}, {state}, USA"

    if min_price is not None:
        payload["min_price"] = min_price
    if max_price is not None:
        payload["max_price"] = max_price
    if bedrooms is not None:
        payload["bedroom"] = bedrooms
    if bathrooms is not None:
        payload["bathroom"] = bathrooms
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                full_url, headers=headers, json=payload, timeout=30.0
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
    bedrooms: Optional[int] = None,
    bathrooms: Optional[int] = None,
) -> str:
    """
    Searches for real estate property listings for sale in a specific city and state.
    You can filter by minimum and maximum price.
    """
    response_data = await fetch_properties_from_api(
        city, state, min_price, max_price, bedrooms, bathrooms
    )

    if "error" in response_data:
        return f"Failed to fetch properties: {response_data['error']}"

    properties = response_data.get("data", [])
    if not properties:
        return f"No properties found in {city}, {state} matching your criteria."

    result_string = f"Found {len(properties)} properties in {city}, {state}:\n\n"
    for prop in properties:
        address = (
            prop.get("google_address")
            if prop.get("google_address")
            else prop.get("address")
        )
        result_string += (
            f"- **{address}**\n"
            f"  - Price: {prop.get('price', 'N/A')}\n"
            f"  - Beds: {prop.get('bedroom', 'N/A')}\n"
            f"  - Baths: {prop.get('bathroom', 'N/A')}\n"
            f"  - Area: {prop.get('area', 'N/A')} sqft\n"
            f"  - Description: {prop.get('property_descriptor', 'N/A')}\n\n"
        )

    return result_string


# --- Main Execution ---
if __name__ == "__main__":
    mcp.run()
