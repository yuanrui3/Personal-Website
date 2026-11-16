"""Charts for the blog post 'Managing AI agents: a short handbook'.

Data are copied from the handbook's sources:
- Kim et al., Towards a Science of Scaling Agent Systems, arXiv:2512.08296
- DataNorth, AI effort levels explained (Artificial Analysis Intelligence Index, read 8 Oct 2026)
- The New Stack, Auto Mode will soon be the default in Claude Code (7 Aug 2026)
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

BLUE = "#1772d0"
GREY = "#9a9a9a"
INK = "#222222"
MID = "#666666"

plt.rcParams.update({
    "svg.fonttype": "none",
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.titlesize": 12.5,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": "#888888",
    "xtick.color": "#444444",
    "ytick.color": "#444444",
    "svg.hashsalt": "managing-ai-agents",
})


def title(fig, text):
    """Finding as the title, flush with the left edge of the figure."""
    fig.suptitle(text, x=0.012, ha="left", fontsize=12.5, fontweight="bold")


def teams(path):
    rows = [  # benchmark, kind of work, worst design, best design (% change vs one agent)
        ("Finance-Agent", "financial analysis", 57.0, 80.8),
        ("BrowseComp-Plus", "web research", -35.0, 9.2),
        ("WorkBench", "workplace tool tasks", -11.0, 5.6),
        ("Terminal-Bench", "command-line tasks", -19.2, 1.7),
        ("SWE-bench Verified", "code fixes", -14.9, -2.1),
        ("PlanCraft", "step-by-step planning", -70.0, -39.1),
    ]
    fig, ax = plt.subplots(figsize=(8.7, 4.3))
    ys = list(range(len(rows)))[::-1]
    for y, (name, kind, lo, hi) in zip(ys, rows):
        ax.plot([lo, hi], [y, y], color="#d6d6d6", lw=3, solid_capstyle="round", zorder=1)
        ax.scatter([lo], [y], s=55, color=GREY, zorder=3)
        ax.scatter([hi], [y], s=55, color=BLUE, zorder=3)
        ax.text(lo - 3, y, f"{lo:+.1f}%".replace("+-", "−").replace("-", "−"), ha="right",
                va="center", fontsize=10, color=MID)
        ax.text(hi + 3, y, f"{hi:+.1f}%".replace("-", "−"), ha="left", va="center", fontsize=10,
                color=BLUE, fontweight="bold")
    ax.set_yticks(ys)
    ax.set_yticklabels([f"{n}\n{k}" for n, k, _, _ in rows], fontsize=10)
    ax.axvline(0, color="#555555", lw=1)
    ax.set_xlim(-100, 112)
    ax.set_xticks([-75, -50, -25, 0, 25, 50, 75, 100])
    ax.set_xticklabels(["−75%", "−50%", "−25%", "0", "+25%", "+50%", "+75%", "+100%"])
    ax.xaxis.grid(True, color="#ebebeb", lw=0.8)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("Change in performance when a team replaces one agent on the same model")
    ax.set_ylim(-0.6, len(rows) - 0.4)
    title(fig, "Teams of agents helped most on financial analysis and hurt most on planning")
    fig.text(0.012, 0.888, "●  worst team design", color=GREY, fontsize=10)
    fig.text(0.22, 0.888, "●  best team design", color=BLUE, fontsize=10, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.905))
    fig.savefig(path)
    plt.close(fig)


def effort(path):
    levels = ["Low", "Medium", "High", "Xhigh", "Max"]
    cost = [0.13, 0.21, 0.32, 0.39, 0.72]
    score = [42, 48, 50, 51, 52]
    fig, ax = plt.subplots(figsize=(8.7, 4.0))
    ax.plot(cost, score, color=BLUE, lw=2, marker="o", ms=6, zorder=3)
    offsets = {"Low": (10, -4, "left"), "Medium": (-10, 6, "right"), "High": (6, -16, "left"),
               "Xhigh": (-8, 9, "right"), "Max": (0, 10, "center")}
    for lv, c, s in zip(levels, cost, score):
        dx, dy, ha = offsets[lv]
        ax.annotate(f"{lv}  {s}", (c, s), xytext=(dx, dy), textcoords="offset points", ha=ha,
                    fontsize=10.5, color=INK, fontweight="bold")
    ax.annotate("+6 points for +$0.08 a task", (0.17, 45), xytext=(14, 0),
                textcoords="offset points", fontsize=10, color=MID, va="center")
    ax.annotate("+1 point for +$0.33 a task (85% more)", (0.555, 51.5), xytext=(0, -26),
                textcoords="offset points", fontsize=10, color=MID, ha="center")
    ax.set_xlim(0, 0.8)
    ax.set_ylim(40, 54)
    ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8])
    ax.set_xticklabels(["$0", "$0.20", "$0.40", "$0.60", "$0.80"])
    ax.set_yticks([40, 44, 48, 52])
    ax.yaxis.grid(True, color="#ebebeb", lw=0.8)
    ax.set_axisbelow(True)
    ax.set_xlabel("Cost per benchmark task")
    ax.set_ylabel("Intelligence Index score")
    title(fig, "The top effort step bought one point for 85% more cost")
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    fig.savefig(path)
    plt.close(fig)


def catches(path):
    rows = [
        ("Human approvers,\nall permission prompts", 13.6, GREY),
        ("Human approvers,\nafter 50 prompts in a session", 5.0, BLUE),
        ("Automated classifier,\nClaude Code auto mode", 89.0, GREY),
    ]
    fig, ax = plt.subplots(figsize=(8.7, 3.0))
    ys = [2, 1, 0]
    for y, (name, v, col) in zip(ys, rows):
        ax.barh(y, v, height=0.5, color=col, zorder=2)
        ax.text(v + 1.5, y, f"{v:g}%", va="center", fontsize=10.5,
                color=BLUE if col == BLUE else INK, fontweight="bold")
    ax.set_yticks(ys)
    ax.set_yticklabels([r[0] for r in rows], fontsize=10)
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"])
    ax.xaxis.grid(True, color="#ebebeb", lw=0.8)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("Share of dangerous commands caught")
    title(fig, "After 50 prompts, human approvers caught 5% of dangerous commands")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(path)
    plt.close(fig)


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    teams(f"{out}/fig-teams.svg")
    effort(f"{out}/fig-effort.svg")
    catches(f"{out}/fig-catch.svg")
