from storesignal.policy import PolicyEngine


def test_policy_basics():
    e = PolicyEngine()
    assert any(h['category'] == 'allergen' and not h['negated']
               for h in e.scan('label said nut free but peanuts inside, allergy ho gayi'))
    assert all(h['negated'] for h in e.scan('no cockroach found, store very clean')
               if h['category'] == 'food_hygiene')
    assert any(h['category'] == 'staff_misconduct' for h in e.scan('billing wale ne badtameezi se baat ki'))


def test_post_noun_negation():
    e = PolicyEngine()
    hits = e.scan('keeda nahi tha, sab clean tha')
    assert any(h['category'] == 'food_hygiene' and h['negated'] for h in hits)
    assert all(h['negated'] for h in hits)


def test_physical_safety_patterns():
    e = PolicyEngine()
    assert any(h['category'] == 'physical_safety' and not h['negated']
               for h in e.scan('wire khula tha aur current laga'))


def test_negated_hits_do_not_flag():
    e = PolicyEngine()
    hits = e.scan('no rats no insects, very clean store')
    assert all(h['negated'] for h in hits)
