"""Model & Trust: every value carries its source tag, or NOT RUN."""
import json

import pandas as pd
import streamlit as st

from common import banner, load_metrics
from storesignal.config import ROOT, cfg

banner()
st.title('Model & Trust')
st.caption('Real evaluation values only after running the actual evaluation. Placeholders '
           'are shown as NOT RUN; anything computed on synthetic data carries a SYNTHETIC tag.')

m = load_metrics()
if m is None:
    st.warning('reports/metrics.json not found. Run `python -m storesignal.cli evaluate` '
               'to compute metrics on the team\u2019s own data.')
    st.stop()

st.markdown('**Data mode:** %s · **Metrics source:** %s · **Generated:** %s'
            % (m.get('data_mode'), m.get('source'), m.get('generated_at', '')[:16]))

st.subheader('Classification quality')
cls = m.get('classification') or {}
if cls.get('status') == 'NOT RUN':
    st.write('NOT RUN')
else:
    c1, c2, c3 = st.columns(3)
    c1.metric('Macro-F1 (%s)' % cls.get('source'), cls.get('macro_f1'))
    c2.metric('Weighted-F1', cls.get('weighted_f1'))
    c3.metric('ECE', m.get('ece', '—'))
    st.write('**By channel**', json.dumps(cls.get('by_channel', {}), indent=1))
    st.write('**By language pattern**', json.dumps(cls.get('by_lang_pattern', {}), indent=1))
    acc = m.get('accuracy_vs_coverage', [])
    if acc:
        st.subheader('Accuracy vs coverage (abstain curve)')
        st.line_chart(pd.DataFrame(acc).set_index('coverage')['accuracy'])

st.subheader('Early-warning radar')
radar = m.get('radar') or {}
if radar.get('planted_incidents'):
    st.write('**Planted incidents (team\u2019s own, SYNTHETIC):**')
    st.dataframe(pd.DataFrame(radar['planted_incidents']), width="stretch", hide_index=True)
if radar.get('false_alerts'):
    fa = radar['false_alerts']
    st.write('False alerts: %s alerts over %s store-weeks → **%s per store-week**'
             % (fa['alerts'], fa['store_weeks'], fa['per_store_week']))
if radar.get('injection_tuning'):
    st.write('**Injection tuning grid (top rows):**')
    st.dataframe(pd.DataFrame(radar['injection_tuning']), width="stretch", hide_index=True)
st.caption(radar.get('note', ''))

st.subheader('Precision statement (R5 output 5)')
ps = m.get('precision_statement') or {}
if ps.get('status') == 'NOT RUN':
    st.write('NOT RUN')
else:
    st.write('Source: %s' % ps.get('source'))
    for tier in ('overall', 'policy_tier', 'emerging_tier'):
        s = ps.get(tier) or {}
        if s.get('n'):
            lo, hi = s.get('wilson_95', ['—', '—'])
            st.write('**%s:** %d of %d escalated alerts truly actionable (%s, 95%% interval '
                     '%s–%s%%)' % (tier, s['actionable'], s['n'],
                                   ('%.1f%%' % (100 * s['precision'])) if s['precision'] is not None else '—',
                                   lo, hi))
    st.caption(ps.get('note', ''))

st.subheader('Policy review')
pr = m.get('policy_review') or {}
st.write(pr if pr.get('status') == 'NOT RUN' else
         'Reviewed %s flags, precision %s' % (pr.get('n_reviewed'), pr.get('precision')))

st.subheader('Acceptance checklist')
checklist = [
    'All four channel types represented',
    'Store master and issue taxonomy loaded and validated',
    'Classification, severity and actionability outputs reproducible',
    'Mandatory-risk categories escalate independently of volume',
    'Seeded incidents evaluated with no hardcoding, no hidden-label tuning',
    'Lead time and false-alert behavior reported',
    'Alerts show evidence, reason, uncertainty, owner, escalation rule',
    'Owner routing from the taxonomy and store master',
    'Regional brief one page, evidence-backed, exportable',
    'Precision statement has sample size and confidence interval',
    'Synthetic data labelled everywhere it appears',
    'Demo can be reset and repeated from documented steps',
]
for item in checklist:
    st.write('- [ ] ' + item)

if cfg.get('data_mode') == 'synthetic':
    st.error('SYNTHETIC DATA: none of the numbers on this page are measured on the '
             'organizers\u2019 dataset. On the final day the same pipeline runs on the real '
             'files and this page shows EVALUATE.PY / DEV values only.')
