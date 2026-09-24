"""Inspect recovery metadata without initializing the worker, models or databases."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.ingestion_inspection import inspect_ingestion

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', default='data')
    parser.add_argument('--limit', type=int, default=100)
    args = parser.parse_args()
    print(json.dumps(inspect_ingestion(args.data_dir, args.limit), indent=2))
