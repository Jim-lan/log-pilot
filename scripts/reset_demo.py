import os
import shutil
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from scripts.generate_logs import generate_logs

import argparse

def reset_environment():
    parser = argparse.ArgumentParser(description="Reset LogPilot Demo Environment")
    parser.add_argument("--count", type=int, default=2000, help="Number of mock logs to generate")
    args = parser.parse_args()

    print(f"🧹 Starting Environment Reset (Generating {args.count} logs)...")
    
    # 1. Define paths to clean
    paths_to_clean = [
        "data/target/logs.duckdb",
        "data/target/vector_store",
        "data/source/landing_zone",
        "data/state/drain3_state.bin"
    ]
    
    # 2. Clean up
    for path in paths_to_clean:
        if os.path.exists(path):
            print(f"   Removing {path}...")
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        else:
            print(f"   Skipping {path} (Not found)")
            
    # 3. Re-create Landing Zone
    os.makedirs("data/source/landing_zone", exist_ok=True)
    print("   Created empty data/source/landing_zone/")
    
    # 4. Generate Mock Data
    print("\n📝 Generating Fresh Mock Data...")
    generate_logs(output_dir="data/source/landing_zone", count=args.count)
    
    print("\n✅ Environment Reset Complete!")
    print("👉 Next Steps:")
    print("   1. Run Ingestion: python3 services/ingestion-worker/src/main.py")
    print("   2. Run API:       python3 services/api_gateway/src/main.py")

if __name__ == "__main__":
    reset_environment()
