import numpy as np, itertools, json
rng = np.random.default_rng(20261005)
PERMS, SIMS, G = 2000, 1000, 3

def holm_reject(p, alpha=0.05):
    # p: (sims, 4). returns boolean reject matrix under Holm
    order = np.argsort(p, axis=1)
    ps = np.take_along_axis(p, order, 1)
    m = p.shape[1]
    thr = alpha / (m - np.arange(m))
    ok = np.cumprod(ps <= thr, axis=1).astype(bool)   # step-down: stop at first failure
    rej = np.zeros_like(ok)
    np.put_along_axis(rej, order, ok, 1)
    return rej

def sim_model(N, p0, cov, a_v, a_t, reg_v, reg_t, k=1.0):
    q = rng.beta(p0*k, (1-p0)*k, size=(SIMS, N))              # task difficulty (U-shaped)
    init = rng.random((SIMS, N, G)) < q[..., None]            # shared initial candidates
    covered = rng.random((SIMS, N, 1)) < cov                  # valid spec + verifier coverage
    u1 = rng.random((SIMS, N, G)); u2 = rng.random((SIMS, N, G))
    ctrl = init
    test = np.where(init, u1 >= reg_t, u1 < a_t)
    ver  = np.where(covered, np.where(init, u2 >= reg_v, u2 < a_v), init)
    f = lambda y: y.mean(axis=2)
    return f(ctrl), f(test), f(ver)

def pvals(D, S):
    obs = D.mean(1)                       # (sims,)
    null = D @ S / D.shape[1]             # (sims, perms)
    return (1 + (null >= obs[:, None] - 1e-12).sum(1)) / (PERMS + 1)

def run(N, p0, cov, a_v=0.35, a_t=0.20, reg_v=0.02, reg_t=0.02):
    S = rng.choice([-1.0, 1.0], size=(N, PERMS))
    P, eff = [], []
    for _ in range(2):  # models A, B
        c, t, v = sim_model(N, p0, cov, a_v, a_t, reg_v, reg_t)
        P += [pvals(v - c, S), pvals(v - t, S)]
        eff += [(v - c).mean(), (v - t).mean()]
    P = np.stack(P, 1)                    # order: C1(A,ctrl) C3(A,test) C2(B,ctrl) C4(B,test)
    rej = holm_reject(P)
    return dict(power_ctrl=rej[:, [0, 2]].mean(), power_test=rej[:, [1, 3]].mean(),
                eff_ctrl=np.mean(eff[0::2]), eff_test=np.mean(eff[1::2]))

if __name__ == "__main__":
    rows = []
    for p0, cov, N in itertools.product([0.5, 0.7, 0.85, 0.92], [0.5, 0.8], [100, 200, 300, 542]):
        r = run(N, p0, cov); r.update(p0=p0, cov=cov, N=N); rows.append(r)
        print(f"p0={p0:.2f} cov={cov:.1f} N={N:3d} | effVsCtrl={r['eff_ctrl']:.3f} effVsTest={r['eff_test']:.3f} | power C1/C2={r['power_ctrl']:.2f}  C3/C4={r['power_test']:.2f}")
    json.dump(rows, open('/home/claude/power_results.json', 'w'))
