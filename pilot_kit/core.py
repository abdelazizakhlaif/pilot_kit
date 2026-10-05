"""Sandbox evaluation, spec validation, verifiers. WARNING: executes model-written code in a subprocess
(timeout only, NOT a real sandbox). Run inside a container/VM you can discard."""
import ast, builtins, json, math, os, subprocess, sys, tempfile

RUNNER = r'''
import json, sys, ast, math
d = json.load(open(sys.argv[1])); ns = {}
def out(ok, fail): print(json.dumps({"ok": ok, "fail": fail})); sys.exit(0)
try:
    exec(compile(d["code"], "<cand>", "exec"), ns); f = ns[d["entry"]]
except BaseException as e:
    out(False, "definition error: %s: %s" % (type(e).__name__, str(e)[:200]))
def same(a, b):
    if isinstance(a, float) or isinstance(b, float):
        try: return math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-6)
        except Exception: return False
    return a == b
for args_r, exp_r in d["tests"]:
    args = ast.literal_eval(args_r); exp = ast.literal_eval(exp_r)
    try: got = f(*args)
    except BaseException as e:
        out(False, ("input=%s expected=%s raised %s: %s" % (args_r, exp_r, type(e).__name__, str(e)[:120]))[:400])
    if not same(got, exp): out(False, ("input=%s expected=%s got=%r" % (args_r, exp_r, got))[:400])
out(True, None)
'''

def run_tests(code, entry, tests, prefix="", timeout=10):
    """tests: list of [args_repr, expected_repr]. Returns (ok, first_failure_text)."""
    full = "from typing import *\n" + prefix + "\n" + code
    with tempfile.TemporaryDirectory() as td:
        open(os.path.join(td, "r.py"), "w").write(RUNNER)
        json.dump({"code": full, "entry": entry, "tests": tests}, open(os.path.join(td, "d.json"), "w"))
        try:
            r = subprocess.run([sys.executable, os.path.join(td, "r.py"), os.path.join(td, "d.json")],
                               capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL, cwd=td)
        except subprocess.TimeoutExpired:
            return False, "timeout"
    try:
        res = json.loads(r.stdout.strip().splitlines()[-1])
        return res["ok"], res["fail"]
    except Exception:
        return False, "no-result: " + (r.stderr or "")[-200:]

def get_fn(prompt, entry):
    for src in (prompt, prompt + "\n    pass\n"):
        try: tree = ast.parse(src)
        except SyntaxError: continue
        fns = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == entry]
        if fns: return fns[-1], tree
    return None, None

def params_of(task):
    fn, _ = get_fn(task["prompt"], task["entry_point"])
    return [a.arg for a in fn.args.args] if fn else []

SAFE = {k: getattr(builtins, k) for k in ["len", "sum", "min", "max", "abs", "all", "any", "sorted", "set", "list",
        "range", "isinstance", "int", "float", "str", "bool", "tuple", "dict", "round", "enumerate", "zip", "reversed"]}

def _ev(expr, ns):
    return bool(eval(compile(ast.parse(expr, mode="eval"), "<spec>", "eval"), {"__builtins__": SAFE, "math": math}, ns))

def spec_valid(spec, task):
    """Non-oracle validity: well-formed AND holds on the PUBLIC examples (which are known correct)."""
    if not isinstance(spec, dict): return False, "not-json"
    pre, post = spec.get("pre", []), spec.get("post", [])
    if not post or not all(isinstance(x, str) for x in pre + post): return False, "empty-or-nonstring"
    names = params_of(task)
    for a_r, e_r in task["public_tests"]:
        try:
            ns = dict(zip(names, ast.literal_eval(a_r)))
            if not all(_ev(p, ns) for p in pre): return False, "pre-false-on-public"
            ns["__return__"] = ast.literal_eval(e_r)
            if not all(_ev(p, ns) for p in post): return False, "post-false-on-public"
        except Exception as ex:
            return False, "error:" + type(ex).__name__
    return True, "ok"

# ---------- verifiers: return (status, counterexample_text); status in PASS/FAIL/UNKNOWN/UNSUPPORTED ----------
def build_contract_module(code, task, spec):
    fn, _ = get_fn(task["prompt"], task["entry_point"])
    if fn is None: return None
    a = fn.args
    if a.vararg or a.kwarg or a.kwonlyargs or fn.returns is None or any(x.annotation is None for x in a.args):
        return None  # no type hints -> CrossHair cannot generate inputs
    one = lambda s: " ".join(s.split())
    doc = ["pre: " + one(p) for p in spec.get("pre", [])] + ["post: " + one(p) for p in spec["post"]]
    wrapper = (f"def {fn.name}__contract({ast.unparse(a)}) -> {ast.unparse(fn.returns)}:\n"
               + '    """\n' + "".join(f"    {l}\n" for l in doc) + '    """\n'
               + f"    return {fn.name}({', '.join(x.arg for x in a.args)})\n")
    return "from typing import *\n" + task["prompt"] + "\n" + code + "\n\n" + wrapper

def crosshair_verify(code, task, spec, per_cond_timeout=10, total_timeout=180):
    # UNTESTED against a live CrossHair install: run `python core.py --selftest` first.
    src = build_contract_module(code, task, spec)
    if src is None: return "UNSUPPORTED", ""
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "m.py"); open(p, "w").write(src)
        try:
            r = subprocess.run([sys.executable, "-m", "crosshair", "check", f"--per_condition_timeout={per_cond_timeout}",
                                "--report_all", p], capture_output=True, text=True, timeout=total_timeout,
                               stdin=subprocess.DEVNULL, cwd=td)
        except subprocess.TimeoutExpired:
            return "UNKNOWN", "timeout"
    out = r.stdout + "\n" + r.stderr
    if "No module named crosshair" in out: raise RuntimeError("crosshair-tool is not installed")
    lines = [l for l in out.splitlines() if l.strip()]
    errs = [l for l in lines if ": error:" in l]
    if errs: return "FAIL", errs[0].split(": error:", 1)[1].strip()[:300]
    if any("Confirmed over all paths" in l for l in lines): return "PASS", ""
    return "UNKNOWN", (lines[-1][:200] if lines else "no-output")

def stub_verify(code, task, spec):
    """PLUMBING TEST ONLY (demo tasks): checks the contract on task['_demo']['probe_inputs'] in-process."""
    ns = {}
    exec("from typing import *\n" + code, ns); f = ns[task["entry_point"]]; names = params_of(task)
    for args in task["_demo"]["probe_inputs"]:
        env = dict(zip(names, args))
        try:
            if not all(_ev(p, env) for p in spec.get("pre", [])): continue
            env["__return__"] = f(*args)
            bad = [p for p in spec["post"] if not _ev(p, env)]
        except Exception as e:
            return "FAIL", f"{task['entry_point']}{tuple(args)} raised {type(e).__name__}"
        if bad: return "FAIL", f"{task['entry_point']}{tuple(args)} returned {env['__return__']!r}, violates: {bad[0]}"
    return "PASS", ""

if __name__ == "__main__":
    if "--selftest" in sys.argv:
        task = {"task_id": "t", "entry_point": "clamp", "public_tests": [],
                "prompt": "def clamp(x: int, lo: int, hi: int) -> int:\n    \"\"\"clamp x into [lo, hi]\"\"\"\n"}
        good = "def clamp(x: int, lo: int, hi: int) -> int:\n    return min(max(x, lo), hi)"
        bad = "def clamp(x: int, lo: int, hi: int) -> int:\n    return min(x, hi)"
        spec = {"pre": ["lo <= hi"], "post": ["lo <= __return__ <= hi"]}
        print("good ->", crosshair_verify(good, task, spec))   # expect PASS (or UNKNOWN)
        print("bad  ->", crosshair_verify(bad, task, spec))    # expect FAIL with a counterexample
