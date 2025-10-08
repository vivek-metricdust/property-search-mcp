import os
import json
from fastapi import FastAPI, Query, HTTPException, status
import httpx
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from google import genai
from google.genai.types import GenerateContentConfig
from dotenv import load_dotenv

# Load environment variables (API_KEY and others)
load_dotenv()

# --- Gemini Configuration and Helper Functions ---
try:
    # Client will automatically look for the GEMINI_API_KEY or GOOGLE_API_KEY
    client = genai.Client()
    MODEL_NAME = "gemini-2.5-flash"
except Exception as e:
    # Handle environment where client initialization might fail
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

    # Flag to help detect if the query was a search request or a general question
    is_search: bool = Field(
        default=False,
        description="True if the query appears to be a property search request.",
    )


async def extract_search_params(query: str) -> PropertySearchParams:
    """Extract property search parameters from natural language query using Gemini's Structured Output."""
    if client is None:
        return PropertySearchParams()

    try:
        # Define a specific Pydantic model for LLM output including the crucial 'is_search' flag
        class LLMPropertySearchParams(PropertySearchParams):
            is_search: bool = Field(
                description="Set to true if the query is a request to search for property (e.g., 'find a house', 'apartment for sale', 'properties in'). Set to false for greetings, time checks, or general questions."
            )

        config = GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=LLMPropertySearchParams,
        )

        # Prompt instructs the model on default values and the logic for the 'is_search' field
        prompt = f"""Extract property search parameters (city, state, country, min_price, max_price) from the query. 
        Crucially, set 'is_search' to true only if the query is clearly a property search request.

        Default values: city='Seattle', state='WA', country='USA', min_price=null, max_price=null.
        
        Query: {query}"""

        # Get response from Gemini
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[prompt],
            config=config,
        )

        if hasattr(response, "parsed") and response.parsed is not None:
            # We use the parsed object which includes the 'is_search' field
            return response.parsed
        else:
            print(
                f"Warning: Structured output parsing failed. Raw text: {response.text}"
            )
            # Fallback to default, non-search parameters
            return PropertySearchParams(is_search=False)

    except Exception as e:
        print(f"Error extracting parameters from Gemini: {str(e)}")
        # Return default parameters with is_search=False on failure
        return PropertySearchParams(is_search=False)


async def generate_general_response(query: str) -> str:
    """Generate a friendly, general conversational response for non-search queries."""
    if client is None:
        return "Sorry, PAI. I can't access the language model right now to answer your question. I am primarily designed for property search requests."

    prompt = f"""You are a helpful, friendly assistant integrated into a property search API. 
    A user has asked a general question or greeting. Respond concisely and conversationally.
    If the question is about the current time or a non-search topic, politely state that you specialize in property searches.
    
    User Query: '{query}'
    
    Your Response:"""

    try:
        response = client.models.generate_content(model=MODEL_NAME, contents=[prompt])
        return response.text
    except Exception as e:
        print(f"Error generating general response: {str(e)}")
        return "Hello! I am a property search assistant. How can I help you find your next home?"


# --- FastAPI Application ---

app = FastAPI(title="Property API", version="1.0.0")
# The mock/test API endpoint URL
BASE_URL = "https://mz5wkrw9e4.execute-api.us-east-1.amazonaws.com/property_listing_service/prod/public/tenant/shopprop"


async def fetch_properties(
    payload: Optional[Dict[str, Any]] = None, city: str = "seattle", state: str = "wa"
) -> Dict[str, Any]:
    """Fetch properties from the external API."""
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API_KEY environment variable not set. Please check your .env file.",
        )

    headers = {
        "apikey": api_key,
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
        # Re-raise HTTP errors with detailed status code and message
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Error fetching properties from external service: {e.response.text}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during API call: {str(e)}",
        )


@app.get("/properties")
async def get_properties(
    query: str = Query(
        None,
        description="Natural language query for property search or a general question",
    ),
    city: str = Query(None, description="City name to search for properties"),
    state: str = Query(None, description="State code (e.g., 'WA')"),
    country: str = Query(None, description="Country name"),
    min_price: Optional[int] = Query(None, description="Minimum price filter"),
    max_price: Optional[int] = Query(None, description="Maximum price filter"),
):
    """
    Handles property searches based on a natural language query or explicit URL parameters.
    Responds conversationally to non-search queries.
    """

    # 1. Initialize with default parameters
    params = PropertySearchParams(city="Seattle", state="WA", country="USA")
    perform_search = True

    if query:
        # 2. Attempt to extract parameters and intent from the natural language query
        try:
            llm_params = await extract_search_params(query)

            # Check if the LLM determined this was NOT a search request
            if not llm_params.is_search:
                # 3. If it's a general query, generate a conversational response and return immediately
                perform_search = False
                general_response_text = await generate_general_response(query)
                return {"message": general_response_text}

            # If it IS a search, use LLM-extracted values as the base
            params = llm_params

        except Exception as e:
            print(
                f"LLM extraction error: {e}. Falling back to URL parameters/defaults."
            )
            pass  # Continue with default/URL parameters

    # 4. Override LLM-extracted or default values with explicit URL query parameters
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

    # 5. Execute the search
    if perform_search:
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

            if params.min_price is not None:
                payload["min_price"] = params.min_price

            if params.max_price is not None:
                payload["max_price"] = params.max_price

            # Fetch properties with the filtered payload
            response = await fetch_properties(payload, params.city, params.state)
            properties = response.get("data", [])

            # Return search results
            return {
                "message": f"Successfully retrieved {len(properties)} properties in {params.city}, {params.state} with specified filters.",
                "search_parameters": params.model_dump(),
                "length": len(properties),
                "properties": properties,
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing property search: {str(e)}",
            )

    # Fallback response if perform_search was set to False but for some reason
    # the general response was not generated/returned (should be unreachable)
    return {
        "message": "Query intent was unclear. Please try a specific property search or greeting."
    }
