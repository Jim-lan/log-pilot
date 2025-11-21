import sys
import os
import shutil

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from shared.utils.template_miner import LogTemplateMiner

def test_drain3_mining():
    print("🧪 Testing Drain3 Integration...")
    
    # Cleanup old state
    if os.path.exists("data/test_drain3_state.bin"):
        os.remove("data/test_drain3_state.bin")

    miner = LogTemplateMiner(persistence_file="data/test_drain3_state.bin", sim_th=0.5)
    
    logs = [
        "Payment processed for user_id=101 amount=50.00",
        "Payment processed for user_id=102 amount=25.00",
        "Login failed for user=admin ip=192.168.1.5",
        "Login failed for user=guest ip=10.0.0.1"
    ]
    
    print("\n📝 Processing Logs:")
    for log in logs:
        template = miner.mine_template(log)
        print(f"   Log: {log}")
        print(f"   Template: {template}")
        
    # Verify Clustering
    # We expect 2 clusters: "Payment processed..." and "Login failed..."
    total_clusters = miner.get_total_clusters()
    print(f"\n🔢 Total Clusters: {total_clusters}")
    
    if total_clusters == 2:
        print("✅ SUCCESS: Correctly identified 2 templates.")
    else:
        print(f"❌ FAILURE: Expected 2 clusters, got {total_clusters}")
        
    # Verify Persistence
    print("\n💾 Verifying Persistence...")
    miner2 = LogTemplateMiner(persistence_file="data/test_drain3_state.bin")
    if miner2.get_total_clusters() == 2:
        print("✅ SUCCESS: State loaded correctly.")
    else:
        print("❌ FAILURE: State failed to load.")

if __name__ == "__main__":
    test_drain3_mining()
