#!/usr/bin/env python3
"""UNTESTED here (needs `pip install evalplus`). HumanEval+ -> pilot task file.
PILOT APPROXIMATION: 'public' = first 3 base inputs (real study: use docstring examples). Expected outputs come from the
canonical solution. MBPP+ prompts carry no type hints -> CrossHair would mark them UNSUPPORTED; add signatures first."""
import argparse, ast, copy, json, random
from evalplus.data import get_human_eval_plus
ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=40); ap.add_argument("--seed", type=int, default=2026)
ap.add_argument("--out", default="pilot_tasks.jsonl"); a = ap.parse_args()
data = list(get_human_eval_plus().values()); random.Random(a.seed).shuffle(data); out = []
for p in data[:a.n]:
    ns = {}; exec("from typing import *\n" + p["prompt"] + p["canonical_solution"], ns); f = ns[p["entry_point"]]; tests = []
    for inp in list(p["base_input"]) + list(p["plus_input"]):
        try:
            e = f(*copy.deepcopy(inp)); t = [repr(tuple(inp)), repr(e)]; ast.literal_eval(t[0]); ast.literal_eval(t[1]); tests.append(t)
        except Exception: continue
    out.append({"task_id": p["task_id"], "entry_point": p["entry_point"], "prompt": p["prompt"],
                "public_tests": tests[:3], "hidden_tests": tests[3:]})
open(a.out, "w").write("\n".join(json.dumps(t) for t in out) + "\n")
print(len(out), "tasks ->", a.out, "| EXCLUDE these ids from the confirmatory sample:", [t["task_id"] for t in out])
