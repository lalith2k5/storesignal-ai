"""Data profiler (gate G1): tells you in two minutes what an unknown file
looks like. Used on the final day when the organizers' files arrive."""
import json
from pathlib import Path

import pandas as pd

from . import langid
from .config import ROOT, cfg
from .ingest import read_any, parse_ts


def _guess_type(s):
    if s.nunique() / max(len(s.dropna()), 1) >= 0.99 and s.str.len().max() <= 80:
        return 'id'
    if s.str.fullmatch(r'\d{4}-\d{2}-\d{2}.*').mean() > 0.8:
        return 'datetime'
    if pd.to_numeric(s, errors='coerce').notna().mean() > 0.8:
        return 'number'
    if s.str.len().median() > 60:
        return 'long text'
    return 'short text'


def profile_file(path, store_ids=None, max_rows=50000):
    p = Path(path)
    df = read_any(p).head(max_rows)
    info = {'file': p.name, 'rows': len(df), 'columns': []}
    for col in df.columns:
        s = df[col].astype(str)
        cinfo = {'name': col, 'type': _guess_type(s),
                 'missing_pct': round(100 * df[col].isna().mean(), 1),
                 'unique': int(s.nunique()),
                 'samples': s.dropna().unique()[:3].tolist()}
        if cinfo['type'] in ('short text', 'long text'):
            L = s.str.len()
            vc = L.value_counts()
            cinfo['len_pcts'] = {'min': int(L.min()), 'median': int(L.median()),
                                 'p95': int(L.quantile(.95)), 'max': int(L.max())}
            cinfo['most_common_len'] = int(vc.index[0]) if len(vc) else None
            cinfo['emoji_pct'] = round(100 * s.str.contains(r'[\U0001F300-\U0001FAFF]', regex=True).mean(), 1)
            cinfo['native_script_pct'] = round(100 * s.str.contains(r'[\u0900-\u097F\u0B80-\u0BFF]', regex=True).mean(), 1)
            cinfo['non_ascii_pct'] = round(100 * s.str.contains(r'[^\x00-\x7F]', regex=True).mean(), 1)
            cinfo['lang_patterns'] = s.map(langid.lang_pattern).value_counts().to_dict()
            cinfo['exact_dup_pct'] = round(100 * s.duplicated().mean(), 1)
        if cinfo['type'] == 'datetime':
            parsed, mode, rate = parse_ts(df[col])
            cinfo['parse_mode'] = mode
            cinfo['parse_ok_pct'] = rate
            if parsed.notna().any():
                cinfo['min'] = str(parsed.min())
                cinfo['max'] = str(parsed.max())
                cinfo['has_time_of_day'] = bool(parsed.dt.normalize().ne(parsed).any())
        if store_ids is not None:
            cinfo['store_overlap_pct'] = round(100 * s.isin(set(map(str, store_ids))).mean(), 1)
        info['columns'].append(cinfo)
    return info


def run():
    raw = ROOT / cfg['paths']['raw']
    reports = ROOT / 'reports'
    reports.mkdir(parents=True, exist_ok=True)
    store_ids = None
    sm = ROOT / 'data' / 'synthetic' / 'records.parquet'
    if sm.exists():
        store_ids = pd.read_parquet(sm)['store_id']
    files = sorted(raw.glob('*')) if raw.exists() else []
    out = []
    for f in files:
        if f.suffix.lower() in ('.csv', '.tsv', '.xlsx', '.xls', '.json', '.jsonl'):
            try:
                out.append(profile_file(f, store_ids))
            except Exception as e:  # noqa: BLE001
                out.append({'file': f.name, 'error': str(e)})
    if not out:
        print('inspect_data: no files in data/raw/ yet (expected on the final day)')
        return
    with open(reports / 'profile.md', 'w', encoding='utf-8') as f:
        for info in out:
            f.write('## %s\n\n' % info.get('file', ''))
            f.write('rows: %s\n\n' % info.get('rows', '?'))
            for c in info.get('columns', []):
                f.write('- **%s** (%s) missing %s%% unique %d samples %s\n'
                        % (c['name'], c['type'], c['missing_pct'], c['unique'],
                           json.dumps(c['samples'], ensure_ascii=False)))
    print(json.dumps(out, indent=2, default=str))
