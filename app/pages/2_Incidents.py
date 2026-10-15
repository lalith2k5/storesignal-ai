"""Incident Explorer: search, evidence, connection graph, routing, tracker."""
import json
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from common import banner, con, event_history, load
from storesignal import tracker
from storesignal.fuse import build_graph, render as render_graph

banner()
rec, alerts = load()
st.title('Incident Explorer')

c = con()
tracker.init_db(c)
rows = c.execute('SELECT * FROM alerts').fetchall()
cols = [d[0] for d in c.execute('SELECT * FROM alerts LIMIT 1').description]
df = pd.DataFrame(rows, columns=cols)
if df.empty:
    st.info('No alerts yet.')
    st.stop()

f1, f2, f3 = st.columns(3)
region = f1.selectbox('Region', ['All'] + sorted(df['region'].dropna().unique().tolist()))
tier = f2.selectbox('Tier', ['All', 'policy', 'emerging', 'both'])
status = f3.selectbox('Status', ['All'] + tracker.STATUSES)
q = st.text_input('Search (alert id, store, issue)', '')
view = df.copy()
if region != 'All':
    view = view[view['region'] == region]
if tier != 'All':
    view = view[view['tier'] == tier]
if status != 'All':
    view = view[view['status'] == status]
if q:
    m = (view['alert_id'].str.contains(q, case=False, na=False)
         | view['store_id'].str.contains(q, case=False, na=False)
         | view['issue'].str.contains(q, case=False, na=False))
    view = view[m]
st.dataframe(view[['alert_id', 'tier', 'store_id', 'region', 'issue', 'severity', 'owner',
                   'status', 'sla_due']].sort_values('sla_due'), width="stretch",
             hide_index=True)

pick = st.selectbox('Alert', view['alert_id'].tolist() if len(view) else [''])
if not pick:
    st.stop()
alert_row = df[df['alert_id'] == pick].iloc[0]
payload = json.loads(alert_row['payload_json'])

st.subheader('Evidence')
st.markdown('**%s** — tier %s, severity %s, owner %s' %
            (payload['issue'], payload['tier'], payload['severity'], payload['owner']))
st.markdown(payload['explanation'])
for note in payload.get('uncertainty_notes', []):
    st.caption('· ' + note)
ev_df = pd.DataFrame(payload['evidence'])
if not ev_df.empty:
    ev_df['ts'] = pd.to_datetime(ev_df['ts'])
    st.dataframe(ev_df[['ts', 'channel', 'record_id', 'text_masked']], width="stretch",
                 hide_index=True)

st.subheader('Connection graph')
cluster_ids = rec[rec['record_id'].isin(set(ev_df['record_id'].tolist()))]['incident_cluster_id'].unique() \
    if not ev_df.empty else []
if len(cluster_ids):
    cluster = rec[rec['incident_cluster_id'] == cluster_ids[0]]
    G = build_graph(cluster_ids[0], cluster, alert_row['store_id'])
    with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as tf:
        render_graph(G, tf.name)
        st.components.v1.html(Path(tf.name).read_text(encoding='utf-8'), height=560)
    st.caption('Correlated pattern. A shared cause is a hypothesis until verified. '
               'Use wording such as \u201cpossible common refrigeration issue\u201d, '
               'never \u201cthe freezer broke\u201d.')

st.subheader('Action tracking')
new_status = st.selectbox('Move status to', tracker.STATUSES, index=tracker.STATUSES.index(alert_row['status']))
actor = st.text_input('Actor', value='region manager')
if st.button('Update status') and new_status != alert_row['status']:
    tracker.set_status(c, pick, new_status, actor)
    st.success('Status updated to %s' % new_status)
    st.rerun()

st.subheader('Owner override (recorded with a reason)')
new_owner = st.text_input('New owner', value=alert_row['owner'])
reason = st.text_input('Reason', '')
if st.button('Override owner') and reason.strip():
    tracker.override_owner(c, pick, new_owner, actor, reason)
    st.success('Owner changed to %s' % new_owner)
    st.rerun()

st.subheader('Reviewer verdict')
verdict = st.radio('Verdict', tracker.VERDICTS, horizontal=True)
if st.button('Record verdict'):
    tracker.add_feedback(c, pick, actor, verdict)
    st.success('Verdict recorded: %s' % verdict)

st.subheader('Event history')
event_history(pick)
