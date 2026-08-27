"""M2 — Inference Cost Levers: $/1M-token, batch x cache x cascade (deck §7).

Run: python missions/m2_inference_levers.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num
from finops import pricing, sustainability

# $/1M tokens (input, output) — illustrative 2026.
MODEL_PRICES = {"small": (0.20, 0.40), "large": (3.00, 15.00)}


def run(verbose: bool = True) -> dict:
    rows = load_csv("token_usage.csv")
    base_cost = opt_cost = 0.0
    base_cost_reasoning = opt_cost_reasoning = 0.0
    base_cost_non_reasoning = opt_cost_non_reasoning = 0.0
    total_tokens = total_tokens_reasoning = total_tokens_non_reasoning = 0
    reasoning_requests = total_requests = 0
    total_wh_reasoning = total_wh_non_reasoning = 0.0
    for r in rows:
        inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
        cached = int(num(r["cached_input_tokens"]))
        is_batch = bool(int(num(r["is_batch"])))
        is_reasoning = bool(int(num(r["is_reasoning"])))
        total_tokens += inp + out
        total_requests += 1

        # BASELINE: naive deployment — everything on the large model, no cache, no batch
        lin, lout = MODEL_PRICES["large"]
        base_req = pricing.request_cost(inp, out, lin, lout)
        base_cost += base_req

        # OPTIMIZED: cascade (route_tier), prompt caching, batch API
        pin, pout = MODEL_PRICES[r["route_tier"]]
        opt_req = pricing.request_cost(inp, out, pin, pout, cached_in=cached, batch=is_batch)
        opt_cost += opt_req

        # ── Extension 4: Reasoning Budget ──
        if is_reasoning:
            total_tokens_reasoning += inp + out
            base_cost_reasoning += base_req
            opt_cost_reasoning += opt_req
            reasoning_requests += 1
            wh = sustainability.wh_per_query(inp + out, is_reasoning=True)
            total_wh_reasoning += wh
        else:
            total_tokens_non_reasoning += inp + out
            base_cost_non_reasoning += base_req
            opt_cost_non_reasoning += opt_req
            wh = sustainability.wh_per_query(inp + out, is_reasoning=False)
            total_wh_non_reasoning += wh

    base_pm = pricing.dollars_per_million(base_cost, total_tokens)
    opt_pm = pricing.dollars_per_million(opt_cost, total_tokens)
    savings_pct = (1 - opt_cost / base_cost) * 100 if base_cost else 0.0

    # Reasoning stats
    reasoning_pct_req = (reasoning_requests / total_requests * 100) if total_requests else 0.0
    reasoning_pct_tokens = (total_tokens_reasoning / total_tokens * 100) if total_tokens else 0.0
    reasoning_pct_cost = (base_cost_reasoning / base_cost * 100) if base_cost else 0.0
    reasoning_pct_wh = (total_wh_reasoning / (total_wh_reasoning + total_wh_non_reasoning) * 100) if (total_wh_reasoning + total_wh_non_reasoning) else 0.0

    # What is the extra cost of reasoning vs non-reasoning?
    if reasoning_requests > 0:
        non_reasoning_reqs = total_requests - reasoning_requests
        avg_cost_non_reasoning = base_cost_non_reasoning / non_reasoning_reqs if non_reasoning_reqs > 0 else 0
        hypothetical_cost = reasoning_requests * avg_cost_non_reasoning
        extra_cost_reasoning = base_cost_reasoning - hypothetical_cost
        extra_pct = (extra_cost_reasoning / base_cost * 100) if base_cost > 0 else 0
        avg_wh_non_reasoning = total_wh_non_reasoning / non_reasoning_reqs if non_reasoning_reqs > 0 else 0
        hypothetical_wh = reasoning_requests * avg_wh_non_reasoning
        extra_wh_reasoning = total_wh_reasoning - hypothetical_wh
    else:
        extra_cost_reasoning = 0.0
        extra_pct = 0.0
        extra_wh_reasoning = 0.0

    if verbose:
        print("== M2 Inference Cost Levers ==")
        print(f"requests={total_requests}  tokens={total_tokens:,}")
        print(f"baseline  : ${base_cost:,.2f}/day   ${base_pm:.3f}/1M-token")
        print(f"optimized : ${opt_cost:,.2f}/day   ${opt_pm:.3f}/1M-token")
        print(f"savings   : {savings_pct:.1f}%  (cascade + caching + batch)")
        print(f"discount stack (batch + 100% cache): {pricing.discount_stack(batch=True, cache_hit_frac=1.0):.3f} of naive")
        print()
        print("--- Extension 4: Reasoning Budget ---")
        print(f"Reasoning requests: {reasoning_requests}/{total_requests} ({reasoning_pct_req:.1f}%)")
        print(f"Reasoning tokens:   {total_tokens_reasoning:,}/{total_tokens:,} ({reasoning_pct_tokens:.1f}%)")
        print(f"Reasoning base cost: ${base_cost_reasoning:.2f}/{base_cost:.2f} ({reasoning_pct_cost:.1f}%)")
        print(f"Reasoning energy:    {total_wh_reasoning:.0f} Wh / {(total_wh_reasoning + total_wh_non_reasoning):.0f} Wh total ({reasoning_pct_wh:.1f}%)")
        print(f"Extra cost from reasoning vs equivalent non-reasoning traffic: ${extra_cost_reasoning:.2f}/day ({extra_pct:.1f}% of total)")
        print(f"Extra energy from reasoning: {extra_wh_reasoning:.0f} Wh/day")

    return {
        "baseline_daily": round(base_cost, 2), "optimized_daily": round(opt_cost, 2),
        "baseline_per_m": round(base_pm, 3), "optimized_per_m": round(opt_pm, 3),
        "savings_pct": round(savings_pct, 1), "total_tokens": total_tokens,
        # Extension 4 data
        "reasoning_requests": reasoning_requests,
        "total_requests": total_requests,
        "reasoning_pct_req": round(reasoning_pct_req, 1),
        "reasoning_pct_tokens": round(reasoning_pct_tokens, 1),
        "reasoning_pct_cost": round(reasoning_pct_cost, 1),
        "reasoning_pct_wh": round(reasoning_pct_wh, 1),
        "base_cost_reasoning": round(base_cost_reasoning, 2),
        "opt_cost_reasoning": round(opt_cost_reasoning, 2),
        "total_wh_reasoning": round(total_wh_reasoning, 0),
        "total_wh_non_reasoning": round(total_wh_non_reasoning, 0),
        "extra_cost_reasoning": round(extra_cost_reasoning, 2),
        "extra_pct": round(extra_pct, 1),
        "extra_wh_reasoning": round(extra_wh_reasoning, 0),
    }


if __name__ == "__main__":
    run()
