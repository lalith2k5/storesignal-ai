"""Messy-format tests (gate G3): the pipeline must load four copies of the
data with different column names, date formats, encodings and file types."""
import json

import pandas as pd
import pytest

from storesignal.automap import automap
from storesignal.ingest import parse_ts, read_any

STORE_IDS = ['S01', 'S02', 'S03']


def _make_reviews(path):
    df = pd.DataFrame({
        'review_id': ['r1', 'r2', 'r3'],
        'date': ['31/12/2026', '01/01/2027', '02/01/2027'],
        'store': ['S01', 'S02', 'S03'],
        'text': ['very bad service today', 'freezer not cooling, milk warm', 'long queue at billing'],
        'stars': ['1', '2', '3'],
    })
    df.to_csv(path, index=False, encoding='utf-8-sig')


def _make_app(path):
    df = pd.DataFrame({
        'id': ['a1', 'a2', 'a3'],
        'created_at': ['2026-12-31', '2027-01-01', '2027-01-02'],
        'store': ['S01', 'S02', 'S03'],
        'comment': ['app crashes at checkout', 'Müller milch not in stock', 'offer not applied on bill'],
        'rating': ['1', '2', '3'],
    })
    df.to_csv(path, sep='\t', index=False, encoding='latin-1')


def _make_staff(path):
    df = pd.DataFrame({
        'note_id': ['n1', 'n2', 'n3'],
        'time': ['2026-12-31T08:00:00', '2027-01-01T09:30:00', '2027-01-02T10:15:00'],
        'store': ['S01', 'S02', 'S03'],
        'note': ['shift note: freezer thanda nahi kar raha', 'note: shelf pe expired biscuits',
                 'shift note: billing line lambi thi'],
    })
    df.to_excel(path, index=False)


def _make_calls(path):
    rows = [{'ticket_id': 't1', 'opened': '2026-12-31T11:00:00', 'store': 'S01',
             'transcript': 'customer called about: rude billing staff'},
            {'ticket_id': 't2', 'opened': '2027-01-01T12:00:00', 'store': 'S02',
             'transcript': 'customer called about: milk packet leaking'},
            {'ticket_id': 't3', 'opened': '2027-01-02T13:00:00', 'store': 'S03',
             'transcript': 'customer called about: wrong bill amount'}]
    with open(path, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')


@pytest.fixture(scope='module')
def messy(tmp_path_factory):
    base = tmp_path_factory.mktemp('messy')
    files = {
        'online_reviews.csv': _make_reviews,
        'app_comments.tsv': _make_app,
        'staff_notes.xlsx': _make_staff,
        'call_transcripts.jsonl': _make_calls,
    }
    for name, fn in files.items():
        fn(base / name)
    return base


def test_loader_reads_all_four(messy):
    counts = {}
    for name in ['online_reviews.csv', 'app_comments.tsv', 'staff_notes.xlsx',
                 'call_transcripts.jsonl']:
        df = read_any(messy / name)
        counts[name] = len(df)
        assert len(df) == 3
    assert counts


def test_dayfirst_dates_parse(messy):
    df = read_any(messy / 'online_reviews.csv')
    parsed, mode, rate = parse_ts(df['date'])
    assert mode == 'dayfirst'
    assert rate >= 95
    assert parsed.iloc[0].month == 12 and parsed.iloc[1].month == 1


def test_automap_finds_columns(messy):
    for name in ['online_reviews.csv', 'app_comments.tsv', 'staff_notes.xlsx',
                 'call_transcripts.jsonl']:
        m = automap(messy / name, store_ids=STORE_IDS)
        targets = {v['target'] for v in m.values()}
        assert {'ts', 'store_id', 'text_raw'} <= targets, (name, m)
