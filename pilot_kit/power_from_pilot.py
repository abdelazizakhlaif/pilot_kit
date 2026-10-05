#!/usr/bin/env python3
"""Re-run the power simulation with parameters measured in the pilot (point / pessimistic / optimistic)."""
import json, sys
import power_sim as P
P.SIMS, P.PERMS = 500, 1000
S = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "pilot_summary.json"))
def avg(k, which):
    v = [m[k][which] for m in S["models"].values() if m[k][which] is not None]
    return sum(v) / len(v) if v else None
def pick(k, kind, default):
    pt = avg(k, "est"); lo = avg(k, "lo") if avg(k, "lo") is not None else pt; hi = avg(k, "hi") if avg(k, "hi") is not None else pt
    if pt is None: return default
    return {"point": pt, "low": lo, "high": hi}[kind]
scen = {"point":       dict(cov="point", a_v="point", a_t="point"),
        "pessimistic": dict(cov="low", a_v="low", a_t="high"),
        "optimistic":  dict(cov="high", a_v="high", a_t="low")}
print("N tasks | scenario | p0 cov a_v a_t | power vs Control (C1/C2) | power vs Test Repair (C3/C4)")
for name, kinds in scen.items():
    p0 = pick("p0", "point", 0.6); cov = pick("cov", kinds["cov"], 0.5)
    a_v = pick("a_v", kinds["a_v"], 0.3); a_t = pick("a_t", kinds["a_t"], 0.2)
    rv, rt = pick("reg_v", "point", 0.02), pick("reg_t", "point", 0.02)
    for N in (100, 200, 300, 542):
        r = P.run(N, min(max(p0, .05), .95), cov, a_v, a_t, rv, rt)
        print(f"{N:4d} | {name:11s} | {p0:.2f} {cov:.2f} {a_v:.2f} {a_t:.2f} | {r['power_ctrl']:.2f} | {r['power_test']:.2f}   (true effects {r['eff_ctrl']:+.3f} / {r['eff_test']:+.3f})")
