#!/bin/bash
set -e

echo "🚀 Starting LogPilot Demo Restart..."

# 1. Reset Environment (Clean + Generate Mock Data)
echo "-----------------------------------"
echo "🧹 Step 1: Resetting Environment..."
# Pass all arguments (e.g., --count 5000) to reset_demo.py
python3 scripts/reset_demo.py "$@"

# 2. Bulk Load into DuckDB
echo "-----------------------------------"
echo "📥 Step 2: Loading Data into DuckDB..."
python3 services/bulk-loader/src/log_loader.py

# 3. Ingest into Knowledge Base
echo "-----------------------------------"
echo "🧠 Step 3: Populating Knowledge Base..."
python3 scripts/ingest_kb.py

echo "-----------------------------------"
echo "✅ Demo Environment Ready!"
echo "👉 Run the API: python3 services/api_gateway/src/main.py"
