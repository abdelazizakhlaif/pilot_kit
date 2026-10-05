"""Synthetic tasks for PLUMBING TESTS ONLY (not research data)."""
import json
D = [
 ("double_all", "xs: List[int]", "List[int]", "[2 * x for x in xs]", "[2 * x for x in xs if x > 0]",
  [([1,2,3],),([],),([5],),([-1,5],),([0],),([4,-4,9],),([-2],)], {"post": ["len(__return__) == len(xs)"]}),
 ("clamp", "x: int, lo: int, hi: int", "int", "min(max(x, lo), hi)", "min(x, hi)",
  [(5,0,10),(3,3,3),(0,0,0),(-5,0,10),(15,0,10),(7,1,2),(-9,-8,-7)], {"pre": ["lo <= hi"], "post": ["lo <= __return__ <= hi"]}),
 ("is_even", "n: int", "bool", "n % 2 == 0", "(n % 2 == 0) if n >= 0 else True",
  [(2,),(3,),(0,),(-3,),(-4,),(7,),(10,)], {"post": ["__return__ == (n % 2 == 0)"]}),
 ("abs_diff", "a: int, b: int", "int", "abs(a - b)", "a - b",
  [(5,3),(3,3),(0,0),(3,5),(-2,2),(9,1),(1,9)], {"post": ["__return__ >= 0"]}),
 ("count_pos", "xs: List[int]", "int", "sum(1 for x in xs if x > 0)", "sum(1 for x in xs if x >= 0)",
  [([1,2],),([-1,-2],),([5],),([0],),([0,1],),([],),([3,-3,0],)], {"post": ["0 <= __return__ <= len(xs)"]}),
 ("last_char", "s: str", "str", "s[-1] if s else ''", "s[-1]",
  [("abc",),("z",),("hello",),("",),("ab",),("q",),("",)], {"post": ["len(__return__) <= 1"]}),
 ("max_of", "xs: List[int]", "int", "max(xs)", "sorted(xs)[0]",
  [([1,2,3],),([5],),([9,1],),([3,2,1],),([-1,-5],),([0,0],),([4,8,6],)], {"pre": ["len(xs) > 0"], "post": ["__return__ in xs", "all(__return__ >= x for x in xs)"]}),
 ("repeat", "s: str, k: int", "str", "s * k", "s * (k + 1) if k > 2 else s * k",
  [("ab",2),("x",1),("a",0),("ab",3),("c",5),("d",4),("e",2)], {"pre": ["k >= 0"], "post": ["len(__return__) == len(s) * k"]}),
]
out = []
for name, sig, ret, good, bad, inputs, spec in D:
    mk = lambda body: f"def {name}({sig}) -> {ret}:\n    return {body}"
    prompt = f"from typing import List\n\n\ndef {name}({sig}) -> {ret}:\n    \"\"\"Implement {name}.\"\"\"\n"
    ns = {}; exec("from typing import *\n" + mk(good), ns); f = ns[name]
    tests = [[repr(tuple(i)), repr(f(*i))] for i in inputs]
    out.append({"task_id": "demo/" + name, "entry_point": name, "prompt": prompt,
                "public_tests": tests[:3], "hidden_tests": tests[3:],
                "_demo": {"canonical_code": mk(good), "buggy_code": mk(bad), "spec": spec,
                          "probe_inputs": [list(i) for i in inputs]}})
open("demo_tasks.jsonl", "w").write("\n".join(json.dumps(t) for t in out) + "\n")
print(len(out), "demo tasks written")
