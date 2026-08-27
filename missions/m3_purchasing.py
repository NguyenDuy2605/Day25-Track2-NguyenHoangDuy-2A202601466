"""M3 — Purchasing Strategy: break-even, tier choice, spot-checkpoint sim (deck §4).

Run: python missions/m3_purchasing.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num, catalog_by_type
from finops import pricing, sustainability

DAYS = 30


def run(verbose: bool = True) -> dict:
    jobs = load_csv("workloads.csv")
    cat = catalog_by_type()
    on_demand_monthly = optimized_monthly = 0.0
    recs = []
    for j in jobs:
        gtype = j["gpu_type"]
        ngpu = int(num(j["num_gpus"]))
        hpd = num(j["hours_per_day"])
        interruptible = bool(int(num(j["interruptible"])))
        c = cat[gtype]
        gpu_hours = hpd * DAYS * ngpu
        od = num(c["on_demand_hr"])
        on_demand_cost = gpu_hours * od

        tier = pricing.recommend_tier(hpd, interruptible, gpu_type=gtype, days=int(num(j.get("days", 30))))
        if tier == "spot":
            sim = pricing.spot_checkpoint_cost(gpu_hours, num(c["spot_hr"]), od, interrupt_rate=pricing.INTERRUPTION_RATES.get(gtype, 0.05))
            opt_cost = sim["spot_cost"]
        elif tier == "reserved":
            opt_cost = gpu_hours * num(c["reserved_3yr_hr"])
        elif tier == "reserved_1yr":
            opt_cost = gpu_hours * num(c["reserved_1yr_hr"])
        else:
            opt_cost = on_demand_cost

        on_demand_monthly += on_demand_cost
        optimized_monthly += opt_cost
        recs.append({"job_id": j["job_id"], "gpu_type": gtype, "tier": tier,
                     "on_demand": round(on_demand_cost), "optimized": round(opt_cost)})

    savings = on_demand_monthly - optimized_monthly
    savings_pct = savings / on_demand_monthly * 100 if on_demand_monthly else 0.0

    if verbose:
        print("== M3 Purchasing Strategy ==")
        print(f"break-even utilization @ 45% reserved discount = {pricing.break_even_utilization(0.45):.0%}")
        print(f"{'job':18}{'gpu':7}{'tier':11}{'on-demand':>12}{'optimized':>12}")
        for r in recs:
            print(f"{r['job_id']:18}{r['gpu_type']:7}{r['tier']:11}${r['on_demand']:>11,}${r['optimized']:>11,}")
        print(f"\nmonthly: on-demand ${on_demand_monthly:,.0f} -> optimized ${optimized_monthly:,.0f}  ({savings_pct:.1f}% saved)")

    # ── Extension 5: Carbon-aware Scheduling ──
    total_carbon_current = 0.0
    total_carbon_cleanest = 0.0
    total_kwh_current = 0.0
    carbon_jobs = []
    cleanest_region = min(sustainability.REGION_CARBON, key=sustainability.REGION_CARBON.get)
    dirtiest_region = max(sustainability.REGION_CARBON, key=sustainability.REGION_CARBON.get)

    for j in jobs:
        if int(num(j["interruptible"])) != 1:
            continue
        gtype = j["gpu_type"]
        ngpu = int(num(j["num_gpus"]))
        hpd = num(j["hours_per_day"])
        days = int(num(j.get("days", 30)))
        c = cat[gtype]
        watts = num(c["watts"])
        gpu_hours = hpd * days * ngpu
        kwh = (watts * gpu_hours) / 1000.0  # convert Wh to kWh

        # Current carbon (assume us-east-1)
        carbon_now = sustainability.carbon_g(kwh * 1000.0, "us-east-1")  # wh = kwh*1000
        # Cleanest region carbon
        carbon_best = sustainability.carbon_g(kwh * 1000.0, cleanest_region)

        total_carbon_current += carbon_now
        total_carbon_cleanest += carbon_best
        total_kwh_current += kwh

        carbon_jobs.append({
            "job_id": j["job_id"],
            "gpu_type": gtype,
            "kwh": round(kwh, 1),
            "carbon_current_g": round(carbon_now, 1),
            "carbon_cleanest_g": round(carbon_best, 1),
            "carbon_saved_g": round(carbon_now - carbon_best, 1),
            "carbon_saved_pct": round((carbon_now - carbon_best) / carbon_now * 100, 1) if carbon_now > 0 else 0,
        })

    carbon_savings_total_g = total_carbon_current - total_carbon_cleanest
    carbon_savings_pct = (carbon_savings_total_g / total_carbon_current * 100) if total_carbon_current > 0 else 0

    # Region comparison table
    region_comparison = []
    for region in sorted(sustainability.REGION_CARBON.keys()):
        gco2_kwh = sustainability.REGION_CARBON[region]
        price_kwh = sustainability.REGION_PRICE_KWH.get(region, 0.12)
        total_carbon = sustainability.carbon_g(total_kwh_current * 1000.0, region)
        total_energy_cost = sustainability.energy_cost_usd(total_kwh_current * 1000.0, region)
        region_comparison.append({
            "region": region,
            "gco2_per_kwh": gco2_kwh,
            "price_per_kwh": price_kwh,
            "total_carbon_g": round(total_carbon, 1),
            "total_energy_cost": round(total_energy_cost, 2),
        })

    if verbose:
        print()
        print("--- Extension 5: Carbon-aware Scheduling ---")
        print(f"Cleanest region: {cleanest_region} ({sustainability.REGION_CARBON[cleanest_region]} gCO2/kWh)")
        print(f"Dirtiest region: {dirtiest_region} ({sustainability.REGION_CARBON[dirtiest_region]} gCO2/kWh)")
        print(f"Total energy of interruptible jobs: {total_kwh_current:.0f} kWh")
        print(f"Carbon at us-east-1: {total_carbon_current:.0f} gCO2e")
        print(f"Carbon at {cleanest_region}: {total_carbon_cleanest:.0f} gCO2e")
        print(f"Carbon savings: {carbon_savings_total_g:.0f} gCO2e ({carbon_savings_pct:.1f}%)")
        print()
        print("Region comparison (all interruptible jobs):")
        print(f"{'Region':18} {'gCO2/kWh':>10} {'$/kWh':>8} {'Carbon g':>12} {'Energy $':>10}")
        for rc in sorted(region_comparison, key=lambda x: x["gco2_per_kwh"]):
            print(f"{rc['region']:18} {rc['gco2_per_kwh']:>10} ${rc['price_per_kwh']:>6.3f} {rc['total_carbon_g']:>10.0f} ${rc['total_energy_cost']:>7.2f}")
        print()
        print("Per-job carbon savings:")
        print(f"{'Job':18} {'GPU':7} {'kWh':>8} {'Current gCO2':>14} {'Clean gCO2':>12} {'Saved gCO2':>12} {'Saved%':>8}")
        for cj in sorted(carbon_jobs, key=lambda x: -x["carbon_saved_g"]):
            print(f"{cj['job_id']:18} {cj['gpu_type']:7} {cj['kwh']:>8.0f} {cj['carbon_current_g']:>12.0f} {cj['carbon_cleanest_g']:>10.0f} {cj['carbon_saved_g']:>10.0f} {cj['carbon_saved_pct']:>7.1f}%")

    return {"recommendations": recs, "on_demand_monthly": round(on_demand_monthly),
            "optimized_monthly": round(optimized_monthly), "savings_pct": round(savings_pct, 1),
            # Extension 5 data
            "carbon_savings_total_g": round(carbon_savings_total_g, 1),
            "carbon_savings_pct": round(carbon_savings_pct, 1),
            "cleanest_region": cleanest_region,
            "region_comparison": region_comparison,
            "carbon_jobs": carbon_jobs,
    }


if __name__ == "__main__":
    run()
