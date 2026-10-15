"""StoreSignal AI — Command Center."""
import pandas as pd
import streamlit as st

from common import banner, con, load

st.set_page_config(page_title='StoreSignal AI', layout='wide')
banner()
st.title('StoreSignal AI: Command Center')
st.caption('Multilingual retail operations early-warning and incident-resolution intelligence. '
           'Detect weak signals early, explain why they matter, escalate risk regardless of '
           'volume, and help teams take accountable action.')

try:
    rec, alerts = load()
except FileNotFoundError:
    st.error('Pipeline artifacts not found. Run `python -m storesignal.cli all` from the '
             'project root first.')
    st.stop()

open_alerts = pd.read_sql("SELECT * FROM alerts WHERE status != 'Resolved'", con())
now_iso = pd.Timestamp.now(tz='UTC').isoformat()

c1, c2, c3, c4 = st.columns(4)
c1.metric('Reports (7 days)', int((rec['ts'] >= rec['ts'].max() - pd.Timedelta(days=7)).sum()))
c2.metric('Open alerts', len(open_alerts))
c3.metric('Policy items to review', int((open_alerts['tier'].isin(['policy', 'both'])).sum()))
c4.metric('Overdue', int((open_alerts['sla_due'] < now_iso).sum()))

st.subheader('Priority queue')
rank = {'critical': 3, 'high': 2, 'medium': 1, 'low': 0}
open_alerts['rank'] = open_alerts['severity'].map(rank).fillna(0)
q = open_alerts.sort_values(['rank', 'alert_ts'], ascending=[False, False])
st.dataframe(q[['alert_id', 'tier', 'store_id', 'issue', 'severity', 'owner', 'status']],
             width="stretch", hide_index=True)

st.subheader('Recent feedback')
chans = sorted(rec['channel'].unique())
sel = st.multiselect('Channel', chans, default=chans)
view = rec[rec['channel'].isin(sel)].sort_values('ts', ascending=False).head(50)
st.dataframe(view[['ts', 'store_id', 'channel', 'issue', 'p1', 'severity', 'text_masked']],
             width="stretch", hide_index=True)

st.caption('StoreSignal turns scattered store chatter into earlier, explainable and '
           'accountable action.')
