@echo off
python property-search-mcp.py --transport sse --port 8000 --path /property-search > server_v3.log 2>&1
pause
