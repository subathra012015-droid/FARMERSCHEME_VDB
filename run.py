#!/usr/bin/env python
"""
One-command startup script for FarmerScheme VDB chatbot.
Runs data ingestion, backend (FastAPI), and frontend (Streamlit) together.
"""

import os
import sys
import subprocess
import time
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
PROJECT_ROOT = Path(__file__).resolve().parent
env_file = PROJECT_ROOT / ".env"

if not env_file.exists():
    print("❌ ERROR: .env file not found!")
    print("   Please create .env with your API keys. See .env.example for template.")
    sys.exit(1)

load_dotenv(env_file)

# Validate API keys
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")
PINECONE_KEY = os.environ.get("PINECONE_API_KEY")
PINECONE_INDEX = os.environ.get("PINECONE_INDEX_NAME", "farmerscheme-db")

if not OPENAI_KEY or OPENAI_KEY == "sk-...your-key-here...":
    print("❌ ERROR: OPENAI_API_KEY not configured in .env")
    sys.exit(1)

if not PINECONE_KEY or PINECONE_KEY == "...your-key-here...":
    print("❌ ERROR: PINECONE_API_KEY not configured in .env")
    sys.exit(1)

print("✅ API keys loaded successfully")
print(f"   OpenAI: {OPENAI_KEY[:20]}...")
print(f"   Pinecone: {PINECONE_KEY[:20]}...")
print(f"   Index: {PINECONE_INDEX}")


def install_requirements():
    """Install dependencies if needed."""
    requirements_file = PROJECT_ROOT / "requirements.txt"
    print("\n📦 Checking dependencies...")
    try:
        import pinecone
        import fastapi
        import streamlit

        print("✅ All dependencies already installed")
        return
    except ImportError:
        print("⏳ Installing dependencies...")
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-q",
                "-r",
                str(requirements_file),
            ],
            check=True,
        )
        print("✅ Dependencies installed")


def run_data_ingestion():
    """Populate Pinecone with scheme data."""
    ingest_script = PROJECT_ROOT / "ingest" / "embed_and_upsert.py"
    data_file = PROJECT_ROOT / "data" / "all_records.json"

    if not ingest_script.exists():
        print("⚠️  Warning: embed_and_upsert.py not found, skipping data ingestion")
        return

    if not data_file.exists():
        print("⚠️  Warning: data/all_records.json not found, skipping data ingestion")
        print("   To enable: Place all_records.json in data/ folder or run scrapers")
        return

    print("\n📚 Checking Pinecone index...")
    try:
        from pinecone import Pinecone

        pc = Pinecone(api_key=PINECONE_KEY)
        index = pc.Index(PINECONE_INDEX)
        stats = index.describe_index_stats()
        total_vectors = stats.total_vector_count

        if total_vectors > 0:
            print(f"✅ Pinecone index already populated ({total_vectors} vectors)")
            return
    except Exception as e:
        print(f"⚠️  Could not check index: {e}")
        print(
            f"   Make sure you created the '{PINECONE_INDEX}' index in Pinecone dashboard"
        )
        return

    print("⏳ Running data ingestion... (this may take 2-5 minutes)")
    try:
        subprocess.run(
            [sys.executable, str(ingest_script)],
            cwd=str(PROJECT_ROOT),
            check=True,
        )
        print("✅ Data ingestion complete")
    except subprocess.CalledProcessError as e:
        print(f"❌ Data ingestion failed: {e}")
        print("   Continuing anyway... (you may see empty responses)")


def run_backend():
    """Start FastAPI backend on port 8000."""
    print("\n🚀 Starting FastAPI backend on http://127.0.0.1:8000")
    print("   Press Ctrl+C in the backend terminal to stop it")
    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--reload",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        cwd=str(PROJECT_ROOT),
    )


def run_frontend():
    """Start Streamlit frontend on port 8501."""
    print("\n🎨 Starting Streamlit frontend on http://localhost:8501")
    print("   Your browser should open automatically")
    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(PROJECT_ROOT / "frontend" / "app.py"),
            "--server.port=8501",
            "--server.address=localhost",
        ],
    )


def main():
    """Run everything."""
    print("=" * 60)
    print("  🌾 FarmerScheme VDB - Full Stack Startup")
    print("=" * 60)

    # Step 1: Install dependencies
    install_requirements()

    # Step 2: Run data ingestion
    run_data_ingestion()

    # Step 3: Start backend
    run_backend()

    # Step 4: Wait a moment for backend to start
    time.sleep(3)

    # Step 5: Start frontend
    run_frontend()

    print("\n" + "=" * 60)
    print("✅ Everything is running!")
    print("=" * 60)
    print("\n📱 Frontend: http://localhost:8501")
    print("🔌 Backend:  http://127.0.0.1:8000")
    print("📖 Docs:     http://127.0.0.1:8000/docs")
    print("\n💡 Tips:")
    print("   - Check backend terminal for API logs")
    print("   - Type a question in Streamlit to test")
    print("   - Press Ctrl+C to stop both servers")
    print("\n" + "=" * 60)

    # Keep running until interrupted
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down...")
        sys.exit(0)


if __name__ == "__main__":
    main()
