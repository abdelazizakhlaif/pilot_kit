#!/usr/bin/env python3
"""Pilot runner: Control / Test Repair / Verification Repair on a shared initial candidate. Resumable."""
import argparse, json, os, time
import core
from llm import make_llm, extract_code, extract_json

def gen_prompt(t):
    return (f"### TASK_ID: {t['task_id']}\n### MODE: gen\nComplete the following Python function. "
            f"Return only the complete function in one ```python code block.\n\n{t['prompt']}")

def repair_prompt(t, code, fb, kind):
    return (f"### TASK_ID: {t['task_id']}\n### MODE: repair\n### FEEDBACK_KIND: {kind}\n"
            f"The solution below to the task is incorrect.\n\nTask:\n{t['prompt']}\n\nCurrent solution:\n```python\n{code}\n```\n\n"
            f"Feedback:\n{fb}\n\nReturn only the corrected complete function in one ```python code block.")

def spec_prompt(t):
    return (f"### TASK_ID: {t['task_id']}\n### MODE: spec\nWrite a formal contract for the function below from its "
            f"description ONLY (do not implement it). Output a JSON object {{\"pre\": [...], \"post\": [...]}} in a ```json block. "
            f"Each item is a Python boolean expression over the parameter names; in post-conditions use __return__ for the return value.\n\n{t['prompt']}")

def load_done(path):
    specs, runs = {}, set()
    if os.path.exists(path):
        for line in open(path):
            r = json.loads(line)
            if r["type"] == "spec": specs[r["task_id"]] = r
            else: runs.add((r["model"], r["task_id"], r["gen"]))
    return specs, runs

def run_one(llm, t, spec_rec, g, a, verify):
    entry, pre = t["entry_point"], t["prompt"]
    pub, allt = t["public_tests"], t["public_tests"] + t["hidden_tests"]
    seed = a.seed * 1000 + g
    rec = {"type": "run", "model": llm.name, "task_id": t["task_id"], "gen": g}
    t0 = time.time()
    init = extract_code(llm.chat(gen_prompt(t), seed))
    ok_all, _ = core.run_tests(init, entry, allt, pre)
    ok_pub, fb = core.run_tests(init, entry, pub, pre)
    rec.update(init_pass=ok_all, init_pub=ok_pub, ctrl_y=ok_all)
    # --- Test Repair arm: repair only while public tests fail (no info -> no repair)
    cur, calls = init, 0
    for r in range(a.rounds):
        if ok_pub: break
        cur = extract_code(llm.chat(repair_prompt(t, cur, fb, "test"), seed + 100 * (r + 1))); calls += 1
        ok_pub, fb = core.run_tests(cur, entry, pub, pre)
    rec["test"] = {"y": core.run_tests(cur, entry, allt, pre)[0], "calls": calls}
    # --- Verification Repair arm: repair only on a verifier FAIL (counterexample)
    cur, calls, sts = init, 0, []
    if spec_rec["valid"]:
        for r in range(a.rounds):
            st, cex = verify(cur, t, spec_rec["spec"]); sts.append(st)
            if st != "FAIL": break
            fbv = "Verifier counterexample: " + cex + ("\nContract: " + json.dumps(spec_rec["spec"]) if a.show_spec else "")
            cur = extract_code(llm.chat(repair_prompt(t, cur, fbv, "verifier"), seed + 100 * (r + 1))); calls += 1
    else:
        sts = ["NO_SPEC"]
    rec["ver"] = {"y": core.run_tests(cur, entry, allt, pre)[0], "calls": calls, "statuses": sts}
    rec["secs"] = round(time.time() - t0, 2)
    return rec

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True); ap.add_argument("--n-tasks", type=int, default=40)
    ap.add_argument("--gen-models", required=True, help="comma list, e.g. ollama:qwen2.5-coder:1.5b,ollama:llama3.2:3b")
    ap.add_argument("--spec-model", required=True); ap.add_argument("--verifier", choices=["crosshair", "stub"], default="crosshair")
    ap.add_argument("--gens", type=int, default=3); ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--seed", type=int, default=1); ap.add_argument("--show-spec", action="store_true")
    ap.add_argument("--cx-timeout", type=int, default=10); ap.add_argument("--out", default="traces.jsonl")
    a = ap.parse_args()
    tasks = [json.loads(l) for l in open(a.tasks)][:a.n_tasks]
    table = {t["task_id"]: t for t in tasks}
    verify = (lambda c, t, s: core.crosshair_verify(c, t, s, a.cx_timeout)) if a.verifier == "crosshair" else core.stub_verify
    specs, done = load_done(a.out)
    out = open(a.out, "a")
    emit = lambda r: (out.write(json.dumps(r) + "\n"), out.flush())
    spec_llm = make_llm(a.spec_model, table)
    for t in tasks:                                   # one frozen spec per task, from the spec model only
        if t["task_id"] in specs: continue
        spec = extract_json(spec_llm.chat(spec_prompt(t), a.seed))
        ok, why = core.spec_valid(spec, t)
        specs[t["task_id"]] = {"type": "spec", "task_id": t["task_id"], "spec_model": spec_llm.name,
                               "spec": spec, "valid": ok, "reason": why}
        emit(specs[t["task_id"]])
    for m in a.gen_models.split(","):
        llm = make_llm(m, table)
        for t in tasks:
            for g in range(a.gens):
                if (llm.name, t["task_id"], g) in done: continue
                emit(run_one(llm, t, specs[t["task_id"]], g, a, verify))
                print(f"{llm.name} {t['task_id']} gen{g} done", flush=True)

if __name__ == "__main__":
    main()
