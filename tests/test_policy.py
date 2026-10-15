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


def test_context_negation_gluten_section():
    """'gluten free section' is wayfinding, not a mislabel."""
    e = PolicyEngine()
    hits = [h for h in e.scan('staff had no idea where the gluten free section was')
            if h['category'] == 'allergen']
    assert hits, 'expected gluten hit to fire'
    assert all(h['negated'] for h in hits), 'gluten-in-section should be negated'


def test_context_negation_gluten_typo():
    """Typo tolerance: 'secton' should still trigger the context negation."""
    e = PolicyEngine()
    hits = [h for h in e.scan('staff had no idea where the gluten free secton was')
            if h['category'] == 'allergen']
    assert hits and all(h['negated'] for h in hits)


def test_context_negation_does_not_hide_real_mislabel():
    """'labeled gluten free but contains wheat' is a real allergen problem."""
    e = PolicyEngine()
    hits = [h for h in e.scan('label said gluten free but contains wheat, allergy ho gayi')
            if h['category'] == 'allergen' and h['span'] == 'gluten']
    assert hits, 'expected gluten hit'
    assert all(not h['negated'] for h in hits), 'real mislabel must NOT be negated'


def test_context_negation_coupon_expired():
    """'coupon expired' is a promo problem, not spoiled food."""
    e = PolicyEngine()
    hits = [h for h in e.scan('coupon says expired though it is valid')
            if h['category'] == 'food_hygiene' and h['span'] == 'expired']
    assert hits and all(h['negated'] for h in hits)


def test_context_negation_does_not_hide_real_expiry():
    """'expired milk on shelf' is a real food-hygiene problem."""
    e = PolicyEngine()
    hits = [h for h in e.scan('found milk packets past their expiry date on the shelf')
            if h['category'] == 'food_hygiene']
    assert hits and all(not h['negated'] for h in hits)
