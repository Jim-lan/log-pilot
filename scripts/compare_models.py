import sys
import os
import pandas as pd

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from services.evaluator.src.runner import EvalRunner

def run_comparison():
    print("⚖️  Starting Model Comparison: Local (M4) vs. Cloud (OpenAI/Gemini)\n")
    
    # 1. Run Cloud Evaluation
    print("☁️  Running Cloud Evaluation...")
    cloud_runner = EvalRunner(provider="openai")
    cloud_results = cloud_runner.evaluate_schema_discovery()
    cloud_score = cloud_results["score"].mean()
    print(f"   Cloud Score: {cloud_score:.2f}")

    # 2. Run Local Evaluation
    print("\n💻 Running Local Evaluation...")
    local_runner = EvalRunner(provider="local")
    local_results = local_runner.evaluate_schema_discovery()
    local_score = local_results["score"].mean()
    print(f"   Local Score: {local_score:.2f}")
    
    # 3. Compare
    print("\n📊 Final Comparison:")
    print(f"   Cloud: {cloud_score:.2f}")
    print(f"   Local: {local_score:.2f}")
    
    diff = cloud_score - local_score
    if diff > 0.1:
        print("   👉 Recommendation: Use Cloud for complex tasks.")
    elif diff < -0.1:
        print("   👉 Recommendation: Local is surprisingly better!")
    else:
        print("   👉 Recommendation: Local is good enough (and cheaper/faster).")

if __name__ == "__main__":
    run_comparison()
