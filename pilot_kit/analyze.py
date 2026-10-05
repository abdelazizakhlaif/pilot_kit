#!/usr/bin/env python3
"""Summarise pilot traces -> pilot_summary.json + table. Bootstrap over TASKS (stdlib only). DESCRIPTIVE ONLY."""
import json, random, sys, collections
COVERED = ("PASS", "FAIL")

def boot(groups, stat, B=2000, seed=7):
    pt = stat([r for g in groups for r in g]); rnd = random.Random(seed); vals = []
    for _ in range(B):
        s = stat([r for g in (rnd.choice(groups) for _ in groups) for r in g])
        if s is not None: vals.append(s)
    vals.sort()
    ci = (vals[int(.025 * len(vals))], vals[int(.975 * len(vals)) - 1]) if len(vals) > 20 else (None, None)
    return {"est": pt, "lo": ci[0], "hi": ci[1]}

def mean(xs): xs = list(xs); return sum(xs) / len(xs) if xs else None
S = {
 "p0":        lambda R: mean(r["ctrl_y"] for r in R),
 "Y_test":    lambda R: mean(r["test"]["y"] for r in R),
 "Y_ver":     lambda R: mean(r["ver"]["y"] for r in R),
 "cov":       lambda R: mean(r["ver"]["statuses"][0] in COVERED for r in R),
 "a_t":       lambda R: mean(r["test"]["y"] for r in R if not r["init_pass"]),
 "a_v":       lambda R: mean(r["ver"]["y"] for r in R if not r["init_pass"] and r["ver"]["statuses"][0] in COVERED),
 "reg_t":     lambda R: mean(not r["test"]["y"] for r in R if r["init_pass"]),
 "reg_v":     lambda R: mean(not r["ver"]["y"] for r in R if r["init_pass"]),
 "diff_ver_ctrl": lambda R: mean(r["ver"]["y"] - r["ctrl_y"] for r in R),
 "diff_ver_test": lambda R: mean(r["ver"]["y"] - r["test"]["y"] for r in R),
 "diff_test_ctrl": lambda R: mean(r["test"]["y"] - r["ctrl_y"] for r in R),
}
def main(path):
    specs, runs = [], collections.defaultdict(lambda: collections.defaultdict(list))
    for l in open(path):
        r = json.loads(l)
        if r["type"] == "spec": specs.append(r)
        else: runs[r["model"]][r["task_id"]].append(r)
    summ = {"n_tasks": len(specs), "spec_valid_rate": mean(s["valid"] for s in specs),
            "spec_invalid_reasons": dict(collections.Counter(s["reason"] for s in specs if not s["valid"])), "models": {}}
    for m, bytask in runs.items():
        groups = list(bytask.values()); allr = [r for g in groups for r in g]
        d = {k: boot(groups, f) for k, f in S.items()}
        d["first_status"] = dict(collections.Counter(r["ver"]["statuses"][0] for r in allr))
        d["median_secs_per_run"] = sorted(r["secs"] for r in allr)[len(allr) // 2]
        summ["models"][m] = d
    json.dump(summ, open("pilot_summary.json", "w"), indent=1)
    f = lambda x: "  n/a " if x["est"] is None else f"{x['est']:.2f}" + ("" if x["lo"] is None else f" [{x['lo']:.2f},{x['hi']:.2f}]")
    print(f"tasks={summ['n_tasks']}  spec_valid_rate={summ['spec_valid_rate']:.2f}  invalid={summ['spec_invalid_reasons']}")
    if summ["n_tasks"] < 30: print("!! fewer than 30 tasks: intervals will be very wide")
    for m, d in summ["models"].items():
        print(f"\n== {m}   first verifier status: {d['first_status']}")
        for k in S: print(f"  {k:15s} {f(d[k])}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "traces.jsonl")
