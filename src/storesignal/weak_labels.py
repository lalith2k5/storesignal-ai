"""Weak supervision (Scenario B): keyword votes + embedding prototype votes
produce pseudo-labels when no labeled sample is provided."""
import re

import numpy as np
import pandas as pd

from . import embed
from .config import ROOT, cfg, load_taxonomy


def _compile(kw):
    """Whole-word match; a trailing * means 'starts with' (matches inflections)."""
    kw = str(kw).lower()
    if kw.endswith('*'):
        return re.compile(r'\b' + re.escape(kw[:-1]) + r'\w*')
    return re.compile(r'\b' + re.escape(kw) + r'\b')


def keyword_votes(texts, issues):
    V = np.zeros((len(texts), len(issues)), dtype='float32')
    for j, it in enumerate(issues):
        pat = re.compile('|'.join(_compile(k).pattern for k in it['seed_keywords']))
        V[:, j] = [len(pat.findall(t)) for t in texts]
    return V


def prototype_scores(E, model, issues):
    protos = []
    for it in issues:
        P = embed.embed([it['description']] + list(it.get('example_texts', [])), model, batch=8)
        c = P.mean(axis=0)
        protos.append(c / np.linalg.norm(c))
    return E @ np.stack(protos).T  # cosine, shape (records, issues)


def softmax(z):
    z = np.exp(z - z.max(axis=1, keepdims=True))
    return z / z.sum(axis=1, keepdims=True)


def weak_labels(V, S, w_kw=1.0, w_emb=2.0, temp=50.0):
    kw = V / (V.sum(axis=1, keepdims=True) + 1e-6)
    emb = softmax(S * temp)
    has_kw = (V.sum(axis=1) > 0).astype('float32')
    denom = (w_kw * has_kw + w_emb)[:, None]
    score = (w_kw * kw + w_emb * emb) / denom
    return score.argmax(axis=1), score.max(axis=1)


def run():
    interim = ROOT / cfg['paths']['interim']
    tax = load_taxonomy()
    issues = tax['issues']
    ids = [it['id'] for it in issues]
    E = np.load(interim / 'embeddings.npy')
    df = pd.read_parquet(interim / 'records_norm.parquet')
    texts = df['text_norm'].tolist()

    V = keyword_votes(texts, issues)
    model = embed.get_model()
    S = prototype_scores(E, model, issues)
    w = cfg['weak']
    labels, conf = weak_labels(V, S, w_kw=w['w_kw'], w_emb=w['w_emb'], temp=w['temp'])

    kw_arg = V.argmax(axis=1)
    emb_arg = S.argmax(axis=1)
    source = np.where((kw_arg == labels) & (emb_arg == labels), 'both',
                      np.where(kw_arg == labels, 'keyword', 'embedding'))

    wl = pd.DataFrame({
        'record_id': df['record_id'],
        'issue': [ids[i] for i in labels],
        'confidence': conf.round(4),
        'source': source,
    })
    keep = (wl['confidence'] >= w['min_conf'])
    kept = wl[keep].copy()
    kept = kept.sort_values('confidence', ascending=False).groupby('issue', sort=False).head(w['cap_per_class'])
    kept.to_parquet(interim / 'weak_labels.parquet')

    counts = kept['issue'].value_counts().reindex(ids).fillna(0).astype(int)
    print('weak_labels: kept %d of %d records' % (len(kept), len(wl)))
    for iid, c in counts.items():
        warn = '  <-- fewer than 30 examples: add keywords or examples' if c < 30 else ''
        print(f'  {iid:24s} {c:6d}{warn}')

    # On synthetic data, reporting accuracy against the generator's own truth
    # is legitimate (it is the team's own label, tagged SYNTHETIC).
    truth_path = ROOT / cfg['paths']['raw'].replace('raw', 'synthetic') / 'truth.parquet'
    if cfg.get('data_mode') == 'synthetic' and truth_path.exists():
        truth = pd.read_parquet(truth_path)
        m = wl.merge(truth, on='record_id', how='inner')
        acc = (m['issue'] == m['true_issue']).mean()
        print(f'weak_labels: accuracy vs synthetic truth = {acc:.3f}  [SYNTHETIC]')
