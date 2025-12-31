import json
import os
import urllib.request
import urllib.parse
import logging

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# --- Configuration (Populated from Environment Variables) ---
API_BASE_URL = "https://mz5wkrw9e4.execute-api.us-east-1.amazonaws.com/property_listing_service/prod/public"
TENANT = os.environ.get("TENANT", "shopprop")
API_KEY = os.environ.get("API_KEY")


def lambda_handler(event, context):
    """
    AWS Lambda handler to search for properties.
    Supports both GET (query parameters) and POST (JSON body).
    """
    logger.info(f"Received event: {json.dumps(event)}")

    # 1. Check for API Key
    if not API_KEY:
        return {
            "statusCode": 500,
            "body": json.dumps(
                {"error": "API_KEY environment variable not set on Lambda."}
            ),
        }

    # 2. Extract Search Parameters
    params = {}

    # Check Query String (GET)
    if event.get("queryStringParameters"):
        params.update(event["queryStringParameters"])

    # Check Body (POST)
    if event.get("body"):
        try:
            body = json.loads(event["body"])
            params.update(body)
        except json.JSONDecodeError:
            pass

    city = params.get("city")
    state = params.get("state")

    if not city or not state:
        return {
            "statusCode": 400,
            "body": json.dumps(
                {
                    "error": "Missing required parameters: 'city' and 'state' are required."
                }
            ),
        }

    # 3. Prepare external API request
    try:
        # Construct URL
        api_path = f"/tenant/{TENANT}/city/{city.lower()}/state/{state.lower()}"
        full_url = f"{API_BASE_URL}{api_path}"

        # Prepare Headers
        headers = {
            "apikey": API_KEY,
            "company": TENANT,
            "tenant": TENANT,
            "Content-Type": "application/json",
            "user": "lambda-user",
        }

        # Prepare Payload (Default values from OpenAPI spec)
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
                "address",
                "image_urls",
                "last_updated_time",
            ],
            "image_count": 10,
            "size": int(params.get("size", 10)),
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
        }

        # Add optional filters
        if "min_price" in params:
            payload["min_price"] = int(params["min_price"])
        if "max_price" in params:
            payload["max_price"] = int(params["max_price"])
        if "bedrooms" in params:
            payload["bedroom"] = int(params["bedrooms"])
        if "bathrooms" in params:
            payload["bathroom"] = int(params["bathrooms"])
        if "cursor" in params:
            payload["cursor"] = params["cursor"]

        # 4. Execute HTTP Post
        req = urllib.request.Request(
            full_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=25) as response:
            status = response.getcode()
            response_body = response.read().decode("utf-8")
            data = json.loads(response_body)

            # 5. Format and Return Response
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(
                    {
                        "data": data.get("data", []),
                        "cursor": data.get("cursor"),
                        "count": len(data.get("data", [])),
                        "status": "success",
                    },
                    indent=2,
                ),
            }

    except urllib.error.HTTPError as e:
        error_msg = e.read().decode("utf-8")
        logger.error(f"API Error: {e.code} - {error_msg}")
        return {
            "statusCode": e.code,
            "body": json.dumps({"error": f"Upstream API Error: {error_msg}"}),
        }
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Internal Server Error: {str(e)}"}),
        }
