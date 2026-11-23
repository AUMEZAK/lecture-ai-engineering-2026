"""Run the course CLI and retain measured outputs for a top-k comparison."""
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import hashlib
import io
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
EVIDENCE = ROOT / "lectures/05/evidence/basic_topk"
QUESTIONS = {
    "lora": "第2回の説明では、LoRAは何を固定し何を学習しますか？ QLoRAは何を加えますか？",
    "memory": "第3回の例では、コンパクションとセッションをまたぐメモリはどう違いますか。日々のメモはすべて長期メモリに入りますか",
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sanitize(text):
    key = os.environ.get("GEMINI_API_KEY")
    return text.replace(key, "[REDACTED]") if key else text


def run_one(phase, mode, qid):
    import app.agent as cli
    from app import config
    from pydantic_ai.messages import ToolCallPart, ToolReturnPart

    expected = 5 if phase == "before" else 2
    assert config.RAG_TOP_K == expected, (config.RAG_TOP_K, expected)
    question = QUESTIONS[qid]
    run_id = f"{phase}_{mode}_{qid}"
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    destination = EVIDENCE / f"{run_id}.json"
    if destination.exists():
        raise SystemExit(f"Existing result preserved: {destination}")
    data = {
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "mode": mode,
        "top_k": config.RAG_TOP_K,
        "model_requested": config.MODEL,
        "temperature": "not explicitly set; unchanged SDK/API default",
        "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_sha256": {str(p.relative_to(ROOT)): digest(p) for p in [
            ROOT / "app/config.py", ROOT / "app/agent.py", ROOT / "app/tools.py",
            ROOT / "app/retrieval.py", config.RAG_SOURCE, config.RAG_DB, ROOT / "uv.lock",
        ]},
        "cost_scope": "generation API estimate only; query embedding and index creation excluded",
        "tool_calls": [],
        "tool_returns": [],
    }
    original_trace = cli.print_trace

    def record_trace(result, elapsed_seconds=None):
        original_trace(result, elapsed_seconds)
        usage = result.usage
        data.update(answer=result.output, elapsed_seconds=elapsed_seconds,
                    input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
                    model_requests=usage.requests,
                    generation_cost_usd=None if usage.cost is None else float(usage.cost))
        names = set()
        for message in result.all_messages():
            if getattr(message, "model_name", None):
                names.add(message.model_name)
            for part in message.parts:
                if isinstance(part, ToolCallPart):
                    args = part.args
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except ValueError:
                            pass
                    data["tool_calls"].append({"name": part.tool_name, "arguments": args,
                                               "call_id": part.tool_call_id})
                elif isinstance(part, ToolReturnPart):
                    payload = json.loads(part.content)
                    returned = {"name": part.tool_name, "call_id": part.tool_call_id,
                                "error": payload.get("error"), "pages": []}
                    pages = payload.get("results", []) + payload.get("seeds", []) + payload.get("expanded", [])
                    node = payload.get("node", {})
                    if node.get("kind") == "page" and not payload.get("children"):
                        pages.append({**node, "page_id": node["id"]})
                    for page in pages:
                        content = page.get("content", "")
                        metadata = {k: v for k, v in page.items() if k != "content"}
                        metadata["content_sha256"] = hashlib.sha256(content.encode()).hexdigest()
                        metadata["content_characters"] = len(content)
                        returned["pages"].append(metadata)
                    if "node" in payload:
                        returned["tree_node_id"] = node.get("id")
                        returned["children_ids"] = [c["id"] for c in payload.get("children", [])]
                    data["tool_returns"].append(returned)
        data["model_names_returned"] = sorted(names)

    cli.print_trace = record_trace
    flags = [] if mode == "vector" else ["--" + mode]
    sys.argv = ["app.agent", *flags, "--trace", question]
    data["command"] = ["uv", "run", "--frozen", "python", "-m", "app.agent", *flags, "--trace", question]
    data["measurement_method"] = "course CLI main; print_trace wrapper records result after timing; no extra model calls"
    stream = io.StringIO()
    status = 0
    with redirect_stdout(stream), redirect_stderr(stream):
        try:
            cli.main()
        except (Exception, SystemExit) as error:
            status = 1
            print(type(error).__name__ + ": " + str(error))
    data["status"] = "ok" if status == 0 else "error"
    data["finished_at"] = datetime.now(timezone.utc).isoformat()
    (EVIDENCE / f"{run_id}.log").write_text(sanitize(stream.getvalue()))
    destination.write_text(sanitize(json.dumps(data, ensure_ascii=False, indent=2)))
    print(run_id, data["status"], data.get("elapsed_seconds"), data.get("input_tokens"), data.get("output_tokens"), flush=True)
    return status


def main():
    if len(sys.argv) == 5 and sys.argv[1] == "--one":
        raise SystemExit(run_one(*sys.argv[2:]))
    phase = sys.argv[1]
    assert phase in ("before", "after")
    tasks = [("vector", "lora"), ("vector", "memory")]
    if phase == "before":
        tasks = [("full-context", "lora"), *tasks, ("tree", "lora"), ("graph", "lora")]
    for index, (mode, qid) in enumerate(tasks):
        subprocess.run([sys.executable, str(Path(__file__).resolve()), "--one", phase, mode, qid], cwd=ROOT, check=True)
        if index + 1 < len(tasks):
            time.sleep(15)


if __name__ == "__main__":
    main()
