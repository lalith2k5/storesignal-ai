"""No hidden-label leakage: pipeline modules never read the synthetic truth
columns. synth.py generates them, and evaluate.py / weak_labels.py may read
them ONLY to report results tagged SYNTHETIC (sanctioned by the guide's
Section 21.3)."""
from pathlib import Path

from storesignal.config import ROOT

ALLOWED = {'synth.py', 'evaluate.py', 'weak_labels.py', '__init__.py'}
PIPELINE = {'ingest.py', 'normalize.py', 'embed.py', 'classify.py', 'train.py', 'score.py',
            'policy.py', 'semantic.py', 'dedupe.py', 'fuse.py', 'radar.py', 'alerts.py',
            'routing.py', 'tracker.py', 'brief.py', 'metrics.py', 'evaluate_adapter.py',
            'cli.py', 'make_sample_ids.py', 'build_taxonomy.py', 'inspect_data.py', 'automap.py'}


def test_no_label_leakage():
    src = ROOT / 'src' / 'storesignal'
    offenders = {}
    for name in PIPELINE:
        text = (src / name).read_text(encoding='utf-8')
        for token in ('true_issue', 'planted'):
            if token in text:
                offenders.setdefault(name, []).append(token)
    assert not offenders, f'pipeline modules reference hidden-truth tokens: {offenders}'
