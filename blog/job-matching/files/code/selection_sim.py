"""
Two-stage selection simulation with standard errors.

Model
-----
N applicants, standardized quality Q (mean 0, variance 1).
Stage 1 score  S1 = r1*Q + sqrt(1-r1^2)*E1      (validity r1)
Stage 2 score  S2 = r2*Q + sqrt(1-r2^2)*E2      (validity r2)
(E1, E2) jointly Gaussian, standard normal, independent of Q, Corr(E1, E2) = rho.
Applicants are independent of one another; simulated markets are independent.
The firm shortlists the n1 highest S1, then hires the 2 highest on
  rule "S2":   the stage-2 score alone, or
  rule "both": the best linear predictor of Q from (S1, S2).
Outcomes are for a uniformly chosen one of the two hires:
  quality   E[Q]                       (SD above a random applicant)
  beats     P(Q_hire > Q of an independent random applicant)
  top10     P(Q_hire > population 90th percentile)

Engine A (exact, normal Q): draws the top-n1 order statistics of S1 directly,
then Q | S1.  Engine B (brute force): draws every applicant, any Q distribution.
Standard errors are across independent simulated markets.
"""
import json, sys, time
import numpy as np
from scipy import stats, integrate

Phi, phi, Pinv = stats.norm.cdf, stats.norm.pdf, stats.norm.ppf
Z90 = Pinv(0.9)


# ---------- exact benchmarks ----------
def A_top2(N):
    """Mean of the two largest of N standard normals, averaged."""
    f = lambda s: s * phi(s) * (Phi(s) ** (N - 1) + (N - 1) * (1 - Phi(s)) * Phi(s) ** (N - 2))
    return N / 2 * integrate.quad(f, -12, 12, limit=800)[0]


def blp_weights(r1, r2, rho):
    c12 = r1 * r2 + rho * np.sqrt((1 - r1**2) * (1 - r2**2))
    S = np.array([[1, c12], [c12, 1]])
    w = np.linalg.solve(S, np.array([r1, r2]))
    R = float(np.sqrt(w @ np.array([r1, r2])))
    return w, R, c12


# ---------- Engine A: exact order statistics, normal Q ----------
def top_order_stats(rng, N, k, T):
    """Top-k order statistics (descending) of N iid N(0,1), T independent rows."""
    V = rng.random((T, k))
    expo = 1.0 / (N - np.arange(k))
    U = np.cumprod(V ** expo, axis=1)
    return Pinv(U)


def engine_A(N, r1, n1, r2, rho, rule, T, rng, batch=100_000, g=None):
    """g: optional monotone map from latent normal quality to reported quality (copula spec)."""
    acc = []
    w = blp_weights(r1, r2, rho)[0] if (r2 is not None and n1 is not None) else None
    for start in range(0, T, batch):
        B = min(batch, T - start)
        if n1 is None:  # everyone gets stage 2; hire top 2 on S2 alone
            S2 = top_order_stats(rng, N, 2, B)
            Qh = r2 * S2 + np.sqrt(1 - r2**2) * rng.standard_normal((B, 2))
        else:
            S1 = top_order_stats(rng, N, n1, B)
            Q = r1 * S1 + np.sqrt(1 - r1**2) * rng.standard_normal((B, n1))
            if r2 is None:  # stage 1 only: hire top 2 on S1
                Qh = Q[:, :2]
            else:
                E1 = (S1 - r1 * Q) / np.sqrt(1 - r1**2)  # exact for every |r1| < 1, including r1 = 0
                E2 = rho * E1 + np.sqrt(1 - rho**2) * rng.standard_normal((B, n1))
                S2 = r2 * Q + np.sqrt(1 - r2**2) * E2
                score = S2 if rule == "S2" else w[0] * S1 + w[1] * S2
                idx = np.argpartition(-score, 1, axis=1)[:, :2]
                Qh = np.take_along_axis(Q, idx, 1)
        Qrep = Qh if g is None else g(Qh)
        acc.append(np.stack([Qrep.mean(1), Phi(Qh).mean(1), (Qh > Z90).mean(1)], 1))
    a = np.concatenate(acc)
    return a.mean(0), a.std(0, ddof=1) / np.sqrt(len(a))


def copula_map(dist):
    """Quality = F^{-1}(Phi(latent)), standardized; scores act on the latent normal scale."""
    if dist == "t5":
        return lambda z: stats.t.ppf(Phi(z), 5) / np.sqrt(5 / 3)
    if dist == "lognormal":
        s = 0.75
        m, v = np.exp(s**2 / 2), (np.exp(s**2) - 1) * np.exp(s**2)
        return lambda z: (np.exp(s * z) - m) / np.sqrt(v)
    if dist == "uniform":
        return lambda z: (Phi(z) - 0.5) * np.sqrt(12)


# ---------- Engine B: brute force, any quality distribution ----------
def draw_quality(rng, dist, shape):
    if dist == "normal":
        return rng.standard_normal(shape)
    if dist == "t5":  # heavy tails
        return rng.standard_t(5, shape) / np.sqrt(5 / 3)
    if dist == "lognormal":  # right-skewed
        s = 0.75
        x = rng.lognormal(0.0, s, shape)
        m, v = np.exp(s**2 / 2), (np.exp(s**2) - 1) * np.exp(s**2)
        return (x - m) / np.sqrt(v)
    if dist == "uniform":  # thin tails
        return (rng.random(shape) - 0.5) * np.sqrt(12)
    raise ValueError(dist)


def quantile90(dist):
    if dist == "normal":
        return Z90
    if dist == "t5":
        return stats.t.ppf(0.9, 5) / np.sqrt(5 / 3)
    if dist == "lognormal":
        s = 0.75
        m, v = np.exp(s**2 / 2), (np.exp(s**2) - 1) * np.exp(s**2)
        return (np.exp(s * Z90) - m) / np.sqrt(v)
    if dist == "uniform":
        return (0.9 - 0.5) * np.sqrt(12)


def cdf_q(dist, x):
    if dist == "normal":
        return Phi(x)
    if dist == "t5":
        return stats.t.cdf(x * np.sqrt(5 / 3), 5)
    if dist == "lognormal":
        s = 0.75
        m, v = np.exp(s**2 / 2), (np.exp(s**2) - 1) * np.exp(s**2)
        y = np.maximum(x * np.sqrt(v) + m, 1e-300)
        return Phi(np.log(y) / s)
    if dist == "uniform":
        return np.clip(x / np.sqrt(12) + 0.5, 0, 1)


def engine_B(designs, dist, rho, T, rng, Nmax=2200, batch=500):
    """designs: dict name -> (N, r1, n1, r2, rule). Common random numbers across designs."""
    out = {k: [] for k in designs}
    q90 = quantile90(dist)
    sizes = [batch] * (T // batch) + ([T % batch] if T % batch else [])
    for bsz in sizes:
        Q = draw_quality(rng, dist, (bsz, Nmax))
        E1 = rng.standard_normal((bsz, Nmax))
        E2 = rho * E1 + np.sqrt(1 - rho**2) * rng.standard_normal((bsz, Nmax))
        for name, (N, r1, n1, r2, rule) in designs.items():
            q, e1, e2 = Q[:, :N], E1[:, :N], E2[:, :N]
            if n1 is None:
                s2 = r2 * q + np.sqrt(1 - r2**2) * e2
                idx = np.argpartition(-s2, 1, axis=1)[:, :2]
                qh = np.take_along_axis(q, idx, 1)
            else:
                s1 = r1 * q + np.sqrt(1 - r1**2) * e1
                sl = np.argpartition(-s1, n1 - 1, axis=1)[:, :n1]
                qs = np.take_along_axis(q, sl, 1)
                if r2 is None:
                    s1s = np.take_along_axis(s1, sl, 1)
                    idx = np.argpartition(-s1s, 1, axis=1)[:, :2]
                else:
                    s2 = r2 * qs + np.sqrt(1 - r2**2) * np.take_along_axis(e2, sl, 1)
                    if rule == "both":
                        w, _, _ = blp_weights(r1, r2, rho)
                        s2 = w[0] * np.take_along_axis(s1, sl, 1) + w[1] * s2
                    idx = np.argpartition(-s2, 1, axis=1)[:, :2]
                qh = np.take_along_axis(qs, idx, 1)
            out[name].append(np.stack([qh.mean(1), cdf_q(dist, qh).mean(1), (qh > q90).mean(1)], 1))
    res = {}
    for k, v in out.items():
        a = np.concatenate(v)
        res[k] = (a.mean(0), a.std(0, ddof=1) / np.sqrt(len(a)))
    return res


DESIGNS = {  # name: (N, r1, n1, r2)
    "prose_only": (2200, 0.19, 2, None),
    "prose_10": (2200, 0.19, 10, 0.47),
    "prose_35": (2200, 0.19, 35, 0.47),
    "prose_75": (2200, 0.19, 75, 0.47),
    "all_stage2": (2200, 0.19, None, 0.47),
    "cap300_35": (300, 0.19, 35, 0.47),
    "exercise_20": (2200, 0.33, 20, 0.47),
}

if __name__ == "__main__":
    T_A = int(sys.argv[1]) if len(sys.argv) > 1 else 2_000_000
    T_B = int(sys.argv[2]) if len(sys.argv) > 2 else 40_000
    rng = np.random.default_rng(20261116)
    R = {"T_A": T_A, "T_B": T_B, "exact": {}, "main": {}, "rho": {}, "rule": {}, "r1": {}, "dist": {}}
    t0 = time.time()

    # exact benchmarks
    A = {n: A_top2(n) for n in (10, 20, 35, 75, 300, 2200)}
    R["exact"] = {
        "A_N": A,
        "prose_only": 0.19 * A[2200],
        "all_stage2": 0.47 * A[2200],
        "worthless_10": 0.47 * A[10], "worthless_35": 0.47 * A[35], "worthless_75": 0.47 * A[75],
        "all_both_R": blp_weights(0.19, 0.47, 0.0)[1],
        "all_both": blp_weights(0.19, 0.47, 0.0)[1] * A[2200],
    }

    # main table, rho = 0, rule S2, with the worthless-screen column
    for name, (N, r1, n1, r2) in DESIGNS.items():
        m, se = engine_A(N, r1, n1, r2, 0.0, "S2", T_A, rng)
        entry = {"mean": m.tolist(), "se": se.tolist()}
        if n1 is not None and r2 is not None and name != "exercise_20":
            m0, se0 = engine_A(N, 0.0, n1, r2, 0.0, "S2", T_A, rng)
            entry["worthless"] = [float(m0[0]), float(se0[0])]
        R["main"][name] = entry
        print(name, np.round(m, 4), np.round(se, 5), entry.get("worthless"), f"{time.time()-t0:.0f}s", flush=True)

    # sensitivity: residual correlation between stages, and decision rule
    for rho in (0.0, 0.25, 0.5):
        for name in ("prose_10", "prose_35", "prose_75", "cap300_35", "exercise_20"):
            N, r1, n1, r2 = DESIGNS[name]
            for rule in ("S2", "both"):
                m, se = engine_A(N, r1, n1, r2, rho, rule, T_A // 2, rng)
                R["rho"][f"{name}|{rho}|{rule}"] = [float(m[0]), float(se[0])]
        print("rho", rho, f"{time.time()-t0:.0f}s", flush=True)

    # sensitivity: stage-1 validity
    for r1 in (0.0, 0.10, 0.19, 0.30):
        for n1 in (10, 35, 75):
            m, se = engine_A(2200, r1, n1, 0.47, 0.0, "S2", T_A // 2, rng)
            R["r1"][f"{r1}|{n1}"] = [float(m[0]), float(se[0])]
    print("r1 done", f"{time.time()-t0:.0f}s", flush=True)

    # non-normal quality (brute force, common random numbers), plus normal as a cross-check of engine A
    dB = {k: (v[0], v[1], v[2], v[3], "S2") for k, v in DESIGNS.items()}
    for dist in ("normal", "t5", "lognormal", "uniform"):
        res = engine_B(dB, dist, 0.0, T_B, rng)
        R["dist"][dist] = {k: {"mean": m.tolist(), "se": se.tolist()} for k, (m, se) in res.items()}
        print(dist, {k: round(float(v[0][0]), 3) for k, v in res.items()}, f"{time.time()-t0:.0f}s", flush=True)

    # non-normal quality, copula specification (scores see the latent normal rank), exact engine
    R["copula"] = {}
    for dist in ("t5", "lognormal", "uniform"):
        g = copula_map(dist)
        R["copula"][dist] = {}
        for name, (N, r1, n1, r2) in DESIGNS.items():
            m, se = engine_A(N, r1, n1, r2, 0.0, "S2", T_A // 4, rng, g=g)
            R["copula"][dist][name] = [float(m[0]), float(se[0])]
        print("copula", dist, {k: round(v[0], 3) for k, v in R["copula"][dist].items()}, f"{time.time()-t0:.0f}s", flush=True)

    json.dump(R, open("selection_results.json", "w"), indent=1)
    print("saved", f"{time.time()-t0:.0f}s")
