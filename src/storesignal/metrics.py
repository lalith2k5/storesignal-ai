"""Metrics computed on the team's own data (dev labels and synthetic truth).
Hidden labels are touched only through the organizers' evaluate.py."""
import csv
import datetime as dt
import hashlib
import json
import subprocess

import numpy as np
from sklearn.metrics import classification_report, f1_score


def classification_metrics(y_true, y_pred, meta=None):
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    out = {'macro_f1': float(f1_score(y_true, y_pred, average='macro')),
           'weighted_f1': float(f1_score(y_true, y_pred, average='weighted')),
           'report': classification_report(y_true, y_pred, output_dict=True, zero_division=0)}
    if meta is not None:
        for col in ['channel', 'lang_pattern']:
            if col in meta.columns:
                by = {}
                for g, idx in meta.groupby(col).indices.items():
                    if len(idx) >= 20:
                        by[g] = round(float(f1_score(y_true[idx], y_pred[idx], average='macro')), 4)
                out['by_' + col] = by
    return out


def ece(conf, correct, bins=10):
    conf, correct = np.asarray(conf, dtype=float), np.asarray(correct, dtype=float)
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            total += m.mean() * abs(correct[m].mean() - conf[m].mean())
    return float(total)


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return ((c - h) / d, (c + h) / d)


def accuracy_vs_coverage(p1, correct):
    """Points of the accuracy-versus-coverage curve."""
    p1, correct = np.asarray(p1, dtype=float), np.asarray(correct, dtype=bool)
    pts = []
    for tau in np.arange(0.30, 0.96, 0.05):
        keep = p1 >= tau
        if keep.sum() < 20:
            continue
        pts.append({'tau': round(float(tau), 2), 'coverage': round(float(keep.mean()), 4),
                    'accuracy': round(float(correct[keep].mean()), 4)})
    return pts


def log_run(scores, cfg_obj, path='reports/eval_log.csv'):
    commit = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'],
                            capture_output=True, text=True).stdout.strip()
    cfg_hash = hashlib.md5(json.dumps(cfg_obj, sort_keys=True, default=str).encode()).hexdigest()[:8]
    with open(path, 'a', newline='') as f:
        csv.writer(f).writerow([dt.datetime.now().isoformat(timespec='seconds'), commit,
                                cfg_hash, json.dumps(scores, default=str)])
