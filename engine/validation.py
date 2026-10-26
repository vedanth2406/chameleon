"""Offline validation of the supplied schema's vocabulary, without dependencies."""
from collections import Counter
from functools import lru_cache
import json
import math
from pathlib import Path


@lru_cache(maxsize=1)
def schema():
    return json.loads((Path(__file__).resolve().parents[1] / 'chameleon_design_schema_v0.9.json').read_text())


def schema_errors(value):
    root = schema()
    errors = []
    types = {'object': lambda v: isinstance(v, dict), 'array': lambda v: isinstance(v, list),
             'string': lambda v: isinstance(v, str), 'null': lambda v: v is None,
             'integer': lambda v: isinstance(v, int) and not isinstance(v, bool),
             'number': lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)}
    def visit(v, spec, path):
        kind = spec.get('type')
        if kind and not any(types[t](v) for t in (kind if isinstance(kind, list) else [kind])):
            errors.append(f'{path}: invalid type (expected {kind})')
            return
        if 'enum' in spec and v not in spec['enum']:
            errors.append(f'{path}: invalid enum')
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            if not math.isfinite(v):
                errors.append(f'{path}: nonfinite number')
            elif ('minimum' in spec and v < spec['minimum']) or ('maximum' in spec and v > spec['maximum']):
                errors.append(f'{path}: out of range')
        if isinstance(v, dict):
            for field in spec.get('required', []):
                if field not in v:
                    errors.append(f'{path}: missing {field}')
            properties = spec.get('properties', {})
            if spec.get('additionalProperties') is False:
                for field in v.keys() - properties.keys():
                    errors.append(f'{path}: unexpected {field}')
            for field, sub in properties.items():
                if field in v:
                    resolved(v[field], sub, f'{path}.{field}')
            for rule in spec.get('allOf', []):
                conditions = rule.get('if', {}).get('properties', {})
                if all(k in v and v[k] == s.get('const') for k, s in conditions.items()):
                    resolved(v, rule['then'], path)
        if isinstance(v, list):
            if len(v) < spec.get('minItems', 0):
                errors.append(f'{path}: too few items')
            for i, item in enumerate(v):
                resolved(item, spec.get('items', {}), f'{path}[{i}]')
    def resolved(v, spec, path):
        if '$ref' in spec:
            ref = spec['$ref']
            spec = root
            for part in ref.split('/')[1:]:
                spec = spec[part]
        visit(v, spec, path)
    resolved(value, root, 'design')
    return errors


def validate_source(source, target):
    errors = schema_errors(source)
    elements = source.get('elements', []) if isinstance(source, dict) else []
    errors.extend(schema_errors({'canvas': target, 'elements': elements}))
    if not errors:
        counts = Counter(e['id'] for e in source['elements'])
        if any(n != 1 for n in counts.values()):
            errors.append('source IDs must be unique')
        for e in source['elements']:
            if e['width'] <= 0 or e['height'] <= 0:
                errors.append(f"{e['id']}: positive box dimensions required")
    if errors:
        raise ValueError('; '.join(dict.fromkeys(errors)))
