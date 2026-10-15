"""Shared Streamlit loader and helpers for the StoreSignal AI demo app."""
import json
import sqlite3

import pandas as pd
import streamlit as st

from storesignal.config import ROOT, cfg


@st.cache_data
def load():
    P = ROOT / cfg['paths']['processed']
    rec = pd.read_parquet(P / 'records_scored.parquet')
    rec['ts'] = pd.to_datetime(rec['ts'])
    rec['policy_cats'] = rec['policy_cats'].map(json.loads)
    rec['entities'] = rec['entities'].map(json.loads)
    with open(P / 'alerts.json', encoding='utf-8') as f:
        alerts = json.load(f)
    return rec, alerts


@st.cache_data
def load_metrics():
    mp = ROOT / 'reports' / 'metrics.json'
    if mp.exists():
        with open(mp, encoding='utf-8') as f:
            return json.load(f)
    return None


def banner():
    if cfg.get('data_mode') == 'synthetic':
        st.warning('SYNTHETIC DEMO DATA. Figures on this page are illustrative, '
                   'not measured on the organizers\u2019 dataset.')


def con():
    return sqlite3.connect(ROOT / cfg['paths']['processed'] / 'tracker.sqlite')


def event_history(alert_id):
    import datetime as dt
    c = con()
    rows = c.execute('SELECT ts, actor, from_status, to_status, note FROM events '
                     'WHERE alert_id=? ORDER BY id', (alert_id,)).fetchall()
    if not rows:
        st.caption('No tracker events yet.')
        return
    for ts, actor, frm, to, note in rows:
        st.write('**%s**  %s → %s · %s' % (ts[:16], frm, to, actor))
        if note:
            st.caption(note)
