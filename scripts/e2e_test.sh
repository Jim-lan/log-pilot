#!/bin/bash
set -e

echo "🚀 Starting End-to-End Test..."

# 1. Cleanup
echo "🧹 Cleaning up old data..."
rm -rf data/duckdb
rm -rf data/vector_store
rm -rf data/landing_zone/*
mkdir -p data/landing_zone

# 2. Setup Mock Data
echo "📝 Generating mock logs..."
# Create a simple log file
echo "2023-10-27 10:00:01 ERROR auth-service Login failed" > data/landing_zone/auth.log
echo "2023-10-27 10:00:02 INFO auth-service Login success" >> data/landing_zone/auth.log

# 3. Ingestion (Mock)
# In a real run, we'd start the ingestion worker. 
# For this script, we'll assume the Bulk Loader or Ingestion Worker is run manually or via python.
echo "📥 Running Bulk Loader..."
export PYTHONPATH=$PYTHONPATH:.
python3 services/bulk_loader/src/log_loader.py

# 4. Knowledge Base Ingestion
echo "🧠 Ingesting into Knowledge Base..."
# We can use the main.py to ingest sample data or write a script to ingest from DB.
# For now, we'll skip explicit KB ingestion in this script as it requires running the service.

# 5. Run Benchmarks
echo "📊 Running Agent Benchmarks..."
python3 scripts/benchmark_agents.py --agent all

echo "✅ E2E Test Complete!"
