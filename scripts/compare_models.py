#!/usr/bin/env python3
"""Start or inspect a persisted model comparison; never auto-promote a model."""
import argparse
import json
from pathlib import Path
import requests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api-url', default='http://localhost:8002')
    parser.add_argument('--profiles', nargs='+')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--data-revision')
    parser.add_argument('--min-pass-rate', type=float)
    parser.add_argument('--max-error-rate', type=float)
    parser.add_argument('--max-p95-seconds', type=float)
    parser.add_argument('--comparison-id')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.output.parent.is_dir():
        parser.error('Output directory does not exist')
    if args.output.exists():
        parser.error('Output exists; choose a new path to preserve the earlier report')
    if args.comparison_id:
        response = requests.get(args.api_url.rstrip('/') + '/evaluate/comparisons/' + args.comparison_id, timeout=30)
    else:
        if not args.profiles or not args.data_revision:
            parser.error('--profiles and --data-revision are required when starting a comparison')
        payload = {key: getattr(args, key) for key in ('profiles', 'repeats', 'limit', 'data_revision',
                   'min_pass_rate', 'max_error_rate', 'max_p95_seconds') if getattr(args, key) is not None}
        response = requests.post(args.api_url.rstrip('/') + '/evaluate/compare', json=payload, timeout=30)
    response.raise_for_status()
    value = response.json()
    with args.output.open('x') as handle:
        json.dump(value, handle, indent=2)
        handle.write('\n')
    print(json.dumps({'comparison_id': value['comparison_id'], 'output': str(args.output)}, indent=2))


if __name__ == '__main__':
    main()
