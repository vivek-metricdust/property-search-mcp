python -m venv .venv
.venv\Scripts\activate
pip install fastapi uvicorn
uvicorn main:app --reload --port 8000
mcp-cli dev openapi http://localhost:8000/openapi.json


npx @openapitools/openapi-generator-cli generate -i http://localhost:8000/openapi.json -g python -o ./generated