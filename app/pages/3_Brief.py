"""Regional Action Brief: region and week selectors, preview, downloads."""
import re

import streamlit as st

from common import banner
from storesignal.config import ROOT

banner()
st.title('Regional Action Brief')
st.caption('One page per region per week: top 5 issues, evidence quotes, affected stores, '
           'trend arrows, the safety box, emerging signals, actions due, and data caveats.')

briefs_dir = ROOT / 'reports' / 'briefs'
md_files = sorted(briefs_dir.glob('*.md')) if briefs_dir.exists() else []
if not md_files:
    st.info('No briefs generated yet. Run `python -m storesignal.cli brief` from the project root.')
    st.stop()

regions = sorted({f.name.split('_')[0] for f in md_files})
region = st.selectbox('Region', regions)
weeks = sorted({f.name.split('_')[1].replace('.md', '') for f in md_files
                if f.name.startswith(region + '_')}, reverse=True)
if not weeks:
    st.info('No briefs for region %s' % region)
    st.stop()
week = st.selectbox('Week (Monday)', weeks)
path = briefs_dir / ('%s_%s.md' % (region, week))
text = path.read_text(encoding='utf-8')
st.markdown(text)
st.download_button('Download Markdown', text, file_name=path.name, mime='text/markdown')
html_path = path.with_suffix('.html')
if html_path.exists():
    st.download_button('Download HTML (print to PDF)', html_path.read_text(encoding='utf-8'),
                       file_name=html_path.name, mime='text/html')
