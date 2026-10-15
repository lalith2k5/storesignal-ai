"""Taxonomy matcher (gate G4): at least 80% of the library issues map back to
themselves when fed as input. Skipped until the embedding model is cached."""
from pathlib import Path

import pytest

from storesignal.build_taxonomy import match
from storesignal.config import load_taxonomy

HF_CACHE = Path.home() / '.cache' / 'huggingface'
_OTHER = Path.home() / 'Library' / 'Caches' / 'huggingface'


@pytest.mark.skipif(not (HF_CACHE.exists() or _OTHER.exists()),
                    reason='embedding model not cached yet; run the pipeline once first')
def test_taxonomy_match():
    lib = load_taxonomy()['issues']
    as_input = [{'id': it['id'], 'name': it['name'], 'owner': it['owner'],
                 'definition': it['description']} for it in lib]
    tax, report = match(as_input)
    accepted = report[report['accepted']]
    assert len(accepted) / len(report) >= 0.8
    # accepted matches must be to the same id
    same = (accepted['organizer_id'] == accepted['matched_library_id']).mean()
    assert same >= 0.8
