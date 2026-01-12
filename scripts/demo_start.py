import os
import shutil
import subprocess
import time
import sys

# Define Paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
SOURCE_DIR = os.path.join(DATA_DIR, "source")
TARGET_DIR = os.path.join(DATA_DIR, "target")
STATE_DIR = os.path.join(DATA_DIR, "state")
LANDING_ZONE = os.path.join(SOURCE_DIR, "landing_zone")
PROCESSED_DIR = os.path.join(SOURCE_DIR, "processed")

def clean_environment():
    print("🧹 Cleaning up environment...")
    
    # 1. Clean Target DBs (logs.duckdb, history.duckdb, metrics.duckdb)
    if os.path.exists(TARGET_DIR):
        print(f"   Deleting contents of {TARGET_DIR}...")
        for filename in os.listdir(TARGET_DIR):
            file_path = os.path.join(TARGET_DIR, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"   ⚠️ Failed to delete {file_path}. Reason: {e}")

    # 2. Clean State (ChromaDB, Drain3 state)
    if os.path.exists(STATE_DIR):
        print(f"   Deleting contents of {STATE_DIR}...")
        for filename in os.listdir(STATE_DIR):
            file_path = os.path.join(STATE_DIR, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"   ⚠️ Failed to delete {file_path}. Reason: {e}")
                
    # 3. Clean Landing Zones
    for zone in [LANDING_ZONE, PROCESSED_DIR]:
        if os.path.exists(zone):
            print(f"   Cleaning {zone}...")
            for filename in os.listdir(zone):
                # Don't delete .gitkeep if it exists
                if filename == ".gitkeep": continue
                
                file_path = os.path.join(zone, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print(f"   ⚠️ Failed to delete {file_path}. Reason: {e}")
    
    # Re-create directories if they were somehow removed (though we only removed contents)
    os.makedirs(LANDING_ZONE, exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(TARGET_DIR, exist_ok=True)
    os.makedirs(STATE_DIR, exist_ok=True)
    
    print("✅ Environment Cleaned.")

def generate_mock_logs():
    print("🎲 Generating initial mock logs...")
    try:
        # Run scripts/generate_logs.py
        # Assuming arguments: --count 1000 --output data/source/landing_zone/initial_logs.log
        subprocess.run([
            "python3", "scripts/generate_logs.py", 
            "--count", "1000", 
            "--output", os.path.join(LANDING_ZONE, "initial_logs.log")
        ], check=True)
        print("✅ Mock logs generated.")
    except Exception as e:
        print(f"❌ Failed to generate logs: {e}")

def start_services():
    print("🚀 Starting Services...")
    
    services = [
        ("Ingestion Worker", ["python3", "services/ingestion-worker/src/main.py"]),
        ("Sentry Service", ["python3", "services/sentry/src/main.py"]),
        ("Pilot API", ["uvicorn", "services.pilot_orchestrator.src.api:app", "--reload", "--port", "8000"]),
    ]
    
    procs = []
    
    try:
        for name, cmd in services:
            print(f"   Starting {name}...")
            # Use separate process groups so we can kill them easily later? 
            # For simplicity, we just Popen them. User will have to Ctrl+C or we handle it.
            # But the user asked for a script to *start* them. Usually this implies running them.
            # To run all in parallel in one terminal, we need to manage them.
            p = subprocess.Popen(cmd)
            procs.append(p)
            
        print("\n✅ All services started.")
        print("   -> Frontend: Open services/frontend/src/index.html in your browser.")
        print("   -> Press Ctrl+C to stop all services.")
        
        # Wait for all processes
        for p in procs:
            p.wait()
            
    except KeyboardInterrupt:
        print("\n🛑 Stopping services...")
        for p in procs:
            p.terminate()
        print("✅ Services stopped.")

if __name__ == "__main__":
    clean_environment()
    generate_mock_logs()
    start_services()
