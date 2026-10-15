"""Build data/labels_dev/sample_ids.csv for the Label Tool: 12-15 records per
weak-label category spread across channels, plus random and policy-hit records."""
import pandas as pd

from .config import ROOT, cfg


def run():
    interim = ROOT / cfg['paths']['interim']
    processed = ROOT / cfg['paths']['processed']
    weak = pd.read_parquet(interim / 'weak_labels.parquet')
    rec = pd.read_parquet(processed / 'records_scored.parquet')
    out_dir = ROOT / 'data' / 'labels_dev'
    out_dir.mkdir(parents=True, exist_ok=True)

    ids = []
    per_class = weak.groupby('issue', group_keys=False).apply(
        lambda g: g.sample(min(14, len(g)), random_state=cfg['seed']), include_groups=False)
    ids += per_class['record_id'].tolist()
    ids += rec.sample(60, random_state=cfg['seed'])['record_id'].tolist()
    ids += rec[rec['policy_flag']].sample(min(60, int(rec['policy_flag'].sum())),
                                          random_state=cfg['seed'])['record_id'].tolist()
    ids = pd.Series(ids).drop_duplicates().sample(frac=1, random_state=cfg['seed']).tolist()
    pd.DataFrame({'record_id': ids}).to_csv(out_dir / 'sample_ids.csv', index=False)
    print('make_sample_ids: %d records sampled for the Label Tool' % len(ids))
