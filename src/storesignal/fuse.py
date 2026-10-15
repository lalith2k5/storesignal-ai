"""Root-cause connection graph (stretch): show related signals as a graph of
reports, the possible incident, the store, and shared entities. Every edge
carries the reason it exists. Correlated pattern, NOT confirmed cause."""
import json

import networkx as nx
import pandas as pd


def build_graph(inc_id, recs, store_id):
    """recs: this incident cluster with record_id, channel, text_masked, entities (list)."""
    G = nx.Graph()
    G.add_node(inc_id, label='Possible incident', color='#d9480f', shape='diamond')
    G.add_node(store_id, label='Store ' + str(store_id), color='#1c7ed6')
    G.add_edge(inc_id, store_id, title='occurred at this store')
    for r in recs.itertuples():
        G.add_node(r.record_id, label=r.channel, title=str(r.text_masked)[:200],
                   color='#2f9e44', shape='box')
        G.add_edge(inc_id, r.record_id,
                   title='grouped: same store, same issue family, within 72 hours')
        ents = json.loads(r.entities) if isinstance(r.entities, str) else (r.entities or [])
        for e in ents:
            G.add_node('ent:' + e, label=e, color='#f08c00', shape='box')
            G.add_edge(r.record_id, 'ent:' + e, title='mentions ' + e)
    return G


def render(G, path):
    from pyvis.network import Network
    net = Network(height='520px', width='100%', cdn_resources='in_line')
    net.from_nx(G)
    net.write_html(str(path))


def family_map(taxonomy):
    return {it['id']: it.get('family', '') for it in taxonomy['issues']}
