import json
import os
import sys

from dotenv import load_dotenv

from background_analysis import run_infringement_analysis_for_case


def main():
  load_dotenv()

  raw_payload = os.environ.get('ANALYSIS_PAYLOAD', '')
  if raw_payload == '':
    print('ERROR: ANALYSIS_PAYLOAD environment variable is required')
    return 1

  try:
    payload = json.loads(raw_payload)
  except json.JSONDecodeError as e:
    print(f'ERROR: ANALYSIS_PAYLOAD is not valid JSON: {str(e)}')
    return 1

  case_id = payload.get('case_id')
  if not case_id:
    print('ERROR: case_id is required in ANALYSIS_PAYLOAD')
    return 1

  print(f'LOG: Background analysis cron started for case_id: {case_id}')
  result, status_code = run_infringement_analysis_for_case(case_id, payload)
  print(json.dumps({
    'status_code': status_code,
    'result': result
  }, indent=2, default=str))

  if status_code < 200 or status_code >= 300:
    return 1
  return 0


if __name__ == '__main__':
  sys.exit(main())
