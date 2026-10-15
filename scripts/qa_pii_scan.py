"""QA tool (§17): scan alert evidence for leaked emails/phones/URLs.
Usage: python scripts/qa_pii_scan.py
"""
import json
import re
from pathlib import Path

EMAIL = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
PHONE = re.compile(r'(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)')
URL = re.compile(r'https?://\S+')

alerts = json.load(open('data/processed/alerts.json', encoding='utf-8'))
findings = []
for a in alerts:
    for ev in a.get('evidence', []):
        t = ev.get('text_masked', '')
        for name, rx in [('email', EMAIL), ('phone', PHONE), ('url', URL)]:
            for m in rx.finditer(t):
                findings.append({'alert_id': a['alert_id'], 'kind': name,
                                 'match': m.group(0)[:40], 'text': t[:120]})

print(f"Scanned {len(alerts)} alerts, {sum(len(a.get('evidence',[])) for a in alerts)} evidence rows.")
if not findings:
    print("PASS: no unmasked emails, phones, or URLs found in alert evidence.")
else:
    print(f"WARNING: {len(findings)} potential PII leaks:")
    for f in findings[:40]:
        print(f"  [{f['kind']}] alert={f['alert_id']} match={f['match']!r} text={f['text'][:80]!r}")
    print(f"\nAll findings written to reports/qa_pii_scan.json")
    Path('reports').mkdir(exist_ok=True)
    json.dump(findings, open('reports/qa_pii_scan.json', 'w'), indent=2)
