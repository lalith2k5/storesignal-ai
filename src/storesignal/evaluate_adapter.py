"""DATA-DEPENDENT (⚠): exports predictions and detections for the organizers'
evaluate.py. Column names come from config/evaluate; change only the config
once the real evaluate.py is seen. Never run it automatically."""
import pandas as pd

from .config import ROOT, cfg


def export(pred, alerts):
    e = cfg['evaluate']
    m = e['prediction_columns']
    out = pred[['record_id', 'issue', 'severity', 'actionable']].copy()
    out = out.rename(columns={'record_id': m['record_id'], 'issue': m['issue'],
                              'severity': m['severity'], 'actionable': m['actionable']})
    out[list(m.values())].to_csv(ROOT / e['predictions_path'], index=False)
    d = e['detection_columns']
    det = pd.DataFrame([{d['store_id']: a['store_id'], d['issue']: a['issue'],
                         d['detected_at']: a['first_ts']}
                        for a in alerts if a.get('tier') != 'policy'])
    det.to_csv(ROOT / e['detections_path'], index=False)
    print('evaluate_adapter: wrote %s (%d rows) and %s (%d rows)'
          % (e['predictions_path'], len(out), e['detections_path'], len(det)))
