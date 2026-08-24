#!/usr/bin/env python3
"""
Pull the JSON array each research subagent returned as its final message, straight from its
task transcript file — so the orchestrator never has to hold hundreds of listings in context.

    CLAUDE_TASKS_DIR=/path/to/session/tasks \
    AGENT_ROWS_OUT=agent_rows.json \
    python3 extract.py <agentId> [<agentId> ...]
"""
import json, sys, os, re

TASKS = os.environ.get("CLAUDE_TASKS_DIR", ".")


def texts(path):
    """Every assistant text block, in order."""
    out = []
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        if o.get("type") != "assistant":
            continue
        content = (o.get("message") or {}).get("content")
        if isinstance(content, str):
            out.append(content)
        elif isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "text":
                    out.append(b.get("text") or "")
    return out


def find_array(blob):
    """Largest well-formed JSON array of objects in a text blob."""
    best = None
    for m in re.finditer(r"\[", blob):
        start, depth, instr, esc = m.start(), 0, False, False
        for i in range(start, len(blob)):
            c = blob[i]
            if instr:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    instr = False
                continue
            if c == '"':
                instr = True
            elif c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    try:
                        v = json.loads(blob[start:i + 1])
                    except Exception:
                        break
                    if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
                        if best is None or len(v) > len(best):
                            best = v
                    break
    return best


def extract(agent_id):
    path = os.path.join(TASKS, agent_id + ".output")
    if not os.path.exists(path):
        return None, "no output file"
    blocks = texts(path)
    for blob in reversed(blocks):
        arr = find_array(blob)
        if arr:
            return arr, None
    return None, f"no JSON array in {len(blocks)} assistant blocks"


if __name__ == "__main__":
    allrows, report = [], []
    for aid in sys.argv[1:]:
        rows, err = extract(aid)
        if rows is None:
            report.append((aid, 0, err))
            continue
        for r in rows:
            r["_agent"] = aid
        allrows.extend(rows)
        report.append((aid, len(rows), ""))
    for aid, n, err in report:
        print(f"{aid}: {n} rows {err}")
    out = os.environ.get("AGENT_ROWS_OUT", "agent_rows.json")
    json.dump(allrows, open(out, "w"), ensure_ascii=False, indent=1)
    print("TOTAL", len(allrows), "->", out)
