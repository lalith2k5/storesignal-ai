"""DATA-DEPENDENT (⚠): the only place that knows the organizers' file and column names.

The names below are placeholders. On the final day, open the real files and
change them here (or run `python -m storesignal.inspect_data` and
`python -m storesignal.automap` to generate a suggested mapping).
"""
CHANNELS = {
    'review': {
        'file': 'online_reviews.csv',
        'map': {'review_id': 'source_id', 'date': 'ts', 'store': 'store_id', 'text': 'text_raw', 'stars': 'rating'},
    },
    'app': {
        'file': 'app_comments.csv',
        'map': {'id': 'source_id', 'created_at': 'ts', 'store': 'store_id', 'comment': 'text_raw', 'rating': 'rating'},
    },
    'staff_note': {
        'file': 'staff_notes.csv',
        'map': {'note_id': 'source_id', 'time': 'ts', 'store': 'store_id', 'note': 'text_raw'},
    },
    'call': {
        'file': 'call_transcripts.csv',
        'map': {'ticket_id': 'source_id', 'opened': 'ts', 'store': 'store_id', 'transcript': 'text_raw'},
    },
}
STORE_MASTER = {'file': 'store_master.csv', 'map': {'store': 'store_id', 'region_name': 'region'}}
