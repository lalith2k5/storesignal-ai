"""Label Tool: hand-label the dev set. Shows the record, never the prediction."""
import pandas as pd
import streamlit as st
import yaml

from common import banner, load
from storesignal.config import ROOT

banner()
rec, _ = load()
tax = yaml.safe_load(open(ROOT / 'config' / 'taxonomy.yaml', encoding='utf-8'))
LAB = ROOT / 'data' / 'labels_dev' / 'dev_labels.csv'
SAMPLE = ROOT / 'data' / 'labels_dev' / 'sample_ids.csv'
if not SAMPLE.exists():
    st.info('data/labels_dev/sample_ids.csv not found. Run '
            '`python -m storesignal.cli label_sample` first.')
    st.stop()

ids = pd.read_csv(SAMPLE)['record_id'].tolist()
done = set(pd.read_csv(LAB)['record_id']) if LAB.exists() else set()
todo = [i for i in ids if i not in done]
st.progress(len(done) / max(len(ids), 1), text='%d of %d labelled' % (len(done), len(ids)))

if todo:
    r = rec[rec['record_id'] == todo[0]].iloc[0]
    st.write('Channel: %s | Store: %s | Rating: %s' % (r['channel'], r['store_id'], r['rating']))
    st.info(r['text_masked'])
    issue = st.selectbox('Issue', [i['id'] for i in tax['issues']])
    sev = st.selectbox('Severity', ['low', 'medium', 'high', 'critical'])
    act = st.checkbox('Actionable')
    if st.button('Save and next'):
        row = pd.DataFrame([{'record_id': r['record_id'], 'issue': issue, 'severity': sev,
                             'actionable': int(act)}])
        LAB.parent.mkdir(parents=True, exist_ok=True)
        row.to_csv(LAB, mode='a', header=not LAB.exists(), index=False)
        st.rerun()
else:
    st.success('All sampled records are labelled.')
