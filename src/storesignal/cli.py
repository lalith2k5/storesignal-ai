"""Pipeline CLI: one command rebuilds everything. Each step module has run()."""
import argparse
import importlib

ORDER = ['ingest', 'normalize', 'embed', 'weak_labels', 'train', 'score',
         'radar', 'alerts', 'brief', 'evaluate']
EXTRA = ['tune', 'label_sample', 'inspect', 'automap', 'build_taxonomy']
ALIAS = {'label_sample': 'make_sample_ids', 'inspect': 'inspect_data'}


def main():
    ap = argparse.ArgumentParser(prog='storesignal')
    ap.add_argument('step', choices=ORDER + EXTRA + ['all'])
    step = ap.parse_args().step
    if step == 'all':
        for name in ORDER:
            print('== running', name)
            importlib.import_module('storesignal.' + name).run()
    else:
        name = ALIAS.get(step, step)
        print('== running', name)
        importlib.import_module('storesignal.' + name).run()


if __name__ == '__main__':
    main()
