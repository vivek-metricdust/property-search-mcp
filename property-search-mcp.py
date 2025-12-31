# property-search-mcp.py - A simpler version for use with clients like mcp-use

import os
import asyncio
import httpx
from typing import Optional, Union
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
    cursor: Optional[str] = None,
    size: Optional[int] = None,
) -> dict:
    """
    Fetches properties from the external property API.

    Args:
        city (str): The city to search for properties.
        state (str): The state to search for properties.
        min_price (Optional[int]): The minimum price of the property.
        max_price (Optional[int]): The maximum price of the property.
        bedrooms (Optional[int]): The number of bedrooms in the property.
        bathrooms (Optional[int]): The number of bathrooms in the property.
        cursor (Optional[str]): The cursor for pagination to fetch the next set of results.
        size (Optional[int]): The number of results to return.

    Returns:
        dict: A dictionary containing the properties.

    Example Usage:
        fetch_properties_from_api("Kirkland", "WA", min_price=100000, max_price=200000)
    """
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

    server_url = openapi_spec["servers"][0]["url"]
    path_template = "/tenant/{tenant}/city/{city}/state/{state}"
    api_path = path_template.format(
        tenant=tenant, city=city.lower(), state=state.lower()
    )
    full_url = f"{server_url}{api_path}"

    path_item = openapi_spec["paths"][path_template]
    base_payload_schema = path_item["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]["properties"]

    payload = {
        key: value.get("example")
        for key, value in base_payload_schema.items()
        if key
        not in ["min_price", "max_price", "bedroom", "bathroom", "cursor", "size"]
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
    if cursor is not None:
        payload["cursor"] = cursor
    if size is not None:
        payload["size"] = size
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
    min_price: Optional[Union[int, str]] = None,
    max_price: Optional[Union[int, str]] = None,
    bedrooms: Optional[Union[int, str]] = None,
    bathrooms: Optional[Union[int, str]] = None,
    cursor: Optional[str] = None,
    size: Optional[Union[int, str]] = None,
) -> str:
    """
    Searches for real estate property listings for sale in a specific city and state.
    You can filter by minimum and maximum price.

    Args:
        city (str): The city to search for properties.
        state (str): The state to search for properties.
        min_price (Optional[Union[int, str]]): The minimum price of the property.
        max_price (Optional[Union[int, str]]): The maximum price of the property.
        bedrooms (Optional[Union[int, str]]): The number of bedrooms in the property.
        bathrooms (Optional[Union[int, str]]): The number of bathrooms in the property.
        cursor (Optional[str]): The cursor for pagination to fetch the next set of results.
        size (Optional[Union[int, str]]): The number of results to return.

    Returns:
        str: A JSON string containing the list of properties with detailed fields (price, area, bedrooms, bathrooms, location, address, images, etc.) and pagination information.

    Example Usage:
        search_properties("Kirkland", "WA", min_price=100000, max_price=200000)
        search_properties("Kirkland", "WA", size=5)
    """
    # Convert string parameters to integers if needed
    try:
        if min_price is not None and isinstance(min_price, str):
            min_price = int(min_price)
        if max_price is not None and isinstance(max_price, str):
            max_price = int(max_price)
        if bedrooms is not None and isinstance(bedrooms, str):
            bedrooms = int(bedrooms)
        if bathrooms is not None and isinstance(bathrooms, str):
            bathrooms = int(bathrooms)
        if size is not None and isinstance(size, str):
            size = int(size)
    except (ValueError, TypeError) as e:
        return "Error: All numeric parameters must be valid numbers"
    response_data = await fetch_properties_from_api(
        city, state, min_price, max_price, bedrooms, bathrooms, cursor, size
    )

    if "error" in response_data:
        return f"Failed to fetch properties: {response_data['error']}"

    properties = response_data.get("data", [])
    if not properties:
        return f"No properties found in {city}, {state} matching your criteria."

    return json.dumps(
        {
            "data": properties,
            "cursor": response_data.get("cursor"),
            "count": len(properties),
            "status": "success",
        },
        indent=2,
    )


# --- Main Execution ---
if __name__ == "__main__":
    mcp.run()
