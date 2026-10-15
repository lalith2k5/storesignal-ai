from storesignal.config import load_policy, load_routes
from storesignal.routing import route_for


def test_policy_route_wins_whatever_the_classifier_said():
    routes, spec = load_routes(), load_policy()
    # classifier says rude_service, but the record had a non-negated allergen hit
    r = route_for('rude_service', ['allergen'], routes, spec)
    assert r['owner'] == 'Supply Chain'
    assert r['severity'] == 'critical'
    assert 'MANDATORY POLICY [allergen]' in r['escalation_rule']


def test_default_route():
    routes, spec = load_routes(), load_policy()
    r = route_for('out_of_stock', [], routes, spec)
    assert r['owner'] == 'Merchandising'
    assert r['severity'] == 'medium'


def test_policy_floor_does_not_lower_severity():
    routes, spec = load_routes(), load_policy()
    r = route_for('allergen_mislabel', ['food_hygiene'], routes, spec)
    # allergen_mislabel is critical in the taxonomy; food_hygiene floor is high
    assert r['severity'] == 'critical'
