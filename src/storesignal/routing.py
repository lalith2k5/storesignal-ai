"""Routing: issue -> owning function, severity, first action, escalation rule."""
SEV = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}


def route_for(issue, policy_cats, routes, policy_spec):
    """Mandatory policy rules are deterministic and always win over the default route."""
    r = dict(routes['routes'].get(issue, routes['default']))
    for cat in (policy_cats or []):
        pc = policy_spec['categories'][cat]
        if SEV.get(pc['severity_floor'], 1) > SEV.get(r['severity'], 1):
            r['severity'] = pc['severity_floor']
        r['owner'], r['cc'] = pc['owner'], pc.get('cc', [])
        r['escalation_rule'] = 'MANDATORY POLICY [' + cat + ']: ' + pc['escalation']
    return r
