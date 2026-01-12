import os
import shutil
import argparse
import time

def ingest_runbook(runbook_name):
    # Source: /data/source/ (User specified)
    source_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/source", runbook_name))
    
    # Target: /data/source/landing_zone/ (Ingestion Worker watches this)
    target_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/source/landing_zone"))
    target_path = os.path.join(target_dir, runbook_name)
    
    if not os.path.exists(source_path):
        print(f"❌ Error: Runbook not found at {source_path}")
        return
        
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)
        
    print(f"🚀 Injecting Knowledge: {runbook_name}")
    print(f"   From: {source_path}")
    print(f"   To:   {target_path}")
    
    shutil.copy2(source_path, target_path)
    print("✅ Runbook copied to landing zone.")
    print("⏳ Waiting for Ingestion Worker to process...")
    
    # Simple spinner
    for _ in range(5):
        time.sleep(1)
        print(".", end="", flush=True)
    print("\n✅ Knowledge Injected! You can now ask the Pilot about this topic.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inject a runbook for the demo.")
    parser.add_argument("--runbook", type=str, required=True, help="Filename of the runbook in data/source/")
    args = parser.parse_args()
    
    ingest_runbook(args.runbook)
