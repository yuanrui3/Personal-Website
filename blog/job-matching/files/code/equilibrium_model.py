"""
A one-shot hiring market with endogenous application counts, noisy costly
screening, two worker types and free entry of vacancies.

Primitives
----------
Workers: mass 1. Type H (share pi) produces y_H in a job, type L produces y_L.
         Every job pays the posted wage w, so a worker's gain from a job is w.
         A type-t worker sends a Poisson number of applications with mean a_t,
         each at cost c_a, to vacancies chosen uniformly at random.
Firms:   mass v of single vacancies, entry cost k each (free entry).
         A vacancy cannot tell applications apart without screening. Screening
         one application costs c_s and returns a binary signal that is correct
         with probability s. The firm screens its pile in random order, makes
         its one offer to the first applicant with a good signal, and stops.
Workers holding several offers accept one at random; the other offers lapse.

Mean-field (large-market) formulas
----------------------------------
Lam_t = share_t * a_t / v,  Lam = Lam_H + Lam_L,  mu = Lam_H / Lam
g_H = s, g_L = 1 - s,       g = mu*g_H + (1-mu)*g_L       (prob. good signal)
F   = 1 - exp(-Lam*g)                                     (vacancy makes an offer)
p_t = g_t * F / (Lam*g)                                   (offer prob. per application)
m_t = 1 - exp(-a_t*p_t)                                   (type-t employment prob.)
alpha_t = m_t / (a_t*p_t)                                 (offer acceptance prob.)
V   = [mu*s*alpha_H*(y_H-w) + (1-mu)*(1-s)*alpha_L*(y_L-w)] / g
Pi  = F*(V - c_s/g) - k                                   (vacancy profit)
Worker best response: a_t = ln(w*p_t/c)/p_t if w*p_t > c else 0, c = c_a + fee,
                      truncated at the cap if there is one.
Free entry: Pi = 0 (largest root in v), or v = 0 if entry never pays.
Total surplus: TS = sum_t share_t*m_t*y_t - c_a*apps - v*(F*c_s/g + k).
"""
import json, sys
import numpy as np
from scipy import optimize


class Params:
    def __init__(self, yH=1.0, yL=0.3, w=0.5, pi=0.3, s=0.8, c_s=0.01, k=0.05, c_a=0.005):
        self.yH, self.yL, self.w, self.pi, self.s, self.c_s, self.k, self.c_a = yH, yL, w, pi, s, c_s, k, c_a

    def copy(self, **kw):
        d = dict(yH=self.yH, yL=self.yL, w=self.w, pi=self.pi, s=self.s, c_s=self.c_s, k=self.k, c_a=self.c_a)
        d.update(kw)
        return Params(**d)


def _ratio(x):
    """(1 - exp(-x)) / x, stable at 0."""
    x = np.asarray(x, float)
    return np.where(x < 1e-10, 1.0 - x / 2, -np.expm1(-x) / np.maximum(x, 1e-300))


def outcomes(P, aH, aL, v):
    """All mean-field quantities for given application intensities and vacancy mass."""
    LH, LL = P.pi * aH / v, (1 - P.pi) * aL / v
    Lam = LH + LL
    if Lam <= 0:
        return dict(Lam=0, mu=0, g=0, F=0, pH=0, pL=0, mH=0, mL=0, alH=1, alL=1, V=0, Pi=-P.k,
                    TS=-P.k * v, screens=0, UH=0, UL=0, hires=0, shareH=np.nan, apps=0)
    mu = LH / Lam
    g = mu * P.s + (1 - mu) * (1 - P.s)
    F = -np.expm1(-Lam * g)
    base = float(_ratio(Lam * g))  # F / (Lam*g)
    pH, pL = P.s * base, (1 - P.s) * base
    mH, mL = -np.expm1(-aH * pH), -np.expm1(-aL * pL)
    alH, alL = float(_ratio(aH * pH)), float(_ratio(aL * pL))
    V = (mu * P.s * alH * (P.yH - P.w) + (1 - mu) * (1 - P.s) * alL * (P.yL - P.w)) / g
    Pi = F * (V - P.c_s / g) - P.k
    apps = P.pi * aH + (1 - P.pi) * aL
    hires = P.pi * mH + (1 - P.pi) * mL
    TS = P.pi * mH * P.yH + (1 - P.pi) * mL * P.yL - P.c_a * apps - v * (F * P.c_s / g + P.k)
    # deviations a vacancy could consider
    V_bad = (mu * (1 - P.s) * alH * (P.yH - P.w) + (1 - mu) * P.s * alL * (P.yL - P.w)) / max(1 - g, 1e-300)
    V_blind = mu * alH * (P.yH - P.w) + (1 - mu) * alL * (P.yL - P.w)
    Pi_blind = -np.expm1(-Lam) * V_blind - P.k
    return dict(Lam=Lam, mu=mu, g=g, F=F, pH=pH, pL=pL, mH=mH, mL=mL, alH=alH, alL=alL, V=V, Pi=Pi, TS=TS,
                screens=F / g, UH=P.w * mH - P.c_a * aH, UL=P.w * mL - P.c_a * aL, hires=hires,
                shareH=P.pi * mH / hires if hires > 0 else np.nan, apps=apps,
                V_bad=V_bad, Pi_blind=Pi_blind, screen_cost=v * F * P.c_s / g, entry_cost=v * P.k)


def _profit_vec(P, aH, aL, v):
    """Vacancy profit for an array of v (vectorized version of outcomes()['Pi'])."""
    LH, LL = P.pi * aH / v, (1 - P.pi) * aL / v
    Lam = LH + LL
    mu = LH / Lam
    g = mu * P.s + (1 - mu) * (1 - P.s)
    F = -np.expm1(-Lam * g)
    base = _ratio(Lam * g)
    alH, alL = _ratio(aH * P.s * base), _ratio(aL * (1 - P.s) * base)
    V = (mu * P.s * alH * (P.yH - P.w) + (1 - mu) * (1 - P.s) * alL * (P.yL - P.w)) / g
    return F * (V - P.c_s / g) - P.k


_VGRID = np.exp(np.linspace(np.log(1e-7), np.log(1e3), 600))


def free_entry_v(P, aH, aL):
    """Largest v with zero profit (profit positive just below it); 0 if entry never pays."""
    if P.pi * aH + (1 - P.pi) * aL <= 0:
        return 0.0
    prof = _profit_vec(P, aH, aL, _VGRID)
    idx = np.where((prof[:-1] > 0) & (prof[1:] <= 0))[0]
    if len(idx) == 0:
        return 0.0
    i = idx[-1]
    f = lambda v: float(_profit_vec(P, aH, aL, np.array([v]))[0])
    return optimize.brentq(f, _VGRID[i], _VGRID[i + 1], xtol=1e-14, rtol=1e-12)


def best_response(P, p, fee=0.0, cap=np.inf):
    c = P.c_a + fee
    a = np.log(P.w * p / c) / p if P.w * p > c else 0.0
    return min(a, cap)


def solve_equilibrium(P, fee=0.0, cap=np.inf, starts=((5, 5), (30, 30), (200, 200), (2, 20), (20, 2)),
                      damp=0.15, tol=1e-10, maxit=1500):
    """Damped best-response iteration from several starts; returns distinct trading equilibria."""
    found = []
    for a0 in starts:
        a = np.array([min(a0[0], cap), min(a0[1], cap)], float)
        ok = False
        for _ in range(maxit):
            v = free_entry_v(P, a[0], a[1])
            if v <= 0:
                break
            o = outcomes(P, a[0], a[1], v)
            br = np.array([best_response(P, o["pH"], fee, cap), best_response(P, o["pL"], fee, cap)])
            new = (1 - damp) * a + damp * br
            if np.max(np.abs(new - a)) < tol * (1 + np.max(a)):
                a, ok = new, True
                break
            a = new
        if ok and v > 0:
            o = outcomes(P, a[0], a[1], v)
            br = np.array([best_response(P, o["pH"], fee, cap), best_response(P, o["pL"], fee, cap)])
            res = float(np.max(np.abs(br - a)))
            if not any(np.allclose([a[0], a[1], v], [f["aH"], f["aL"], f["v"]], rtol=1e-5, atol=1e-7) for f in found):
                found.append(dict(aH=float(a[0]), aL=float(a[1]), v=float(v), resid_a=res, resid_Pi=float(o["Pi"]), **o))
    found.sort(key=lambda d: -d["TS"])
    return found


def _cap_eq(P, c):
    """Best trading equilibrium under a common cap c (None if the market shuts)."""
    eq = solve_equilibrium(P, cap=c, starts=((c, c), (min(5, c), min(5, c)), (min(2, c), min(2, c))))
    return eq[0] if eq else None


def best_cap(P):
    """Welfare-maximizing common cap on applications, with free entry and best responses."""
    lf = solve_equilibrium(P)
    if not lf:
        return None, None
    hi = max(lf[0]["aH"], lf[0]["aL"])
    grid = np.unique(np.concatenate([np.linspace(0.5, min(hi, 20), 79), np.geomspace(1, hi, 60)]))
    best_c, best_e = hi, lf[0]
    for c in grid:
        e = _cap_eq(P, c)
        if e is not None and e["TS"] > best_e["TS"]:
            best_c, best_e = c, e
    def f(c):
        e = _cap_eq(P, c)
        return -e["TS"] if e is not None else 1e9
    r = optimize.minimize_scalar(f, bounds=(max(0.25, best_c * 0.9), min(hi, best_c * 1.1)), method="bounded",
                                 options=dict(xatol=1e-4))
    e = _cap_eq(P, r.x)
    if e is not None and e["TS"] > best_e["TS"]:
        best_c, best_e = r.x, e
    return float(best_c), best_e


def best_fee(P):
    """Welfare-maximizing application fee, rebated lump-sum (so it is a pure transfer)."""
    f = lambda fee: -(solve_equilibrium(P, fee=fee) or [dict(TS=-1e9)])[0]["TS"]
    grid = np.geomspace(P.c_a * 0.05, P.w * 0.2, 24)
    vals = [f(x) for x in grid]
    i = int(np.argmin(vals))
    lo, up = grid[max(i - 1, 0)], grid[min(i + 1, len(grid) - 1)]
    r = optimize.minimize_scalar(f, bounds=(lo, up), method="bounded", options=dict(xatol=1e-7))
    fee = r.x if r.fun <= vals[i] else grid[i]
    return fee, solve_equilibrium(P, fee=fee)[0]


def planner(P):
    """Surplus-maximizing (a_H, a_L, v) taking the screening technology as given."""
    def neg(x):
        aH, aL, v = np.exp(x)
        return -outcomes(P, aH, aL, v)["TS"]
    best = None
    for x0 in [(1, 1, 0.3), (3, 0.5, 0.5), (5, 5, 1.0), (2, 0.05, 0.3), (8, 0.01, 0.5), (1.5, 0.001, 0.2)]:
        r = optimize.minimize(neg, np.log(x0), method="Nelder-Mead",
                              options=dict(xatol=1e-9, fatol=1e-13, maxiter=20000, maxfev=20000))
        if best is None or r.fun < best.fun:
            best = r
    aH, aL, v = np.exp(best.x)
    return dict(aH=float(aH), aL=float(aL), v=float(v), **outcomes(P, aH, aL, v))


# ---------- agent-based check of the mean-field formulas ----------
def agent_sim(P, aH, aL, v, n_workers=200_000, seed=1):
    rng = np.random.default_rng(seed)
    nH = int(round(P.pi * n_workers)); nL = n_workers - nH
    nF = max(int(round(v * n_workers)), 1)
    typ = np.r_[np.ones(nH, bool), np.zeros(nL, bool)]
    k = np.r_[rng.poisson(aH, nH), rng.poisson(aL, nL)]
    worker = np.repeat(np.arange(n_workers), k)
    firm = rng.integers(0, nF, worker.size)
    good = rng.random(worker.size) < np.where(typ[worker], P.s, 1 - P.s)
    key = rng.random(worker.size)
    order = np.lexsort((key, firm))
    firm_s, good_s, worker_s = firm[order], good[order], worker[order]
    start = np.r_[0, np.flatnonzero(np.diff(firm_s)) + 1]
    pos = np.arange(firm_s.size) - np.repeat(start, np.diff(np.r_[start, firm_s.size]))
    gi = np.flatnonzero(good_s)                       # good applications in screening order
    first = gi[np.r_[True, np.diff(firm_s[gi]) != 0]] if gi.size else gi   # first good per firm
    offer_w = worker_s[first]
    screens_with_good = pos[first] + 1
    n_per_firm = np.bincount(firm_s, minlength=nF)
    has_good = np.zeros(nF, bool); has_good[firm_s[first]] = True
    total_screens = screens_with_good.sum() + n_per_firm[~has_good].sum()
    # each worker with offers accepts one at random
    perm = rng.permutation(offer_w.size)
    _, first_idx = np.unique(offer_w[perm], return_index=True)
    accepted_w = offer_w[perm][first_idx]
    hiredH = typ[accepted_w].sum(); hiredL = accepted_w.size - hiredH
    profit = (hiredH * (P.yH - P.w) + hiredL * (P.yL - P.w) - P.c_s * total_screens) / nF - P.k
    return dict(mH=hiredH / nH, mL=hiredL / nL, screens=total_screens / nF, Pi=profit,
                offers_per_firm=offer_w.size / nF, apps_per_firm=worker.size / nF)


def row(tag, e):
    keys = ("aH", "aL", "v", "Lam", "mu", "mH", "mL", "hires", "shareH", "TS", "UH", "UL", "screen_cost",
            "entry_cost", "apps", "Pi", "V_bad", "Pi_blind", "pH", "pL")
    return dict(tag=tag, **{k: float(e[k]) for k in keys if k in e})


# ======================================================================
# Revision (after external review): scalar equilibrium search, corrected
# type-level utilities under a rebated fee, and a hard application cap.
# ======================================================================

def best_responses_z(P, z, fee=0.0, cap=np.inf):
    """Workers' best responses when good-signal applications per vacancy equal z."""
    hz = float(_ratio(z))
    pH, pL = P.s * hz, (1 - P.s) * hz
    return best_response(P, pH, fee, cap), best_response(P, pL, fee, cap)


def _state_z(P, z, fee, cap):
    aH, aL = best_responses_z(P, z, fee, cap)
    B = P.pi * aH * P.s + (1 - P.pi) * aL * (1 - P.s)
    if B <= 0:
        return None
    v = B / z  # makes the congestion identity Lam*g = z hold exactly
    return aH, aL, v


def all_equilibria(P, fee=0.0, cap=np.inf, zmin=1e-5, zmax=1e5, n=6000):
    """Every trading equilibrium found by scanning z = Lam*g and solving Pi(z) = 0.
    Workers best-respond exactly at each z, so only the scalar profit condition remains."""
    zs = np.geomspace(zmin, zmax, n)
    vals = []
    for z in zs:
        st = _state_z(P, z, fee, cap)
        vals.append(np.nan if st is None else outcomes(P, st[0], st[1], st[2])["Pi"])
    vals = np.array(vals)
    eqs = []
    for i in range(n - 1):
        a, b = vals[i], vals[i + 1]
        if np.isfinite(a) and np.isfinite(b) and a * b < 0:
            f = lambda z: outcomes(P, *_state_z(P, z, fee, cap))["Pi"]
            z0 = optimize.brentq(f, zs[i], zs[i + 1], xtol=1e-15, rtol=1e-13)
            aH, aL, v = _state_z(P, z0, fee, cap)
            o = outcomes(P, aH, aL, v)
            A = P.pi * aH + (1 - P.pi) * aL
            # type-level utility with the fee rebated equally to every worker
            UH = P.w * o["mH"] - (P.c_a + fee) * aH + fee * A
            UL = P.w * o["mL"] - (P.c_a + fee) * aL + fee * A
            # local profit slope in v at fixed applications (entry stability)
            dv = 1e-6 * v
            slope = (outcomes(P, aH, aL, v + dv)["Pi"] - outcomes(P, aH, aL, v - dv)["Pi"]) / (2 * dv)
            d = dict(o)
            d.update(aH=float(aH), aL=float(aL), v=float(v), z=float(z0), UH=float(UH), UL=float(UL),
                     fee=float(fee), cap=float(cap), dPi_dv=float(slope), resid_Pi=float(o["Pi"]))
            eqs.append(d)
    eqs.sort(key=lambda d: -d["TS"])
    return eqs


def best_eq(P, fee=0.0, cap=np.inf):
    e = all_equilibria(P, fee, cap)
    return e[0] if e else None


def best_cap_z(P):
    """Welfare-maximizing common cap on the Poisson application intensity."""
    lf = best_eq(P)
    hi = max(lf["aH"], lf["aL"]) if lf else 500.0
    grid = np.unique(np.concatenate([np.linspace(0.25, min(hi, 25), 99), np.geomspace(1, max(hi, 2), 50)]))
    best_c, best_e = np.inf, lf
    for c in grid:
        e = best_eq(P, cap=c)
        if e is not None and (best_e is None or e["TS"] > best_e["TS"] + 1e-12):
            best_c, best_e = c, e
    if np.isfinite(best_c):
        f = lambda c: -(best_eq(P, cap=c) or dict(TS=-1e9))["TS"]
        r = optimize.minimize_scalar(f, bounds=(max(0.1, best_c * 0.9), best_c * 1.1), method="bounded",
                                     options=dict(xatol=1e-5))
        e = best_eq(P, cap=r.x)
        if e is not None and e["TS"] > best_e["TS"]:
            best_c, best_e = r.x, e
    return float(best_c), best_e


def best_fee_z(P):
    """Welfare-maximizing per-application fee (rebated lump-sum, equally to all workers); includes fee = 0."""
    grid = np.r_[0.0, np.geomspace(P.c_a * 0.02, P.w * 0.5, 60)]
    res = [(fee, best_eq(P, fee=fee)) for fee in grid]
    res = [(f, e) for f, e in res if e is not None]
    i = int(np.argmax([e["TS"] for _, e in res]))
    fee0 = res[i][0]
    lo = res[max(i - 1, 0)][0]; up = res[min(i + 1, len(res) - 1)][0]
    f = lambda x: -(best_eq(P, fee=x) or dict(TS=-1e9))["TS"]
    if up > lo:
        r = optimize.minimize_scalar(f, bounds=(lo, up), method="bounded", options=dict(xatol=1e-8))
        e = best_eq(P, fee=r.x)
        if e is not None and e["TS"] > res[i][1]["TS"]:
            return float(r.x), e
    return float(fee0), res[i][1]


def hard_cap_eq(P, n):
    """Hard cap of n applications (integer), binding for both types: every worker sends exactly n.
    Each application yields an offer independently with prob p_t, so m_t = 1-(1-p_t)^n and
    alpha_t = m_t/(n p_t). Returns the best trading equilibrium, or None. Also reports whether
    sending all n is each type's best reply (marginal value w p (1-p)^(n-1) >= c_a)."""
    def outcomes_hard(v):
        o = outcomes(P, n, n, v)  # arrivals at vacancies are unchanged (still Poisson in the large market)
        pH, pL = o["pH"], o["pL"]
        mH, mL = 1 - (1 - pH) ** n, 1 - (1 - pL) ** n
        alH = mH / (n * pH) if pH > 0 else 1.0
        alL = mL / (n * pL) if pL > 0 else 1.0
        mu, g, F = o["mu"], o["g"], o["F"]
        V = (mu * P.s * alH * (P.yH - P.w) + (1 - mu) * (1 - P.s) * alL * (P.yL - P.w)) / g
        Pi = F * (V - P.c_s / g) - P.k
        hires = P.pi * mH + (1 - P.pi) * mL
        TS = P.pi * mH * P.yH + (1 - P.pi) * mL * P.yL - P.c_a * n - v * (F * P.c_s / g + P.k)
        return dict(Pi=Pi, mH=mH, mL=mL, hires=hires, TS=TS, shareH=P.pi * mH / hires if hires > 0 else np.nan,
                    UH=P.w * mH - P.c_a * n, UL=P.w * mL - P.c_a * n, pH=pH, pL=pL, v=v)
    vs = np.geomspace(1e-5, 1e3, 3000)
    pr = np.array([outcomes_hard(v)["Pi"] for v in vs])
    out = []
    for i in range(len(vs) - 1):
        if pr[i] * pr[i + 1] < 0:
            v0 = optimize.brentq(lambda v: outcomes_hard(v)["Pi"], vs[i], vs[i + 1], xtol=1e-15)
            d = outcomes_hard(v0)
            d["br_ok"] = bool(P.w * d["pH"] * (1 - d["pH"]) ** (n - 1) >= P.c_a and
                              P.w * d["pL"] * (1 - d["pL"]) ** (n - 1) >= P.c_a)
            out.append(d)
    out.sort(key=lambda d: -d["TS"])
    return out[0] if out else None


# ---------- fixed-count application technology ----------
def outcomes_fixed(P, aH, aL, v):
    """Every type-t worker sends exactly a_t applications (continuous relaxation of an integer count).
    Arrivals at a vacancy stay Poisson in the large market, so F, g, p_t are unchanged; offers per worker
    are Binomial(a_t, p_t), giving m_t = 1-(1-p_t)^a_t and alpha_t = m_t/(a_t p_t)."""
    o = outcomes(P, aH, aL, v)
    if o["Lam"] <= 0:
        return o
    pH, pL = o["pH"], o["pL"]
    mH = 1 - (1 - pH) ** aH if aH > 0 else 0.0
    mL = 1 - (1 - pL) ** aL if aL > 0 else 0.0
    alH = mH / (aH * pH) if aH * pH > 0 else 1.0
    alL = mL / (aL * pL) if aL * pL > 0 else 1.0
    mu, g, F = o["mu"], o["g"], o["F"]
    V = (mu * P.s * alH * (P.yH - P.w) + (1 - mu) * (1 - P.s) * alL * (P.yL - P.w)) / g
    Pi = F * (V - P.c_s / g) - P.k
    apps = P.pi * aH + (1 - P.pi) * aL
    hires = P.pi * mH + (1 - P.pi) * mL
    TS = P.pi * mH * P.yH + (1 - P.pi) * mL * P.yL - P.c_a * apps - v * (F * P.c_s / g + P.k)
    o.update(mH=mH, mL=mL, alH=alH, alL=alL, V=V, Pi=Pi, hires=hires, TS=TS, apps=apps,
             shareH=P.pi * mH / hires if hires > 0 else np.nan, UH=P.w * mH - P.c_a * aH, UL=P.w * mL - P.c_a * aL)
    return o


def best_response_fixed(P, p, fee=0.0, cap=np.inf):
    c = P.c_a + fee
    if p <= 0:
        return 0.0
    h = -np.log1p(-p)
    a = np.log(P.w * h / c) / h if P.w * h > c else 0.0
    return min(a, cap)


def all_equilibria_fixed(P, fee=0.0, cap=np.inf, zmin=1e-5, zmax=1e5, n=4000):
    def state(z):
        hz = float(_ratio(z))
        aH = best_response_fixed(P, P.s * hz, fee, cap)
        aL = best_response_fixed(P, (1 - P.s) * hz, fee, cap)
        B = P.pi * aH * P.s + (1 - P.pi) * aL * (1 - P.s)
        return None if B <= 0 else (aH, aL, B / z)
    zs = np.geomspace(zmin, zmax, n)
    vals = np.array([np.nan if state(z) is None else outcomes_fixed(P, *state(z))["Pi"] for z in zs])
    eqs = []
    for i in range(n - 1):
        a, b = vals[i], vals[i + 1]
        if np.isfinite(a) and np.isfinite(b) and a * b < 0:
            z0 = optimize.brentq(lambda z: outcomes_fixed(P, *state(z))["Pi"], zs[i], zs[i + 1], xtol=1e-15)
            aH, aL, v = state(z0)
            o = outcomes_fixed(P, aH, aL, v)
            A = P.pi * aH + (1 - P.pi) * aL
            d = dict(o)
            d.update(aH=aH, aL=aL, v=v, z=z0, UH=P.w * o["mH"] - (P.c_a + fee) * aH + fee * A,
                     UL=P.w * o["mL"] - (P.c_a + fee) * aL + fee * A)
            eqs.append(d)
    eqs.sort(key=lambda d: -d["TS"])
    return eqs


def best_hard_cap(P):
    """Best binding integer cap under the fixed-count technology (every worker sends exactly n)."""
    lf = all_equilibria_fixed(P)
    hi = int(np.ceil(max(lf[0]["aH"], lf[0]["aL"]))) if lf else 300
    best = (None, None)
    for n in range(1, min(hi, 200) + 1):
        e = hard_cap_eq(P, n)
        if e is not None and e["br_ok"] and (best[1] is None or e["TS"] > best[1]["TS"]):
            best = (n, e)
    return best


def best_fee_fixed(P):
    grid = np.r_[0.0, np.geomspace(P.c_a * 0.02, P.w * 0.5, 50)]
    res = [(f, all_equilibria_fixed(P, fee=f)) for f in grid]
    res = [(f, e[0]) for f, e in res if e]
    i = int(np.argmax([e["TS"] for _, e in res]))
    lo, up = res[max(i - 1, 0)][0], res[min(i + 1, len(res) - 1)][0]
    if up > lo:
        r = optimize.minimize_scalar(lambda x: -((all_equilibria_fixed(P, fee=x) or [dict(TS=-1e9)])[0]["TS"]),
                                     bounds=(lo, up), method="bounded", options=dict(xatol=1e-8))
        e = all_equilibria_fixed(P, fee=r.x)
        if e and e[0]["TS"] > res[i][1]["TS"]:
            return float(r.x), e[0]
    return float(res[i][0]), res[i][1]
