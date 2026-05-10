"""
Smoke test for /api/infringement-chart/<case_id> error-code surface.

Run from the Backend directory:
    python test_infringement_chart_errors.py

Exercises the live endpoint (via Flask test_client) and the underlying
get_infringement_chart() function for every documented error_code.
"""

import json
import sys
from contextlib import contextmanager

CASE_ID = 'googlepatents_54602cb5-23e8-4e42-8d6b-c33642007029_WO2021187654A1'
USER_ID = '54602cb5-23e8-4e42-8d6b-c33642007029'


def _print_header(label):
    line = '=' * 78
    print(f'\n{line}\n{label}\n{line}')


def _hit_endpoint(client, headers=None, case_id=CASE_ID):
    resp = client.get(f'/api/infringement-chart/{case_id}', headers=headers or {})
    try:
        body = resp.get_json()
    except Exception:
        body = resp.data.decode('utf-8', errors='replace')
    print(f'  status : {resp.status_code}')
    print(f'  body   : {json.dumps(body, indent=2, default=str)[:1000]}')
    return resp.status_code, body


@contextmanager
def patched(target_module, attr_name, value):
    sentinel = object()
    original = getattr(target_module, attr_name, sentinel)
    setattr(target_module, attr_name, value)
    try:
        yield
    finally:
        if original is sentinel:
            delattr(target_module, attr_name)
        else:
            setattr(target_module, attr_name, original)


def main():
    import app as app_module
    from app import app
    import models.cases as cases_module
    from models.cases import get_infringement_chart

    flask_client = app.test_client()

    _print_header('1. Direct call: get_infringement_chart(real case_id)')
    chart, code = get_infringement_chart(CASE_ID)
    rows = len(chart) if chart is not None else 0
    print(f'  error_code   : {code}')
    print(f'  rows         : {rows}')
    if chart and rows:
        sample = chart[0]
        if isinstance(sample, dict):
            print(f'  sample keys  : {list(sample.keys())}')

    _print_header('2. Endpoint: missing X-User-ID -> NO_SESSION (401)')
    _hit_endpoint(flask_client, headers={})

    _print_header('3. Endpoint: real case_id with X-User-ID')
    _hit_endpoint(flask_client, headers={'X-User-ID': USER_ID})

    _print_header('4. Endpoint: bogus case_id -> CASE_NOT_FOUND (404)')
    _hit_endpoint(
        flask_client,
        headers={'X-User-ID': USER_ID},
        case_id='__definitely_not_a_real_case__',
    )

    # --- Synthetic error paths via stubbing getDataById in models.cases ---

    def make_stub_case(claims=None, infringements=None):
        return lambda *a, **kw: {
            '_id': CASE_ID,
            'id': CASE_ID,
            'claims': claims if claims is not None else [],
            'infringements': infringements if infringements is not None else [],
        }

    _print_header('5. Stubbed: case has no claims -> NO_PARENT_CLAIMS (422)')
    with patched(cases_module, 'getDataById', make_stub_case(claims=[], infringements=[{'claims': ['x']}])):
        _hit_endpoint(flask_client, headers={'X-User-ID': USER_ID})

    _print_header('6. Stubbed: case has claims but no infringements -> NO_INFRINGEMENTS (422)')
    with patched(cases_module, 'getDataById', make_stub_case(claims=['1. A device.'], infringements=[])):
        _hit_endpoint(flask_client, headers={'X-User-ID': USER_ID})

    _print_header('7. Stubbed: infringements have no claims -> INFRINGEMENT_CLAIMS_MISSING (422)')
    with patched(
        cases_module,
        'getDataById',
        make_stub_case(claims=['1. A device.'], infringements=[{'claims': []}, {'claims': ['  ']}]),
    ):
        _hit_endpoint(flask_client, headers={'X-User-ID': USER_ID})

    _print_header('8. Stubbed: scoring returns empty -> NO_MATCHES_ABOVE_THRESHOLD (200)')

    def empty_scorer(parent_claims, inf_claims, existing, threshold=0.5):
        # stored_rows non-None (so persistence path fires), entry_chart_rows empty
        return [], []

    with patched(cases_module, 'getDataById', make_stub_case(
        claims=['1. A device comprising a widget.'],
        infringements=[{'claims': ['Some unrelated claim text.']}],
    )), patched(cases_module, 'score_infringement_matrix_entry', empty_scorer), \
         patched(cases_module, 'update_case', lambda *a, **kw: None):
        _hit_endpoint(flask_client, headers={'X-User-ID': USER_ID})

    _print_header('9. Stubbed: success path -> 200 with chart_data')

    def good_scorer(parent_claims, inf_claims, existing, threshold=0.5):
        rows = [{
            'ref_claim': parent_claims[0],
            'infringing_claim': inf_claims[0],
            'similarity_score': 0.92,
            'evaluation_method': 'embedding_cosine',
            'last_evaluated': '2026-05-11T00:00:00Z',
        }]
        return rows, rows

    with patched(cases_module, 'getDataById', make_stub_case(
        claims=['1. A device comprising a widget.'],
        infringements=[{'claims': ['A device having a widget.']}],
    )), patched(cases_module, 'score_infringement_matrix_entry', good_scorer), \
         patched(cases_module, 'update_case', lambda *a, **kw: None):
        _hit_endpoint(flask_client, headers={'X-User-ID': USER_ID})

    _print_header('Done.')


if __name__ == '__main__':
    sys.exit(main() or 0)
