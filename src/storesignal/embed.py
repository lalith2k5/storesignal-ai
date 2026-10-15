"""Sentence embeddings for cross-language meaning. Runs once and is cached."""
import hashlib
import json

import numpy as np
import pandas as pd
import torch
from sentence_transformers import SentenceTransformer

from .config import ROOT, cfg


def get_model(name=None, device=None):
    name = name or cfg['embedding_model']
    if device is None:
        device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    try:
        return SentenceTransformer(name, device=device)
    except Exception:
        return SentenceTransformer(name, device='cpu')


def embed(texts, model, batch=64):
    prefix = cfg.get('embedding_prefix', 'query: ')
    try:
        X = model.encode([prefix + t for t in texts], batch_size=batch,
                         normalize_embeddings=True, show_progress_bar=True)
    except Exception:
        # MPS can fail on some ops; fall back to CPU.
        model = SentenceTransformer(cfg['embedding_model'], device='cpu')
        X = model.encode([prefix + t for t in texts], batch_size=batch,
                         normalize_embeddings=True, show_progress_bar=True)
    return np.asarray(X, dtype='float32')


def run():
    interim = ROOT / cfg['paths']['interim']
    df = pd.read_parquet(interim / 'records_norm.parquet')
    texts = df['text_norm'].fillna('empty').tolist()
    h = hashlib.md5('\n'.join(texts).encode('utf-8')).hexdigest()[:16]
    meta_path = interim / 'embeddings_meta.json'
    emb_path = interim / 'embeddings.npy'
    if meta_path.exists() and emb_path.exists():
        meta = json.load(open(meta_path, encoding='utf-8'))
        if meta.get('text_hash') == h:
            print(f"embed: cache hit ({meta['rows']} rows, dim {meta['dim']}), skipping")
            return
    model = get_model()
    E = embed(texts, model)
    np.save(emb_path, E)
    json.dump({'model': cfg['embedding_model'], 'dim': int(E.shape[1]),
               'rows': int(E.shape[0]), 'text_hash': h},
              open(meta_path, 'w', encoding='utf-8'), indent=2)
    print(f'embed: {E.shape[0]} rows x {E.shape[1]} dims saved')
