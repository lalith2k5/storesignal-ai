"""Safety-first policy engine. Runs on every record, before deduplication and
before any model threshold. Nothing downstream can switch it off."""
import re

import yaml

from .config import ROOT


def _compile(p):
    p = p.lower()
    if p.endswith('*'):
        return re.compile(r'\b' + re.escape(p[:-1]) + r'\w*')
    return re.compile(r'\b' + re.escape(p) + r'\b')


class PolicyEngine:
    def __init__(self, path=None):
        spec = yaml.safe_load(open(path or ROOT / 'config' / 'policy_rules.yaml', encoding='utf-8'))
        self.neg = set(spec['negation_cues'])
        self.spec = spec
        self.cats = {c: {**v, 'rx': [(_compile(p), p) for p in v['patterns']]}
                     for c, v in spec['categories'].items()}

    def scan(self, text_norm):
        hits = []
        for cat, v in self.cats.items():
            for rx, pat in v['rx']:
                for m in rx.finditer(text_norm):
                    before = text_norm[:m.start()].split()[-3:]
                    after = text_norm[m.end():].split()[:2]  # Hindi/Marathi/Tamil negate after the noun
                    negated = any(w in self.neg for w in before + after)
                    hits.append({'category': cat, 'pattern': pat, 'span': m.group(0), 'negated': negated})
        return hits
