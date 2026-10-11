"""Command-line entry point for the same service used by the browser."""
import argparse
import json
from pathlib import Path
import sys

from service import Product


def main():
    parser = argparse.ArgumentParser(description='University service desk: retrieval, requests, and staff decisions.')
    parser.add_argument('--data-dir', type=Path, default=Path(__file__).resolve().parent / '.product-data')
    parser.add_argument('--out', type=Path, help='Also write the JSON result to this file.')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('state', help='Read the current inbox, directory, and knowledge index.')
    view = commands.add_parser('view', help='Select the local student or staff context.')
    view.add_argument('view', choices=('student','staff'))
    submit = commands.add_parser('submit', help='Submit a request to the orchestrator.')
    submit.add_argument('--requester', required=True)
    submit.add_argument('--role', choices=('student','staff'), default='student')
    submit.add_argument('--text', required=True)
    search = commands.add_parser('search', help='Search indexed knowledge within requester visibility.')
    search.add_argument('query')
    search.add_argument('--role', choices=('student','staff'), default='student')
    for name in ('assign','resolve','note','escalate'):
        command = commands.add_parser(name, help=f'{name.capitalize()} an existing request.')
        command.add_argument('ticket_id', type=int)
        command.add_argument('--version', type=int, required=True)
        command.add_argument('--actor', default='coordinator')
        command.add_argument('--note', required=True)
        if name == 'assign':
            command.add_argument('--assignee-id', required=True)
    export = commands.add_parser('export', help='Export a complete ticket and its trace.')
    export.add_argument('ticket_id', type=int)
    commands.add_parser('reindex', help='Rebuild the inverted index from persisted knowledge.')
    knowledge = commands.add_parser('knowledge-add', help='Add searchable guidance.')
    knowledge.add_argument('--title', required=True)
    knowledge.add_argument('--body', required=True)
    knowledge.add_argument('--department', required=True)
    knowledge.add_argument('--visibility', choices=('all','staff'), default='all')
    args = parser.parse_args()
    payload = vars(args).copy()
    command = payload.pop('command')
    data_dir, out = payload.pop('data_dir'), payload.pop('out')
    try:
        product = Product(data_dir)
        result = product.state() if command == 'state' else product.action(command.replace('-','_'), payload)
    except (ValueError, PermissionError, RuntimeError) as error:
        print(json.dumps({'error':str(error)}), file=sys.stderr)
        return 1
    encoded = json.dumps(result, indent=2, ensure_ascii=False)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(encoded + '\n', encoding='utf-8')
    print(encoded)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
