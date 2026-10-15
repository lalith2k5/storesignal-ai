"""Early-Warning Radar with the replay simulator."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from common import banner, load
from storesignal.config import cfg

banner()
rec, alerts = load()
st.title('Early-Warning Radar')
st.caption('Each store is compared with its own history, scaled by its own activity '
           '(exposure proxy = store total feedback volume). The detector is causal: at '
           'every moment it uses only records that existed then.')

if not alerts:
    st.info('No alerts yet.')
    st.stop()

from storesignal.radar import baseline_b3_fire  # noqa: E402


def timeline(a):
    ev = pd.DataFrame(a['evidence'])
    if ev.empty:
        return []
    ev['ts'] = pd.to_datetime(ev['ts'])
    ev = ev.sort_values('ts')
    steps = [(ev['ts'].iloc[0], 'First weak signal (%s)' % ev['channel'].iloc[0])]
    seen = {ev['channel'].iloc[0]}
    for r in ev.itertuples():
        if r.channel not in seen:
            steps.append((r.ts, 'Report from another channel (%s)' % r.channel))
            seen.add(r.channel)
    t_alert = pd.Timestamp(a['alert_ts'])
    steps.append((t_alert, 'ALERT: severity %s, owner %s' % (a['severity'], a['owner'])))
    steps.append((t_alert, 'Recommended: ' + a.get('action', a['escalation_rule'])))
    return sorted(steps, key=lambda s: s[0])


default_id = cfg.get('demo', {}).get('replay_alert_id', '')
labels = ['%s | %s | %s' % (a['alert_id'], a['store_id'], a['issue']) for a in alerts]
default_idx = next((i for i, l in enumerate(labels) if l.split(' | ')[0] == default_id), 0)
pick = st.selectbox('Incident', labels, index=default_idx)
a = next(x for x in alerts if x['alert_id'] == pick.split(' | ')[0])

ev = rec[(rec['store_id'] == a['store_id']) & (rec['issue'] == a['issue'])
         & (rec['ts'] <= pd.Timestamp(a['alert_ts']) + pd.Timedelta(days=1))].copy()
daily = ev.set_index('ts').resample('D').size()
fig = go.Figure(go.Bar(x=daily.index, y=daily.values, name='unique reports per day'))
t_alert = pd.Timestamp(a['alert_ts'])
fig.add_shape(type='line', x0=t_alert, x1=t_alert, y0=0, y1=1, yref='paper',
              line=dict(color='red', dash='dash'))
fig.update_layout(height=320, yaxis_title='reports/day')
st.plotly_chart(fig, width="stretch")

why = a['why']
st.markdown('**Why this alert exists:** %s unique reports in %s days versus about %s expected '
            '(%sx, p=%s). Channels: %s.' %
            (why.get('k'), why.get('window_days'), why.get('expected'), why.get('ratio'),
             why.get('p'), ', '.join(a['channels'])))
st.markdown('**Explanation:** ' + a['explanation'])
if a.get('uncertainty_notes'):
    st.caption(' · '.join(a['uncertainty_notes']))

steps = timeline(a)
if steps:
    t0 = steps[0][0]
    span = int((steps[-1][0] - t0).total_seconds() // 3600) + 6
    h = st.slider('Replay: hours since the first related report', 0, span, 0)
    now = t0 + pd.Timedelta(hours=h)
    for t, text in [s for s in steps if s[0] <= now]:
        st.write('**%s**  %s' % (t.strftime('%d %b %H:%M'), text))

    b = baseline_b3_fire(ev['ts'].tolist(), k=cfg['baselines']['b3_k'],
                         days=cfg['baselines']['b3_days'])
    st.caption('Simple volume rule (%d reports in %d days) would fire: %s. StoreSignal fired: %s. '
               'This comparison is the team\u2019s own measure; the organizers\u2019 lead time '
               'comes only from evaluate.py.' %
               (cfg['baselines']['b3_k'], cfg['baselines']['b3_days'],
                b.strftime('%d %b %H:%M') if b is not None else 'never',
                t_alert.strftime('%d %b %H:%M')))
    if st.button('Reset replay'):
        st.rerun()

pat = a['why'].get('pattern_id')
if pat:
    peers = [x for x in alerts if x['why'].get('pattern_id') == pat and x['alert_id'] != a['alert_id']]
    if peers:
        st.subheader('Cross-store pattern')
        st.warning('Multi-store pattern, shared cause unverified.')
        st.write(', '.join('%s · %s' % (p['store_id'], p['issue']) for p in peers))
