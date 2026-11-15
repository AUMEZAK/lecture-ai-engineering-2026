"""同じケース・本人確認済みラベル・モデルで、根拠の方針変更を比較する。"""
from pathlib import Path
import datetime
import difflib
import hashlib
import importlib.metadata
import json
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'lectures/04'
EVIDENCE = BASE / 'evidence/basic_comparison'
RUBRIC = ROOT / 'data/eval/rubric.md'
LABELS = BASE / 'labels.jsonl'
MODEL = 'gemini-3.5-flash-lite'
KEYS = ('grounding', 'scope', 'hint', 'clarity', 'lecture_mark')
SOURCE_COMMIT = 'bc41dfac203acff0706b7da10d09339d91830bfe'
LABEL_HASH = 'cf1688d45e38889069dd1831b2bebf0061da3c20985e0eb4e16a912f4c40183a'
RUBRIC_HASH = '38b9f33a5ba0a93359ed78651b3048821c58f856d6a9839f79d8e90ba8bd5198'
FIXED = ['data/eval/lec04_cases.jsonl', 'data/glossary.json', 'lectures/04/labels.jsonl',
         'app/judge.py', 'app/config.py', 'app/tools.py', 'uv.lock']

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def dump(name, obj):
    (EVIDENCE / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def run():
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if head != SOURCE_COMMIT:
        raise SystemExit(f'Unexpected source HEAD: {head}')
    if digest(LABELS) != LABEL_HASH or digest(RUBRIC) != RUBRIC_HASH:
        raise SystemExit('Labels or baseline rubric differ from the fixed inputs.')
    rows = [json.loads(x) for x in LABELS.read_text().splitlines() if x.strip()]
    cases = [json.loads(x) for x in (ROOT / FIXED[0]).read_text().splitlines() if x.strip()]
    ids = [x['id'] for x in cases]
    if len(ids) != 10 or len(set(ids)) != 10 or [x['id'] for x in rows] != ids:
        raise SystemExit('Require exactly the same 10 unique case IDs in labels.')
    if any(x.get(k) not in ('pass', 'fail') for x in rows for k in KEYS):
        raise SystemExit('Every label must have five pass/fail verdicts.')
    original = RUBRIC.read_text(encoding='utf-8')
    undecided = '- 用語集にない語について、「用語集にはない」と伝えたうえで一般的な説明をすることが、「推測で断定する」にあたるかどうか'
    anchor = '- 回答が「分からない」「用語集にはない」と伝えているだけなら、矛盾はないので pass'
    policy = '- 用語集にない語を、「用語集にはない」と伝えたうえで一般的に説明するのは、断定ではない（pass）'
    if original.count(undecided) != 1 or original.count(anchor) != 1:
        raise SystemExit('Expected exactly one target policy and grounding anchor.')
    revised = original.replace(anchor, anchor+'\n'+policy).replace(undecided+'\n', '')
    EVIDENCE.mkdir(parents=True, exist_ok=False)
    (EVIDENCE / 'rubric.before.md').write_text(original, encoding='utf-8')
    (EVIDENCE / 'rubric.after.md').write_text(revised, encoding='utf-8')
    (EVIDENCE / 'rubric.patch').write_text(''.join(difflib.unified_diff(
        original.splitlines(True), revised.splitlines(True),
        fromfile='data/eval/rubric.md (before)', tofile='data/eval/rubric.md (after)')), encoding='utf-8')
    fixed_hashes = {p: digest(ROOT/p) for p in FIXED}
    meta = {'status': 'running', 'source_commit': head, 'requested_model': MODEL,
            'model_reported_by_cli': None, 'server_model_version': 'not exposed by course CLI',
            'temperature': 0, 'repetitions_per_condition': 1,
            'human_label_method': '提示された判定案を本人が各件ごとに確認したラベル。独立した盲検判定ではない。',
            'changed_policy': '根拠: 用語集にないと明示した一般説明を許容する',
            'fixed_hashes': fixed_hashes, 'started_utc': now(), 'runs': {},
            'packages': {n: importlib.metadata.version(n) for n in ['google-genai', 'pydantic-ai-slim']}}
    dump('execution.json', meta)
    try:
        for phase in ('baseline', 'variant'):
            if phase == 'variant':
                if digest(RUBRIC) != RUBRIC_HASH:
                    raise RuntimeError('Baseline rubric changed unexpectedly.')
                RUBRIC.write_text(revised, encoding='utf-8')
            if any(digest(ROOT/p) != h for p,h in fixed_hashes.items()):
                raise RuntimeError('A fixed input changed.')
            command = [sys.executable, '-m', 'app.judge', '--model', MODEL, '--wait', '5',
                       '--cases', 'data/eval/lec04_cases.jsonl', '--labels', 'lectures/04/labels.jsonl',
                       '--rubric', 'data/eval/rubric.md',
                       '--out', f'lectures/04/evidence/basic_comparison/{phase}.json']
            info = {'command': command, 'started_utc': now(), 'rubric_sha256': digest(RUBRIC)}
            meta['runs'][phase] = info
            dump('execution.json', meta)
            started = time.monotonic()
            with (EVIDENCE / f'{phase}.log').open('w') as log:
                result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=1200)
            info.update(ended_utc=now(), elapsed_seconds=round(time.monotonic()-started, 3),
                        exit_code=result.returncode, log_sha256=digest(EVIDENCE/f'{phase}.log'))
            dump('execution.json', meta)
            if result.returncode:
                raise RuntimeError(f'{phase} failed; see the preserved log.')
            output = json.loads((EVIDENCE/f'{phase}.json').read_text())
            if output['model'] != MODEL or set(output['verdicts']) != set(ids):
                raise RuntimeError('Result model or case IDs differ.')
            info['result_sha256'] = digest(EVIDENCE/f'{phase}.json')
            meta['model_reported_by_cli'] = output['model']
            print(json.dumps({'phase':phase, 'summary':output['summary']},ensure_ascii=False), flush=True)
        if any(digest(ROOT/p) != h for p,h in fixed_hashes.items()):
            raise RuntimeError('A fixed input changed after comparison.')
        meta.update(status='completed', ended_utc=now(), rubric_after_sha256=digest(RUBRIC))
        dump('execution.json', meta)
        print('COMPARISON_COMPLETED', flush=True)
    except BaseException as exc:
        meta.update(status='failed', ended_utc=now(), error_type=type(exc).__name__, error=str(exc))
        dump('execution.json', meta)
        raise

if __name__ == '__main__':
    run()
