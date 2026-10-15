"""Issue classification: hybrid TF-IDF (char+word) + multilingual embeddings
with logistic regression. M1 = TF-IDF only, M2 = embeddings only, M3 = hybrid."""
import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion


def make_vectorizer(max_features=300000):
    return FeatureUnion([
        ('char', TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 5), min_df=3,
                                 sublinear_tf=True, max_features=max_features)),
        ('word', TfidfVectorizer(analyzer='word', ngram_range=(1, 2), min_df=2,
                                 sublinear_tf=True, token_pattern=r"[\w']+")),
    ])


def _features(m, texts, E, fit=False):
    parts = []
    if m.get('use_tfidf', True):
        out = m['vec'].fit_transform(texts) if fit else m['vec'].transform(texts)
        parts.append(out)
    if m.get('use_emb', True) and E is not None:
        parts.append(sp.csr_matrix(np.asarray(E, dtype='float32') * m.get('w', 1.0)))
    return sp.hstack(parts).tocsr()


def fit(texts, E, y, use_tfidf=True, use_emb=True, emb_weight=1.0, C=4.0,
        max_features=300000, solver='lbfgs'):
    m = {'vec': make_vectorizer(max_features) if use_tfidf else None,
         'use_tfidf': use_tfidf, 'use_emb': use_emb and E is not None, 'w': emb_weight}
    X = _features(m, texts, E, fit=True)
    m['clf'] = LogisticRegression(C=C, max_iter=3000, class_weight='balanced', solver=solver).fit(X, y)
    m['classes'] = m['clf'].classes_
    return m


def predict(m, texts, E):
    X = _features(m, texts, E)
    P = m['clf'].predict_proba(X)
    cls = m['clf'].classes_
    order = np.argsort(-P, axis=1)
    i1, i2 = order[:, 0], order[:, 1]
    r = np.arange(len(P))
    return pd.DataFrame({'issue': cls[i1], 'p1': P[r, i1], 'issue2': cls[i2], 'p2': P[r, i2],
                         'margin': P[r, i1] - P[r, i2]})


# ---- Severity and actionability (Scenario B: transparent rules) ----
SEV = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}
INTENSITY = ['again', 'everyone', 'children', 'kids', 'baby', 'sick', 'hospital', 'daily',
             'since morning', 'baar baar', 'romba', 'bahut']


def severity(issue_default, policy_floor, rating, text_norm):
    s = SEV.get(issue_default, 1)
    if policy_floor:  # mandatory-risk categories raise the floor
        s = max(s, SEV.get(policy_floor, s))
    if any(w in str(text_norm) for w in INTENSITY) or (pd.notna(rating) and rating <= 1):
        s = min(s + 1, 3)
    return s


CONCRETE = ['counter', 'aisle', 'freezer', 'fridge', 'shelf', 'floor', 'billing', 'app', 'today',
            'yesterday', 'morning', 'batch', 'expired', 'label', 'delivery', 'staff', 'store',
            'payment', 'coupon', 'slot', 'order']


def actionable_heuristic(text_norm, p1):
    t = str(text_norm)
    return int(len(t.split()) >= 4 and p1 >= 0.5 and any(w in t for w in CONCRETE))
