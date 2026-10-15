"""Train the classifier. Training table = weak labels, with hand labels from
data/labels_dev/dev_labels.csv replacing weak labels for the same records
(and repeated 3x). Model choice is by macro-F1 on the dev set, never by size."""
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedKFold

from . import classify
from .config import ROOT, cfg, load_taxonomy


def _training_table(weak, dev):
    """Dev labels replace weak labels for the same records; dev records are
    added 3x so the hand labels carry weight. Returns (weak, dev)."""
    if dev is None or len(dev) == 0:
        return weak, dev
    dev = dev.dropna(subset=['issue']).copy()
    dev_map = dict(zip(dev['record_id'], dev['issue']))
    weak = weak.copy()
    mask = weak['record_id'].isin(dev_map)
    weak.loc[mask, 'issue'] = weak.loc[mask, 'record_id'].map(dev_map)
    extra = pd.concat([dev] * 3, ignore_index=True)
    extra['confidence'] = 1.0
    extra['source'] = 'hand_label'
    weak = pd.concat([weak, extra], ignore_index=True)
    return weak, dev


def run():
    interim = ROOT / cfg['paths']['interim']
    weak = pd.read_parquet(interim / 'weak_labels.parquet')
    df = pd.read_parquet(interim / 'records_norm.parquet')
    E = np.load(interim / 'embeddings.npy')
    pos = dict(zip(df['record_id'], np.arange(len(df))))
    ids = [it['id'] for it in load_taxonomy()['issues']]

    dev_path = ROOT / 'data' / 'labels_dev' / 'dev_labels.csv'
    dev = pd.read_csv(dev_path) if dev_path.exists() else None
    if dev is not None:
        dev = dev[dev['record_id'].isin(pos)]

    weak, dev = _training_table(weak, dev)
    weak = weak[weak['issue'].isin(ids)].reset_index(drop=True)
    idx = weak['record_id'].map(pos).tolist()
    texts = df.loc[idx, 'text_norm'].tolist()
    Ew = E[idx]
    y = weak['issue'].tolist()

    c = cfg['classifier']
    # Model comparison on the dev set when available (M1 vs M2 vs M3).
    if dev is not None and len(dev) >= 60:
        dev_idx = dev['record_id'].map(pos).tolist()
        dev_texts = df.loc[dev_idx, 'text_norm'].tolist()
        dev_E = E[dev_idx]
        dev_y = dev['issue'].tolist()
        comparisons = []
        for name, u_t, u_e in [('M1-tfidf', True, False), ('M2-emb', False, True), ('M3-hybrid', True, True)]:
            m = classify.fit(texts, Ew, y, use_tfidf=u_t, use_emb=u_e, emb_weight=c['emb_weight'],
                             C=c['C'], max_features=c['max_features'])
            pred = classify.predict(m, dev_texts, dev_E)['issue']
            macro = f1_score(dev_y, pred, average='macro')
            comparisons.append({'model': name, 'dev_macro_f1': round(float(macro), 4)})
        cmp_df = pd.DataFrame(comparisons)
        reports = ROOT / 'reports'
        reports.mkdir(parents=True, exist_ok=True)
        cmp_df.to_csv(reports / 'model_comparison.csv', index=False)
        print('train: model comparison on dev set')
        print(cmp_df.to_string(index=False))
    else:
        print('train: fewer than 60 dev labels -- fitting M3 (hybrid) directly')

    m = classify.fit(texts, Ew, y, use_tfidf=True, use_emb=True, emb_weight=c['emb_weight'],
                     C=c['C'], max_features=c['max_features'])
    tau = c['tau']
    if dev is not None and len(dev) >= 60:
        dev_idx = dev['record_id'].map(pos).tolist()
        dev_texts = df.loc[dev_idx, 'text_norm'].tolist()
        dev_E = E[dev_idx]
        dev_y = pd.Series(dev['issue'].tolist())
        P = classify.predict(m, dev_texts, dev_E)
        for t in np.arange(0.30, 0.96, 0.05):
            keep = P['p1'] >= t
            if keep.sum() < 20:
                continue
            acc = (P.loc[keep, 'issue'].reset_index(drop=True)
                   == dev_y[keep.tolist()].reset_index(drop=True)).mean()
            if acc >= 0.90:
                tau = float(t)
                print(f'train: tau tuned to {tau} (dev accuracy {acc:.3f} on kept records)')
                break

    models = ROOT / 'models'
    models.mkdir(parents=True, exist_ok=True)
    joblib.dump({'model': m, 'tau': tau, 'config': {k: cfg[k] for k in ('classifier', 'weak', 'seed')}},
                models / 'clf.joblib')
    print(f'train: saved models/clf.joblib with tau={tau}, {len(y)} training rows, '
          f'{m["clf"].classes_.shape[0]} classes')
