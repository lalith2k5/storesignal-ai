"""Semantic safety net: catches spellings the regex policy rules miss.
Flags go to the review queue only; they are never auto-escalated."""
import numpy as np
import pandas as pd
import yaml

from . import embed
from .config import ROOT, cfg


def semantic_flags(E, texts, percentile=99.5, skip_rows=None):
    """Return a DataFrame with semantic_flag, semantic_category, semantic_sim.
    skip_rows: boolean array of rows already regex-flagged (not re-flagged)."""
    spec = yaml.safe_load(open(ROOT / 'config' / 'safety_prototypes.yaml', encoding='utf-8'))
    model = embed.get_model()
    best_cat = np.full(len(E), '', dtype=object)
    best_sim = np.zeros(len(E), dtype='float32')
    for cat, sents in spec['categories'].items():
        P = embed.embed(sents, model, batch=8)
        sim = (E @ P.T).max(axis=1)
        thr = np.percentile(sim, percentile)
        hit = sim >= thr
        if skip_rows is not None:
            hit = hit & ~np.asarray(skip_rows)
        better = hit & (sim > best_sim)
        best_cat[better] = cat
        best_sim = np.maximum(best_sim, sim * hit)
    return pd.DataFrame({'semantic_flag': best_cat != '',
                         'semantic_category': best_cat,
                         'semantic_sim': best_sim.round(4)})
