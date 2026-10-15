"""Safety-first policy engine. Runs on every record, before deduplication and
before any model threshold. Nothing downstream can switch it off."""
from rapidfuzz import fuzz
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
        # Context negations: word-level cues that suppress a match.
        # e.g. "gluten free section" is wayfinding, not a mislabel;
        # "coupon expired" is a promo problem, not spoiled food.
        ctx = spec.get('context_negations') or {}
        self.ctx_window = int(ctx.get('window_words', 3))
        self.ctx_cues = {k.lower(): [w.lower() for w in v]
                         for k, v in (ctx.get('cues') or {}).items()}
        self.ctx_thr = 85  # fuzzy ratio for typo tolerance (secton ~ section)

    def _context_negated(self, matched_word, before_words, after_words):
        cues = self.ctx_cues.get(matched_word)
        if not cues:
            return False
        for w in before_words + after_words:
            for c in cues:
                if fuzz.ratio(w, c) >= self.ctx_thr:
                    return True
        return False

    def scan(self, text_norm):
        hits = []
        for cat, v in self.cats.items():
            for rx, pat in v['rx']:
                for m in rx.finditer(text_norm):
                    before = text_norm[:m.start()].split()[-3:]
                    after = text_norm[m.end():].split()[:2]  # Hindi/Marathi/Tamil negate after the noun
                    negated = any(w in self.neg for w in before + after)
                    if not negated:
                        ctx_before = text_norm[:m.start()].split()[-self.ctx_window:]
                        ctx_after = text_norm[m.end():].split()[:self.ctx_window]
                        if self._context_negated(m.group(0).lower(), ctx_before, ctx_after):
                            negated = True
                    hits.append({'category': cat, 'pattern': pat, 'span': m.group(0), 'negated': negated})
        return hits
