"""Rough language-pattern tag. Used ONLY to slice error analysis; never drives routing."""
import re

_DEV = re.compile(r'[\u0900-\u097F]')
_TAM = re.compile(r'[\u0B80-\u0BFF]')
HI = set('nahi kya hai bahut accha kharab thanda garam paisa wala hain bhi aur'.split())
TA = set('romba illai nalla mosam enna inga sapadu'.split())
MR = set('khup aahe ahe kay changla majha'.split())


def lang_pattern(t):
    if _DEV.search(t) or _TAM.search(t):
        return 'native_script'
    w = set(t.split())
    h, ta, m = len(w & HI), len(w & TA), len(w & MR)
    if h + ta + m == 0:
        return 'english'
    if sum(x > 0 for x in (h, ta, m)) > 1:
        return 'mixed'
    return 'hinglish' if h else 'romanized_tamil' if ta else 'romanized_marathi'
