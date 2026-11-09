"""Execute the lecture-03 basic comparison with the real CLI."""
import ast
import difflib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path.cwd()
TARGET = ROOT / "app/tools.py"
OUT = ROOT / "lectures/03/evidence"
QUESTION = 'LoRAとQLoRAの違いは？'
OLD = '答える前に使うこと。query には調べたい用語を1つだけ入れる（例: "LoRA"）。'
NEW = '答える前に使うこと。query には比較したい用語をまとめて入れる（例: "LoRA QLoRA"）。'

def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def run(condition):
    command = ["uv", "run", "python", "-m", "app.agent", "--trace", QUESTION]
    started = datetime.now(timezone.utc).isoformat()
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
        output, code = result.stdout + result.stderr, result.returncode
    except subprocess.TimeoutExpired as error:
        output = "TIMEOUT after 180 seconds\n"
        for part in (error.stdout, error.stderr):
            if part:
                output += part.decode("utf-8", errors="replace") if isinstance(part, bytes) else part
        code = 124
    (OUT / (condition + ".txt")).write_text(output, encoding="utf-8")
    print(condition, "exit", code, flush=True)
    print(output, flush=True)
    return {"command": command, "started_utc": started, "exit_code": code, "log_sha256": digest(output)}

def main():
    if not TARGET.is_file():
        raise SystemExit("Run from the course repository root")
    if not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit("GEMINI_API_KEY not set; no API calls made")
    if OUT.exists():
        raise SystemExit("Evidence already exists; refusing overwrite")
    before = TARGET.read_text(encoding="utf-8")
    assert before.count(OLD) == 1
    after = before.replace(OLD, NEW, 1)
    trees = [ast.parse(before), ast.parse(after)]
    for tree in trees:
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "search_glossary")
        fn.body.pop(0)
    assert ast.dump(trees[0]) == ast.dump(trees[1])
    OUT.mkdir(parents=True)
    metadata = {"status":"running", "question":QUESTION,
        "repetitions_per_condition":1,
        "source_commit":subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
        "before_source_sha256":digest(before), "after_source_sha256":digest(after),
        "glossary_sha256":hashlib.sha256((ROOT / "data/glossary.json").read_bytes()).hexdigest(),
        "model_environment":os.environ.get("AIE_MODEL","course default"),
        "baseline_tests":"11 passed in 6.12s (terminal observation)",
        "omnicampus_submitted_by_assistant":False}
    record = OUT / "execution.json"
    record.write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+"\n")
    metadata["baseline"] = run("baseline")
    if metadata["baseline"]["exit_code"]:
        metadata["status"] = "baseline_failed_no_source_change"
    else:
        TARGET.write_text(after,encoding="utf-8")
        patch = "".join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile="a/app/tools.py",tofile="b/app/tools.py"))
        (OUT / "docstring.patch").write_text(patch,encoding="utf-8")
        metadata["variant"] = run("variant")
        metadata["status"] = "complete" if not metadata["variant"]["exit_code"] else "variant_failed"
    record.write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+"\n")
    print("EVIDENCE_STATUS",metadata["status"],flush=True)
    return 0 if metadata["status"] == "complete" else 1

if __name__ == "__main__":
    sys.exit(main())
