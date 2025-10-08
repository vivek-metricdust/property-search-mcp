import os
import json
import asyncio
import httpx
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

# --- MCP Imports ---
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from pydantic import BaseModel, Field

# Load environment variables (API_KEY)
load_dotenv()

# --- MCP Server Initialization ---
# This line MUST be here to create the 'server' object
server = Server("property-search-mcp")


# --- Pydantic Model for Tool Arguments ---
class PropertySearchParams(BaseModel):
    """Parameters for the property search tool."""

    city: str = Field(description="City name to search in (e.g., 'Seattle')")
    state: str = Field(description="State code (e.g., 'WA')")
    min_price: Optional[int] = Field(None, description="Minimum property price")
    max_price: Optional[int] = Field(None, description="Maximum property price")


# --- Helper Function to Fetch Properties ---
async def fetch_properties_from_api(params: PropertySearchParams) -> Dict[str, Any]:
    """Fetches properties from the external property API."""
    api_key = os.getenv("API_KEY")
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

    BASE_URL = "https://mz5wkrw9e4.execute-api.us-east-1.amazonaws.com/property_listing_service/prod/public/tenant/shopprop"
    api_url = f"{BASE_URL}/city/{params.city.lower()}/state/{params.state.lower()}"

    payload: Dict[str, Any] = {
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


# --- MCP Tool Definitions ---


@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    """Returns the list of available tools to the MCP client."""
    return [
        Tool(
            name="search_properties",
            description="Searches for real estate property listings for sale in a specific city and state. You can filter by minimum and maximum price.",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "The city to search in (e.g., Seattle)",
                    },
                    "state": {
                        "type": "string",
                        "description": "The state code to search in (e.g., WA)",
                    },
                    "min_price": {
                        "type": "integer",
                        "description": "Minimum price filter",
                    },
                    "max_price": {
                        "type": "integer",
                        "description": "Maximum price filter",
                    },
                },
                "required": ["city", "state"],
            },
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handles the execution of a tool when called by the MCP client."""
    if name == "search_properties":
        try:
            params = PropertySearchParams(**arguments)
        except Exception as e:
            return [
                TextContent(type="text", text=f"Error: Invalid arguments provided. {e}")
            ]

        response_data = await fetch_properties_from_api(params)

        if "error" in response_data:
            return [
                TextContent(
                    type="text",
                    text=f"Failed to fetch properties: {response_data['error']}",
                )
            ]

        properties = response_data.get("data", [])
        if not properties:
            return [
                TextContent(
                    type="text",
                    text=f"No properties found in {params.city}, {params.state} matching your criteria.",
                )
            ]

            # Format the results into a readable string for the AI
        result_string = (
            f"Found {len(properties)} properties in {params.city}, {params.state}:\n\n"
        )
        for prop in properties:
            # --- FIX IS HERE ---
            # Get the price value
            price_val = prop.get("price")
            # Check if it's a number, and if so, format it with commas. Otherwise, use 'N/A'.
            formatted_price = (
                f"${price_val:,}" if isinstance(price_val, (int, float)) else "N/A"
            )

            result_string += (
                f"- **{prop.get('address', 'N/A')}**\n"
                f"  - Price: {formatted_price}\n"  # Use the safely formatted price
                f"  - Beds: {prop.get('bedroom', 'N/A')} | Baths: {prop.get('bathroom', 'N/A')}\n"
                f"  - Area: {prop.get('area', 'N/A')} sqft\n"
                f"  - Description: {prop.get('property_descriptor', 'N/A')}\n\n"
            )

        return [TextContent(type="text", text=result_string)]

    return [TextContent(type="text", text=f"Error: Unknown tool '{name}'")]


# --- Main Execution ---
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
