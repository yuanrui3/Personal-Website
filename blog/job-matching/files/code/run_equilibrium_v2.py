"""Revised equilibrium runs: every case solved with the scalar z-scan (all equilibria), Poisson-intensity
caps and hard integer caps, rebated fees with type-level utilities under an equal lump-sum rebate,
planner benchmark, cap curves, and agent-based validation."""
import json, time
import numpy as np
import equilibrium_model as M

t0 = time.time()
B = M.Params()
CASES = [  # (group, label, params)
    ("cost", "c_a = 0.05", B.copy(c_a=0.05)),
    ("cost", "c_a = 0.02 (pre-AI baseline)", B.copy(c_a=0.02)),
    ("cost", "c_a = 0.005", B.copy(c_a=0.005)),
    ("cost", "c_a = 0.001 (baseline)", B.copy(c_a=0.001)),
    ("cost", "c_a = 0.0002", B.copy(c_a=0.0002)),
    ("shock", "noisier signal (s = 0.65)", B.copy(c_a=0.02, s=0.65)),
    ("shock", "cheaper screening (c_s = 0.002)", B.copy(c_a=0.02, c_s=0.002)),
    ("shock", "all three AI shocks", B.copy(c_a=0.001, s=0.65, c_s=0.002)),
    ("robust", "fewer able workers (pi = 0.15)", B.copy(c_a=0.001, pi=0.15)),
    ("robust", "more able workers (pi = 0.5)", B.copy(c_a=0.001, pi=0.5)),
    ("robust", "unqualified hires lose value (y_L = -0.2)", B.copy(c_a=0.001, yL=-0.2)),
    ("robust", "higher wage (w = 0.7)", B.copy(c_a=0.001, w=0.7)),
    ("robust", "lower wage (w = 0.35)", B.copy(c_a=0.001, w=0.35)),
    ("robust", "costlier entry (k = 0.15)", B.copy(c_a=0.001, k=0.15)),
    ("robust", "sharper signal (s = 0.95)", B.copy(c_a=0.001, s=0.95)),
    ("robust", "costlier screening (c_s = 0.03)", B.copy(c_a=0.001, c_s=0.03)),
]
KEYS = ("aH", "aL", "v", "z", "Lam", "mu", "F", "g", "mH", "mL", "hires", "shareH", "TS", "UH", "UL", "apps",
        "screen_cost", "entry_cost", "Pi", "pH", "pL", "dPi_dv")
pick = lambda e: {k: float(e[k]) for k in KEYS if k in e and e[k] is not None}

out = dict(cases=[], cap_curve=[], hard_cap_curve=[], validation=[])
for grp, lab, P in CASES:
    lf_all = M.all_equilibria(P)
    lf = lf_all[0]
    cap, ce = M.best_cap_z(P)
    fee, fe = M.best_fee_z(P)
    pl = M.planner(P)
    lfx = M.all_equilibria_fixed(P)
    hc, he = M.best_hard_cap(P)
    feex, fex = M.best_fee_fixed(P)
    rec = dict(group=grp, label=lab, n_eq=len(lf_all), lf=pick(lf), app_spend=float(P.c_a * lf["apps"]),
               cap=cap, cap_eq=pick(ce), cap_helps=bool(ce["TS"] > lf["TS"] + 1e-9),
               fee=fee, fee_eq=pick(fe), planner=dict(TS=float(pl["TS"]), aH=float(pl["aH"]), aL=float(pl["aL"]), v=float(pl["v"])),
               fixed=dict(n_eq=len(lfx), lf=pick(lfx[0]), hard_cap=hc, hard_eq=pick(he) if he else None,
                          hard_helps=bool(he is not None and he["TS"] > lfx[0]["TS"] + 1e-9), fee=feex, fee_eq=pick(fex)))
    out["cases"].append(rec)
    print(f"{lab}: n_eq={len(lf_all)} LF TS={lf['TS']:.4f} aH={lf['aH']:.1f} aL={lf['aL']:.1f} | icap {cap:.2f} {ce['TS']:.4f} "
          f"| fee {fee:.4f} {fe['TS']:.4f} UH {fe['UH']:.3f} UL {fe['UL']:.3f} | planner {pl['TS']:.4f} "
          f"|| fixed LF {lfx[0]['TS']:.4f} hard {hc} {he['TS'] if he else float('nan'):.4f} fee {feex:.4f} {fex['TS']:.4f} [{time.time()-t0:.0f}s]", flush=True)

P = B.copy(c_a=0.001)
for cap in (1, 2, 3, 4, 5, 6, 8, 10, 15, 25, 50, 100):
    e = M.best_eq(P, cap=cap)
    out["cap_curve"].append(dict(cap=cap, **pick(e)))
lf = M.best_eq(P); out["cap_curve"].append(dict(cap=None, **pick(lf)))
for n in (1, 2, 3, 4, 5, 6, 7, 8, 10, 15, 25, 50, 100):
    e = M.hard_cap_eq(P, n)
    out["hard_cap_curve"].append(dict(cap=n, TS=float(e["TS"]), hires=float(e["hires"]), shareH=float(e["shareH"]),
                                      UH=float(e["UH"]), UL=float(e["UL"]), br_ok=e["br_ok"]))
print("curves done", f"[{time.time()-t0:.0f}s]", flush=True)

for label, P, cap in (("laissez-faire, c_a = 0.02", B.copy(c_a=0.02), np.inf),
                      ("laissez-faire, c_a = 0.005", B.copy(c_a=0.005), np.inf),
                      ("intensity cap 4, c_a = 0.001", B.copy(c_a=0.001), 4.0),
                      ("laissez-faire, y_L = -0.2", B.copy(c_a=0.001, yL=-0.2), np.inf)):
    e = M.best_eq(P, cap=cap)
    sims = [M.agent_sim(P, e["aH"], e["aL"], e["v"], n_workers=200_000, seed=sd) for sd in range(12)]
    agg = {k: (float(np.mean([s[k] for s in sims])), float(np.std([s[k] for s in sims], ddof=1) / np.sqrt(len(sims))))
           for k in ("mH", "mL", "screens", "Pi")}
    out["validation"].append(dict(label=label, theory=dict(mH=float(e["mH"]), mL=float(e["mL"]),
                                  screens=float(e["F"] / e["g"]), Pi=float(e["Pi"])), sim=agg))
    print("validation", label, {k: (round(float(out['validation'][-1]['theory'][k]), 4), round(agg[k][0], 4), round(agg[k][1], 5)) for k in agg},
          f"[{time.time()-t0:.0f}s]", flush=True)

json.dump(out, open("equilibrium_results_v2.json", "w"), indent=1)
print("saved", f"{time.time()-t0:.0f}s", flush=True)
