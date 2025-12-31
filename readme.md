python -m venv .venv
.venv\Scripts\activate
pip install fastapi uvicorn
uvicorn main:app --reload --port 8000

npx @modelcontextprotocol/inspector python property-search-mcp.py

pip install mcp aiohttp

python property-search-mcp.py --transport sse --port 8000
