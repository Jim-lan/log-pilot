"""Validated dataset identity; fixture setup is deliberately outside execution."""
from shared.evaluation_context import validate_cases


def load_dataset(value):
    if isinstance(value, list):
        return validate_cases(value), {'dataset_format': 1, 'dataset_split': 'legacy_unpartitioned'}
    if not isinstance(value, dict) or type(value.get('schema_version')) is not int or value['schema_version'] != 2:
        raise ValueError('Unsupported dataset format')
    for name in ('dataset_id', 'version'):
        if not isinstance(value.get(name), str) or not 1 <= len(value[name]) <= 128:
            raise ValueError('Missing dataset identity')
    if value.get('split') not in ('development', 'held_out'):
        raise ValueError('Invalid dataset split')
    return validate_cases(value.get('cases')), {
        'dataset_format': 2, 'dataset_id': value['dataset_id'],
        'dataset_version': value['version'], 'dataset_split': value['split']}
