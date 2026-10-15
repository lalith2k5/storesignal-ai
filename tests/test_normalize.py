from storesignal.normalize import normalize


def test_idempotent():
    t = 'sooooo gud  Freezer!! nahi thanda  😡'
    once, twice = normalize(t), normalize(normalize(t))
    assert once == twice


def test_keeps_negation():
    t = 'not cooling, nahi thanda, illai poochi nako keeda'
    out = normalize(t)
    for w in ['not', 'nahi', 'illai', 'nako']:
        assert w in out


def test_emoji_becomes_token():
    out = normalize('very bad service 😡')
    assert 'emoji_' in out


def test_spelling_variants_canonicalized():
    out = normalize('kharaab thandaa gandi')
    assert 'kharab' in out and 'thanda' in out and 'ganda' in out


def test_abbreviations_expanded():
    assert 'freezer' in normalize('frzr not cooling')
