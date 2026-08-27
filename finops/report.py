"""Report assembly — the lab's deliverable: baseline vs optimized + savings chart."""
from __future__ import annotations


def build_report(baseline_usd: float, optimized_usd: float, levers: dict,
                 sustainability: dict | None = None, period: str = "monthly") -> str:
    """Return a markdown cost-optimization report."""
    savings = baseline_usd - optimized_usd
    pct = (savings / baseline_usd * 100.0) if baseline_usd > 0 else 0.0
    lines = [
        "# NimbusAI - GPU Cost Optimization Report",
        "",
        f"**Period:** {period}  ",
        f"**Baseline spend:** ${baseline_usd:,.0f}  ",
        f"**Optimized spend:** ${optimized_usd:,.0f}  ",
        f"**Projected savings:** ${savings:,.0f}  (**{pct:.0f}%**)",
        "",
        "## Savings by lever",
        "",
        "| Lever | Savings (USD) |",
        "|---|---|",
    ]
    for name, amount in levers.items():
        lines.append(f"| {name} | ${amount:,.0f} |")
    if sustainability:
        lines += [
            "",
            "## Sustainability",
            "",
            f"- Energy per query: {sustainability.get('wh_per_query', 0):.2f} Wh",
            f"- Carbon per query: {sustainability.get('carbon_g', 0):.3f} gCO2e",
            f"- Cheapest+cleanest region: {sustainability.get('best_region', 'n/a')}",
        ]
        # ── Extension 4: Reasoning Budget ──
        if "reasoning_pct_req" in sustainability:
            lines += [
                "",
                "### Reasoning Budget Analysis (Extension)",
                "",
                f"- Reasoning requests: {sustainability.get('reasoning_pct_req', 0):.1f}% of total traffic",
                f"- Reasoning cost: {sustainability.get('reasoning_pct_cost', 0):.1f}% of total baseline cost",
                f"- Reasoning energy: {sustainability.get('reasoning_pct_wh', 0):.1f}% of total inference energy",
                f"- Energy per reasoning query: {sustainability.get('wh_per_reasoning_query', 0):.1f} Wh (~80x normal query)",
                f"- Potential savings from capping reasoning at 10% traffic: ${sustainability.get('cap_savings_usd', 0):.2f}/day",
            ]
        # ── Extension 5: Carbon-aware Scheduling ──
        if "carbon_savings_total_g" in sustainability:
            lines += [
                "",
                "### Carbon-aware Scheduling (Extension)",
                "",
                f"- Total carbon savings (interruptible jobs -> cleanest region): {sustainability.get('carbon_savings_total_g', 0):.0f} gCO2e ({sustainability.get('carbon_savings_pct', 0):.1f}%)",
                f"- Cleanest region used: {sustainability.get('cleanest_region', 'n/a')}",
            ]
            rc_list = sustainability.get("region_comparison", [])
            if rc_list:
                lines += [
                    "",
                    "| Region | gCO2/kWh | $/kWh | Carbon (g) | Energy Cost ($) |",
                    "|---|---|---|---|---|",
                ]
                for rc in sorted(rc_list, key=lambda x: x["gco2_per_kwh"]):
                    lines.append(f"| {rc['region']} | {rc['gco2_per_kwh']} | ${rc['price_per_kwh']:.3f} | {rc['total_carbon_g']:.0f} | ${rc['total_energy_cost']:.2f} |")
    lines += ["", "_Figures are June-2026 as-of snapshots; re-baseline before acting._"]
    return "\n".join(lines)


def savings_waterfall(levers: dict, path: str) -> str:
    """Write a simple savings bar chart PNG. Returns the path. No-op if matplotlib absent."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return ""
    names = list(levers.keys())
    vals = [levers[n] for n in names]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(names, vals, color="#2e548a")
    ax.set_ylabel("Savings (USD / month)")
    ax.set_title("GPU cost savings by FinOps lever")
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path
