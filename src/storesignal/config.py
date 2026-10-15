"""Central configuration loading."""
from pathlib import Path

import yaml

# Project root = two levels above this file (src/storesignal/config.py).
ROOT = Path(__file__).resolve().parents[2]


def load_cfg():
    with open(ROOT / 'config' / 'config.yaml', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_yaml(name):
    with open(ROOT / 'config' / name, encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_taxonomy():
    return load_yaml('taxonomy.yaml')


def load_routes():
    return load_yaml('routing.yaml')


def load_policy():
    return load_yaml('policy_rules.yaml')


def load_entities():
    return load_yaml('entities.yaml')


cfg = load_cfg()
