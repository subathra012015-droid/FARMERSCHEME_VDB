import os

os.environ["OPENAI_API_KEY"] = "x"
os.environ["PINECONE_API_KEY"] = "x"
os.environ["PINECONE_INDEX_NAME"] = "farmerscheme-vdb"

from backend.main import app
from fastapi.testclient import TestClient

client = TestClient(app)
resp = client.post("/chat", json={"message": "hello", "language": "en"})
print(resp.status_code)
print(resp.text)
