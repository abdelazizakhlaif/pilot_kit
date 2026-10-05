"""LLM backends (stdlib only). Spec strings: mock:NAME[:p_gen] | ollama:MODEL | openai:MODEL
openai: uses env OPENAI_BASE_URL (+ optional OPENAI_API_KEY) -> works with llama.cpp server, vLLM, etc."""
import json, os, random, re, urllib.request, zlib

def extract_code(text):
    m = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text, re.S)
    return (m[-1] if m else text).strip("\n")

def extract_json(text):
    m = re.findall(r"```(?:json)?\s*\n(.*?)```", text, re.S)
    for s in ([m[-1]] if m else []) + [text]:
        try: return json.loads(s)
        except Exception: pass
    return None

def _post(url, body, headers, timeout=900):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

class Ollama:
    def __init__(self, model, temperature=0.2, max_tokens=768):
        self.model, self.t, self.n = model, temperature, max_tokens
        self.host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self.name = "ollama:" + model
    def chat(self, prompt, seed):
        r = _post(self.host + "/api/chat", {"model": self.model, "stream": False,
                  "messages": [{"role": "user", "content": prompt}],
                  "options": {"temperature": self.t, "seed": seed, "num_predict": self.n}},
                  {"Content-Type": "application/json"})
        return r["message"]["content"]

class OpenAICompat:
    def __init__(self, model, temperature=0.2, max_tokens=768):
        self.model, self.t, self.n = model, temperature, max_tokens
        self.url = os.environ["OPENAI_BASE_URL"].rstrip("/") + "/chat/completions"
        self.key = os.environ.get("OPENAI_API_KEY", "")
        self.name = "openai:" + model
    def chat(self, prompt, seed):
        h = {"Content-Type": "application/json"}
        if self.key: h["Authorization"] = "Bearer " + self.key
        r = _post(self.url, {"model": self.model, "temperature": self.t, "seed": seed, "max_tokens": self.n,
                             "messages": [{"role": "user", "content": prompt}]}, h)
        return r["choices"][0]["message"]["content"]

class Mock:
    """PLUMBING TEST ONLY. Deterministic fake model driven by _demo fields of demo tasks."""
    RATES = {"test": 0.30, "verifier": 0.60}
    def __init__(self, name, tasks, p_gen=0.5):
        self.name, self.tasks, self.p_gen = "mock:" + name, tasks, p_gen
    def chat(self, prompt, seed):
        tid = re.search(r"### TASK_ID: (.*)", prompt).group(1).strip()
        mode = re.search(r"### MODE: (\w+)", prompt).group(1)
        d = self.tasks[tid]["_demo"]
        rnd = random.Random(zlib.crc32(f"{self.name}|{tid}|{mode}|{seed}".encode()))
        if mode == "spec":
            spec = d["spec"] if rnd.random() < 0.85 else {"post": ["??"]}
            return "```json\n" + json.dumps(spec) + "\n```"
        p = self.p_gen if mode == "gen" else self.RATES[re.search(r"### FEEDBACK_KIND: (\w+)", prompt).group(1)]
        return "```python\n" + (d["canonical_code"] if rnd.random() < p else d["buggy_code"]) + "\n```"

def make_llm(spec, tasks=None):
    kind, _, rest = spec.partition(":")
    if kind == "mock":
        name, _, p = rest.partition(":")
        return Mock(name, tasks, float(p) if p else 0.5)
    if kind == "ollama": return Ollama(rest)
    if kind == "openai": return OpenAICompat(rest)
    raise ValueError("unknown backend: " + spec)
