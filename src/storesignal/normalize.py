"""Text normalization: keep signals, never erase negation."""
import re
import unicodedata
from collections import Counter

import emoji
import pandas as pd
import yaml

from .config import ROOT, cfg
from .langid import lang_pattern
from .pii import mask_pii

_N = yaml.safe_load(open(ROOT / 'config' / 'normalization.yaml', encoding='utf-8'))
_ABBR = _N['abbreviations']
_VAR = {v: canon for canon, vs in _N['variants'].items() for v in vs}
_REPEAT = re.compile(r'(.)\1{2,}')
_TOKEN = re.compile(r"[\w']+|[^\w\s]")


def normalize(text):
    t = unicodedata.normalize('NFKC', str(text))
    t = emoji.demojize(t, delimiters=(' emoji_', ' '))
    t = _REPEAT.sub(r'\1\1', t.lower())
    out = []
    for w in _TOKEN.findall(t):
        w = _VAR.get(w, w)
        out.append(_ABBR.get(w, w))
    return ' '.join(out)


def _truncation_caps(df):
    """Per channel, if the most common exact text length covers >= 1% of rows
    and is >= 100 chars, treat it as a truncation cap."""
    caps = {}
    for ch, idx in df.groupby('channel').indices.items():
        vc = df.loc[idx, 'text_raw'].astype(str).str.len().value_counts()
        if len(vc) == 0:
            continue
        top_len, top_count = int(vc.index[0]), int(vc.iloc[0])
        if top_len >= 100 and top_count >= max(1, 0.01 * len(idx)):
            caps[ch] = top_len
    return caps


def run():
    interim = ROOT / cfg['paths']['interim']
    df = pd.read_parquet(interim / 'records.parquet')
    df['text_masked'] = df['text_raw'].astype(str).map(mask_pii)
    df['text_norm'] = df['text_masked'].map(normalize)
    df['lang_pattern'] = df['text_norm'].map(lang_pattern)

    caps = _truncation_caps(df)
    flags = pd.Series(False, index=df.index)
    for ch, idx in df.groupby('channel').indices.items():
        t = df.loc[idx, 'text_raw'].astype(str)
        m = t.str.rstrip().str.endswith('...')
        cap = caps.get(ch)
        if cap:
            m = m | (t.str.len() >= cap - 1)
        flags.loc[idx] = m
    df['is_truncated'] = flags

    df = df.sort_values(['ts', 'record_id'], na_position='last', kind='stable').reset_index(drop=True)
    df.to_parquet(interim / 'records_norm.parquet')

    # Grow the normalization dictionary from evidence: the 400 most frequent
    # tokens that are not already in the dictionary.
    known = set(_ABBR) | set(_VAR) | set(_VAR.values())
    cnt = Counter(w for t in df['text_norm'] for w in t.split())
    unknown = [(w, c) for w, c in cnt.most_common(1500) if w not in known][:400]
    reports = ROOT / cfg['paths']['reports']
    reports.mkdir(parents=True, exist_ok=True)
    with open(reports / 'unknown_tokens.txt', 'w', encoding='utf-8') as f:
        f.write('# 400 most frequent tokens not in config/normalization.yaml\n')
        f.write('# Group spelling variants by eye and add them to the variants block.\n')
        for w, c in unknown:
            f.write(f'{c}\t{w}\n')
    print(f'normalize: {len(df)} rows, truncation caps {caps}, '
          f'{len(unknown)} unknown tokens written to reports/unknown_tokens.txt')
