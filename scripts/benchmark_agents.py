import argparse
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from services.evaluator.src.runner import EvalRunner

def main():
    parser = argparse.ArgumentParser(description="Run LogPilot Agent Benchmarks")
    parser.add_argument("--agent", choices=["schema", "sql", "all"], default="all", help="Agent to evaluate")
    args = parser.parse_args()

    runner = EvalRunner()
    
    if args.agent in ["schema", "all"]:
        df = runner.evaluate_schema_discovery()
        print("\n📊 Schema Discovery Results:")
        print(df)
        print(f"Average Score: {df['score'].mean():.2f}")

    if args.agent in ["sql", "all"]:
        df = runner.evaluate_sql_gen()
        print("\n📊 SQL Generation Results:")
        print(df)
        print(f"Average Score: {df['score'].mean():.2f}")

if __name__ == "__main__":
    main()
