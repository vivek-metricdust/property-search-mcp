python -m venv .venv
.venv\Scripts\activate
pip install fastapi uvicorn
uvicorn main:app --reload --port 8000

npx @modelcontextprotocol/inspector python main.py