"""Taxonomy matcher (gate G4): turn the organizers' taxonomy file into
config/taxonomy.yaml and a draft config/routing.yaml on the final day.
Matches each organizer issue to the closest library entry; ids, names and
owners always come from the organizers' file."""
import re

import numpy as np
import pandas as pd
import yaml

from . import embed
from .config import ROOT, cfg, load_taxonomy

RISK_HINTS = re.compile(r'safety|allergen|hygiene|misconduct|expir', re.IGNORECASE)


def match(organizer_issues, library_issues=None, model=None):
    """organizer_issues: list of dicts with id, name, owner, definition (optional).
    Returns (taxonomy list, match report DataFrame)."""
    library = library_issues or load_taxonomy()['issues']
    model = model or embed.get_model()
    lib_texts = [it['name'] + ' ' + it['description'] for it in library]
    lib_vecs = embed.embed(lib_texts, model, batch=8)
    out = []
    rows = []
    for oi in organizer_issues:
        otext = str(oi.get('name', '')) + ' ' + str(oi.get('definition', ''))
        v = embed.embed([otext], model, batch=1)[0]
        sims = lib_vecs @ v
        order = np.argsort(-sims)
        best = library[order[0]]
        otext_l = otext.lower()
        otext_tokens = set(re.findall(r'\w+', otext_l))
        kw_shared = set()
        for _kw in best.get('seed_keywords', []):
            _kws = _kw.lower()
            if _kws in otext_l:
                kw_shared.add(_kw)
            elif any(_t.strip('*') in otext_tokens for _t in _kws.split() if len(_t.strip('*')) >= 4):
                kw_shared.add(_kw)
        sim1, sim2 = float(sims[order[0]]), float(sims[order[1]])
        accept = bool(kw_shared) and (sim1 - sim2 >= 0.02 or sim1 >= 0.80)
        if accept:
            entry = {k: best[k] for k in ('description', 'seed_keywords', 'example_texts', 'family')}
        else:
            entry = {'description': '', 'seed_keywords': [], 'example_texts': [], 'family': ''}
        mandatory = bool(best.get('mandatory_risk')) or bool(RISK_HINTS.search(otext))
        out.append({
            'id': oi['id'], 'name': oi.get('name', oi['id']),
            'owner': oi.get('owner', 'Store Ops'),
            'default_severity': oi.get('severity') or best.get('default_severity', 'medium'),
            'mandatory_risk': mandatory,
            **entry,
        })
        rows.append({'organizer_id': oi['id'], 'organizer_name': oi.get('name', ''),
                     'matched_library_id': best['id'], 'similarity': round(sim1, 4),
                     'accepted': accept, 'shared_keywords': ', '.join(sorted(kw_shared)[:6]),
                     'mandatory': mandatory, 'review': ''})
    return out, pd.DataFrame(rows)


def run():
    """Read the organizers' taxonomy from config/taxonomy_organizer.yaml (any
    list format) and write taxonomy.yaml + routing draft + match report."""
    src = ROOT / 'config' / 'taxonomy_organizer.yaml'
    if not src.exists():
        print('build_taxonomy: config/taxonomy_organizer.yaml not found -- '
              'place the organizers\' taxonomy there on the final day.')
        return
    raw = yaml.safe_load(open(src, encoding='utf-8'))
    if isinstance(raw, dict):
        items = raw.get('issues') or raw.get('taxonomy') or list(raw.values())[0]
    else:
        items = raw
    org = [{'id': str(it.get('id') or it.get('issue_id') or it.get('name')),
            'name': str(it.get('name', '')), 'owner': str(it.get('owner', 'Store Ops')),
            'severity': it.get('severity') or it.get('default_severity'),
            'definition': str(it.get('definition') or it.get('description') or '')}
           for it in items]
    tax, report = match(org)
    with open(ROOT / 'config' / 'taxonomy.yaml', 'w', encoding='utf-8') as f:
        yaml.safe_dump({'issues': tax}, f, allow_unicode=True, sort_keys=False)
    default_route = {'owner': 'Store Ops', 'severity': 'medium',
                     'first_action': 'Review the evidence and assign an owner',
                     'escalation_rule': 'Standard trend rule', 'sla_hours': 72}
    routes = {'routes': {it['id']: {'owner': it['owner'], 'severity': it['default_severity'],
                                    'first_action': 'Review the evidence and assign an owner',
                                    'escalation_rule': 'Standard trend rule', 'sla_hours': 72}
                         for it in tax},
              'default': default_route}
    with open(ROOT / 'config' / 'routing_draft.yaml', 'w', encoding='utf-8') as f:
        yaml.safe_dump(routes, f, allow_unicode=True, sort_keys=False)
    reports = ROOT / 'reports'
    reports.mkdir(parents=True, exist_ok=True)
    report.to_csv(reports / 'taxonomy_match.csv', index=False)
    print('build_taxonomy: matched %d/%d issues; review reports/taxonomy_match.csv '
          'and fix the Review column by hand' % (int(report['accepted'].sum()), len(report)))
