from __future__ import annotations

import csv
import math
import random
import statistics
from pathlib import Path


PROJECT = {"analysis_type": "technical_backtest", "category": "Market Signals & Event Analytics", "columns": ["date", "close"], "long_window": 5, "methods": ["단기 이동평균이 장기 이동평균을 넘으면 long, 아니면 cash로 둔다.", "신호는 다음 기간 수익률에 적용하고 포지션 변경 비용을 차감한다.", "가격 경로는 합성 데이터이며 실제 종목 히스토리가 아니다."], "module_name": "technical_backtest_baseline", "objective": "단기/장기 이동평균 신호를 재현 가능한 백테스트 테이블로 변환한다.", "question": "이동평균 교차 신호는 거래비용을 고려해도 단순 보유보다 나은 경로를 만드는가?", "rows": [["2026-03-01", 100.0], ["2026-03-02", 101.2], ["2026-03-03", 100.7], ["2026-03-04", 102.1], ["2026-03-05", 103.4], ["2026-03-06", 102.8], ["2026-03-07", 104.3], ["2026-03-08", 105.1], ["2026-03-09", 103.9], ["2026-03-10", 106.0]], "sample_name": "price_series.csv", "short_window": 3, "title_en": "Technical Indicator Backtest", "title_ko": "기술적 지표 백테스트", "transaction_cost": 0.001}
ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "sample" / PROJECT["sample_name"]
TABLE_PATH = ROOT / "outputs" / "tables" / "baseline_results.csv"


def _read_rows(path: Path = DATA_PATH) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


def _as_float(row: dict[str, str], key: str, default: float = 0.0) -> float:
    value = row.get(key, "")
    return default if value in ("", None) else float(value)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _variance(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = _mean(values)
    return sum((x - avg) ** 2 for x in values) / (len(values) - 1)


def _covariance(x: list[float], y: list[float]) -> float:
    if len(x) < 2:
        return 0.0
    mx, my = _mean(x), _mean(y)
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (len(x) - 1)


def _quantile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * pct
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[int(position)]
    weight = position - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def _round(value: float, digits: int = 6) -> float:
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return 0.0
    return round(value, digits)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _bs_core(spot: float, strike: float, rate: float, vol: float, maturity: float) -> tuple[float, float]:
    if spot <= 0 or strike <= 0 or vol <= 0 or maturity <= 0:
        raise ValueError("spot, strike, volatility, and maturity must be positive")
    sqrt_t = math.sqrt(maturity)
    d1 = (math.log(spot / strike) + (rate + 0.5 * vol * vol) * maturity) / (vol * sqrt_t)
    d2 = d1 - vol * sqrt_t
    return d1, d2


def _bs_price(spot: float, strike: float, rate: float, vol: float, maturity: float, option_type: str) -> float:
    d1, d2 = _bs_core(spot, strike, rate, vol, maturity)
    discount = math.exp(-rate * maturity)
    if option_type == "call":
        return spot * _norm_cdf(d1) - strike * discount * _norm_cdf(d2)
    if option_type == "put":
        return strike * discount * _norm_cdf(-d2) - spot * _norm_cdf(-d1)
    raise ValueError(f"unsupported option_type: {option_type}")


def _bs_greeks(spot: float, strike: float, rate: float, vol: float, maturity: float, option_type: str) -> dict[str, float]:
    d1, d2 = _bs_core(spot, strike, rate, vol, maturity)
    sqrt_t = math.sqrt(maturity)
    discount = math.exp(-rate * maturity)
    pdf = _norm_pdf(d1)
    if option_type == "call":
        delta = _norm_cdf(d1)
        theta = -(spot * pdf * vol) / (2 * sqrt_t) - rate * strike * discount * _norm_cdf(d2)
    else:
        delta = _norm_cdf(d1) - 1
        theta = -(spot * pdf * vol) / (2 * sqrt_t) + rate * strike * discount * _norm_cdf(-d2)
    gamma = pdf / (spot * vol * sqrt_t)
    vega_abs = spot * pdf * sqrt_t
    return {
        "delta": delta,
        "gamma": gamma,
        "vega_abs": vega_abs,
        "vega_1pct": vega_abs / 100,
        "theta_annual": theta,
    }


def _analyze_black_scholes(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    output = []
    for row in rows:
        spot = _as_float(row, "spot")
        strike = _as_float(row, "strike")
        rate = _as_float(row, "rate")
        vol = _as_float(row, "volatility")
        maturity = _as_float(row, "maturity")
        option_type = row["option_type"]
        price = _bs_price(spot, strike, rate, vol, maturity, option_type)
        greeks = _bs_greeks(spot, strike, rate, vol, maturity, option_type)
        output.append({
            "scenario_id": row.get("scenario_id", row.get("quote_id", "")),
            "option_type": option_type,
            "moneyness": _round(spot / strike),
            "price": _round(price),
            "delta": _round(greeks["delta"]),
            "gamma": _round(greeks["gamma"]),
            "vega_1pct": _round(greeks["vega_1pct"]),
            "theta_annual": _round(greeks["theta_annual"]),
        })
    return output


def _analyze_greek(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    output = []
    for row in rows:
        spot = _as_float(row, "spot")
        strike = _as_float(row, "strike")
        rate = _as_float(row, "rate")
        vol = _as_float(row, "volatility")
        maturity = _as_float(row, "maturity")
        option_type = row["option_type"]
        contracts = _as_float(row, "position_contracts")
        multiplier = _as_float(row, "contract_multiplier")
        d_spot = spot * _as_float(row, "shock_spot_pct")
        d_vol = _as_float(row, "shock_vol_abs")
        greeks = _bs_greeks(spot, strike, rate, vol, maturity, option_type)
        unit_pnl = greeks["delta"] * d_spot + 0.5 * greeks["gamma"] * d_spot ** 2 + greeks["vega_abs"] * d_vol
        output.append({
            "scenario_id": row["scenario_id"],
            "delta": _round(greeks["delta"]),
            "gamma": _round(greeks["gamma"]),
            "vega_1pct": _round(greeks["vega_1pct"]),
            "spot_shock": _round(d_spot),
            "vol_shock_abs": _round(d_vol),
            "approx_unit_pnl": _round(unit_pnl),
            "approx_position_pnl": _round(unit_pnl * contracts * multiplier),
        })
    return output


def _analyze_implied_volatility(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    output = []
    for row in rows:
        spot = _as_float(row, "spot")
        strike = _as_float(row, "strike")
        rate = _as_float(row, "rate")
        maturity = _as_float(row, "maturity")
        option_type = row["option_type"]
        target = _as_float(row, "market_price")
        low, high = 0.01, 2.0
        for _ in range(80):
            mid = (low + high) / 2
            model = _bs_price(spot, strike, rate, mid, maturity, option_type)
            if model < target:
                low = mid
            else:
                high = mid
        implied = (low + high) / 2
        model_check = _bs_price(spot, strike, rate, implied, maturity, option_type)
        moneyness = spot / strike
        bucket = "ITM" if (option_type == "call" and moneyness > 1.03) or (option_type == "put" and moneyness < 0.97) else "OTM" if abs(moneyness - 1) > 0.03 else "ATM"
        output.append({
            "quote_id": row["quote_id"],
            "option_type": option_type,
            "moneyness": _round(moneyness),
            "moneyness_bucket": bucket,
            "market_price": _round(target),
            "implied_volatility": _round(implied),
            "model_price_check": _round(model_check),
            "pricing_error": _round(model_check - target),
        })
    return output


def _analyze_monte_carlo(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    output = []
    for row in rows:
        rng = random.Random(int(_as_float(row, "seed")))
        base = _as_float(row, "base_value")
        mu = _as_float(row, "annual_mu")
        sigma = _as_float(row, "annual_sigma")
        horizon = _as_float(row, "horizon_days") / 252.0
        n_paths = int(_as_float(row, "n_paths"))
        values = [
            base * math.exp((mu - 0.5 * sigma ** 2) * horizon + sigma * math.sqrt(horizon) * rng.gauss(0, 1))
            for _ in range(n_paths)
        ]
        output.append({
            "scenario_id": row["scenario_id"],
            "n_paths": n_paths,
            "mean_terminal_value": _round(_mean(values)),
            "p05_terminal_value": _round(_quantile(values, 0.05)),
            "p50_terminal_value": _round(_quantile(values, 0.50)),
            "p95_terminal_value": _round(_quantile(values, 0.95)),
            "loss_probability": _round(sum(v < base for v in values) / n_paths),
        })
    return output


def _analyze_stock_paths(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    output = []
    for row in rows:
        rng = random.Random(int(_as_float(row, "seed")))
        spot = _as_float(row, "spot")
        mu = _as_float(row, "annual_mu")
        sigma = _as_float(row, "annual_sigma")
        horizon = _as_float(row, "horizon_days") / 252.0
        n_steps = int(_as_float(row, "n_steps"))
        n_paths = int(_as_float(row, "n_paths"))
        barrier = _as_float(row, "down_barrier")
        dt = horizon / n_steps
        terminals, drawdowns = [], []
        barrier_hits = 0
        for _ in range(n_paths):
            price = spot
            peak = spot
            max_dd = 0.0
            touched = False
            for _step in range(n_steps):
                price *= math.exp((mu - 0.5 * sigma ** 2) * dt + sigma * math.sqrt(dt) * rng.gauss(0, 1))
                peak = max(peak, price)
                max_dd = max(max_dd, 1 - price / peak)
                touched = touched or price <= barrier
            terminals.append(price)
            drawdowns.append(max_dd)
            barrier_hits += int(touched)
        output.append({
            "scenario_id": row["scenario_id"],
            "mean_terminal_price": _round(_mean(terminals)),
            "p05_terminal_price": _round(_quantile(terminals, 0.05)),
            "p95_terminal_price": _round(_quantile(terminals, 0.95)),
            "down_barrier_touch_probability": _round(barrier_hits / n_paths),
            "average_max_drawdown": _round(_mean(drawdowns)),
        })
    return output


def _analyze_var(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    returns = [_as_float(row, "portfolio_return") for row in rows]
    q05 = _quantile(returns, 0.05)
    tail = [r for r in returns if r <= q05]
    var_95 = -q05
    es_95 = -_mean(tail)
    exceptions = sum(1 for r in returns if r < -var_95)
    exception_rate = exceptions / len(returns)
    zone = "green" if exception_rate <= 0.08 else "yellow" if exception_rate <= 0.15 else "red"
    return [{
        "confidence_level": 0.95,
        "sample_size": len(returns),
        "historical_var": _round(var_95),
        "expected_shortfall": _round(es_95),
        "exceptions": exceptions,
        "exception_rate": _round(exception_rate),
        "traffic_light_zone": zone,
    }]


def _analyze_covariance(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    assets = [row["asset"] for row in rows]
    weights = [_as_float(row, "weight") for row in rows]
    ret_keys = [key for key in rows[0] if key.startswith("ret_")]
    matrix = [[_as_float(row, key) for key in ret_keys] for row in rows]
    cov = [[_covariance(matrix[i], matrix[j]) for j in range(len(assets))] for i in range(len(assets))]
    port_var = sum(weights[i] * weights[j] * cov[i][j] for i in range(len(assets)) for j in range(len(assets)))
    output = []
    for i, asset in enumerate(assets):
        marginal = sum(cov[i][j] * weights[j] for j in range(len(assets)))
        component = weights[i] * marginal
        output.append({
            "asset": asset,
            "weight": _round(weights[i]),
            "standalone_volatility": _round(math.sqrt(max(cov[i][i], 0.0))),
            "marginal_risk_contribution": _round(marginal),
            "component_variance_contribution": _round(component),
            "risk_contribution_pct": _round(component / port_var if port_var else 0.0),
        })
    return output


def _z_scores(values: list[float]) -> list[float]:
    avg = _mean(values)
    sd = statistics.pstdev(values) or 1.0
    return [(v - avg) / sd for v in values]


def _analyze_interest_rate(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    features = ["policy_rate", "inflation_yoy", "unemployment_rate", "term_spread", "credit_spread"]
    z = {feature: _z_scores([_as_float(row, feature) for row in rows]) for feature in features}
    output = []
    for idx, row in enumerate(rows):
        score = (
            0.20 * z["policy_rate"][idx]
            + 0.45 * z["inflation_yoy"][idx]
            - 0.25 * z["unemployment_rate"][idx]
            + 0.25 * z["term_spread"][idx]
            - 0.15 * z["credit_spread"][idx]
        )
        predicted_change_bp = score * 12.0
        direction = "hike_pressure" if predicted_change_bp > 4 else "cut_pressure" if predicted_change_bp < -4 else "hold"
        output.append({
            "date": row["date"],
            "signal_score": _round(score),
            "predicted_change_bp": _round(predicted_change_bp),
            "predicted_direction": direction,
        })
    return output


def _weight_grid(n_assets: int, step: int = 10) -> list[list[float]]:
    units = 100 // step
    combos: list[list[int]] = []

    def build(prefix: list[int], remaining: int, slots: int) -> None:
        if slots == 1:
            combos.append(prefix + [remaining])
            return
        for value in range(remaining + 1):
            build(prefix + [value], remaining - value, slots - 1)

    build([], units, n_assets)
    return [[value * step / 100 for value in combo] for combo in combos]


def _analyze_optimal_portfolio(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    assets = [row["asset"] for row in rows]
    ret_keys = [key for key in rows[0] if key.startswith("ret_")]
    matrix = [[_as_float(row, key) for key in ret_keys] for row in rows]
    annual_means = [_mean(series) * 12 for series in matrix]
    cov = [[_covariance(matrix[i], matrix[j]) * 12 for j in range(len(assets))] for i in range(len(assets))]
    risk_free = 0.025
    best = None
    for weights in _weight_grid(len(assets), 10):
        port_ret = sum(w * r for w, r in zip(weights, annual_means))
        port_var = sum(weights[i] * weights[j] * cov[i][j] for i in range(len(assets)) for j in range(len(assets)))
        port_vol = math.sqrt(max(port_var, 0.0))
        sharpe = (port_ret - risk_free) / port_vol if port_vol else -999
        if best is None or sharpe > best["sharpe"]:
            best = {"weights": weights, "return": port_ret, "volatility": port_vol, "sharpe": sharpe}
    assert best is not None
    return [
        {
            "asset": asset,
            "optimal_weight": _round(weight),
            "portfolio_expected_return": _round(best["return"]),
            "portfolio_volatility": _round(best["volatility"]),
            "portfolio_sharpe": _round(best["sharpe"]),
        }
        for asset, weight in zip(assets, best["weights"])
    ]


def _analyze_rebalancing(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    asset_columns = PROJECT["asset_columns"]
    target = PROJECT["target_weights"]
    band = PROJECT["rebalance_band"]
    cost_rate = PROJECT["transaction_cost"]
    holdings = [100.0 * weight for weight in target]
    prev_weights = target[:]
    output = []
    for row in rows:
        returns = [_as_float(row, col) for col in asset_columns]
        holdings = [value * (1 + ret) for value, ret in zip(holdings, returns)]
        value_before = sum(holdings)
        current_weights = [value / value_before for value in holdings]
        max_deviation = max(abs(w - t) for w, t in zip(current_weights, target))
        rebalanced = max_deviation > band
        turnover = 0.0
        if rebalanced:
            desired = [value_before * weight for weight in target]
            turnover = sum(abs(d - h) for d, h in zip(desired, holdings)) / value_before
            cost = value_before * turnover * cost_rate
            value_after = value_before - cost
            holdings = [value_after * weight for weight in target]
            current_weights = target[:]
        else:
            cost = 0.0
            value_after = value_before
        output.append({
            "date": row["date"],
            "portfolio_value": _round(value_after),
            "max_weight_deviation": _round(max_deviation),
            "turnover": _round(turnover),
            "transaction_cost": _round(cost),
            "rebalanced": rebalanced,
        })
        prev_weights = current_weights
    return output


def _analyze_multi_factor(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    factors = ["value_score", "momentum_score", "quality_score", "low_volatility_score"]
    z = {factor: _z_scores([_as_float(row, factor) for row in rows]) for factor in factors}
    scored = []
    for idx, row in enumerate(rows):
        composite = sum(z[factor][idx] for factor in factors) / len(factors)
        scored.append((row["asset"], composite, _as_float(row, "market_cap")))
    ranked = sorted(scored, key=lambda item: item[1], reverse=True)
    selected = ranked[:3]
    positive_total = sum(max(score, 0.0) for _, score, _ in selected) or len(selected)
    selected_map = {
        asset: max(score, 0.0) / positive_total if positive_total != len(selected) else 1 / len(selected)
        for asset, score, _ in selected
    }
    return [
        {
            "asset": asset,
            "composite_score": _round(score),
            "rank": rank,
            "selected_weight": _round(selected_map.get(asset, 0.0)),
            "market_cap": _round(market_cap),
        }
        for rank, (asset, score, market_cap) in enumerate(ranked, start=1)
    ]


def _analyze_bab(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    betas = [_as_float(row, "beta") for row in rows]
    median_beta = _quantile(betas, 0.5)
    legs = {
        "low_beta_leg": [row for row in rows if _as_float(row, "beta") <= median_beta],
        "high_beta_leg": [row for row in rows if _as_float(row, "beta") > median_beta],
    }
    output = []
    scaled_returns = {}
    for leg, leg_rows in legs.items():
        avg_beta = _mean([_as_float(row, "beta") for row in leg_rows])
        avg_excess = _mean([_as_float(row, "expected_excess_return") for row in leg_rows])
        scale_to_beta_one = 1.0 / avg_beta if avg_beta else 0.0
        scaled_excess = avg_excess * scale_to_beta_one
        scaled_returns[leg] = scaled_excess
        output.append({
            "leg": leg,
            "asset_count": len(leg_rows),
            "average_beta": _round(avg_beta),
            "average_expected_excess_return": _round(avg_excess),
            "scale_to_beta_one": _round(scale_to_beta_one),
            "scaled_expected_excess_return": _round(scaled_excess),
        })
    output.append({
        "leg": "bab_spread",
        "asset_count": len(rows),
        "average_beta": "",
        "average_expected_excess_return": "",
        "scale_to_beta_one": "",
        "scaled_expected_excess_return": _round(scaled_returns["low_beta_leg"] - scaled_returns["high_beta_leg"]),
    })
    return output


def _analyze_portfolio_insurance(rows: list[dict[str, str]], dynamic_floor: bool) -> list[dict[str, object]]:
    value = float(PROJECT["initial_value"])
    floor = value * float(PROJECT["floor_ratio"])
    peak = value
    multiplier = float(PROJECT["multiplier"])
    max_risky_weight = float(PROJECT["max_risky_weight"])
    output = []
    for row in rows:
        if dynamic_floor:
            peak = max(peak, value)
            floor = max(floor, peak * float(PROJECT["floor_ratio"]))
        cushion = max(value - floor, 0.0)
        risky_weight = min(max(multiplier * cushion / value, 0.0), max_risky_weight) if value else 0.0
        safe_weight = 1.0 - risky_weight
        risky_return = _as_float(row, "risky_return")
        safe_return = _as_float(row, "safe_return")
        value *= risky_weight * (1 + risky_return) + safe_weight * (1 + safe_return)
        breach = value < floor
        output.append({
            "date": row["date"],
            "floor_value": _round(floor),
            "cushion": _round(cushion),
            "risky_weight": _round(risky_weight),
            "safe_weight": _round(safe_weight),
            "portfolio_value": _round(value),
            "floor_breach": breach,
        })
    return output


def _tokenize(text: str) -> list[str]:
    cleaned = []
    for char in text.lower():
        cleaned.append(char if char.isalnum() or char.isspace() else " ")
    return [token for token in "".join(cleaned).split() if token]


POSITIVE_WORDS = {
    "beats", "strong", "stronger", "stable", "improved", "improvement", "buyback", "approved",
    "resilient", "growth", "supports", "secures", "lower", "cash", "return"
}
NEGATIVE_WORDS = {
    "pressure", "warned", "risk", "delay", "disruption", "higher", "slow", "faces",
    "probe", "uncertainty", "legal", "shutdown", "downside", "cost"
}


def _sentiment_score(text: str) -> tuple[int, int, int, str]:
    tokens = _tokenize(text)
    positives = sum(1 for token in tokens if token in POSITIVE_WORDS)
    negatives = sum(1 for token in tokens if token in NEGATIVE_WORDS)
    score = positives - negatives
    label = "positive" if score > 0 else "negative" if score < 0 else "neutral"
    return len(tokens), positives, negatives, label


def _analyze_big_data(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    for row in rows:
        symbol = row["symbol"]
        price = _as_float(row, "price")
        quantity = _as_float(row, "quantity")
        entry = grouped.setdefault(symbol, {"notional": 0.0, "quantity": 0.0, "count": 0, "venues": set()})
        entry["notional"] = float(entry["notional"]) + price * quantity
        entry["quantity"] = float(entry["quantity"]) + quantity
        entry["count"] = int(entry["count"]) + 1
        entry["venues"].add(row["venue"])
    output = []
    for symbol, entry in sorted(grouped.items()):
        quantity = float(entry["quantity"])
        notional = float(entry["notional"])
        output.append({
            "symbol": symbol,
            "trade_count": entry["count"],
            "total_quantity": _round(quantity),
            "notional_value": _round(notional),
            "vwap": _round(notional / quantity if quantity else 0.0),
            "venue_count": len(entry["venues"]),
        })
    return output


def _analyze_news_nlp(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    output = []
    for row in rows:
        token_count, positives, negatives, label = _sentiment_score(f"{row['headline']} {row['summary']}")
        output.append({
            "article_id": row["article_id"],
            "symbol": row["symbol"],
            "token_count": token_count,
            "positive_word_count": positives,
            "negative_word_count": negatives,
            "sentiment_score": positives - negatives,
            "sentiment_label": label,
        })
    return output


def _analyze_sentiment_strategy(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    output = []
    cumulative = 1.0
    previous_position = 0
    cost_rate = float(PROJECT["transaction_cost"])
    for row in rows:
        _, positives, negatives, label = _sentiment_score(f"{row['headline']} {row['summary']}")
        score = positives - negatives
        position = 1 if score > 0 else -1 if score < 0 else 0
        turnover = abs(position - previous_position)
        strategy_return = position * _as_float(row, "next_day_return") - turnover * cost_rate
        cumulative *= 1 + strategy_return
        output.append({
            "date": row["date"],
            "symbol": row["symbol"],
            "sentiment_label": label,
            "position": position,
            "next_day_return": _round(_as_float(row, "next_day_return")),
            "strategy_return_after_cost": _round(strategy_return),
            "cumulative_value": _round(cumulative),
        })
        previous_position = position
    return output


def _analyze_event_study(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    output = []
    for row in rows:
        market = _as_float(row, "market_return")
        ar_minus_1 = _as_float(row, "stock_return_t_minus_1") - market
        ar_0 = _as_float(row, "stock_return_t0") - market
        ar_plus_1 = _as_float(row, "stock_return_t_plus_1") - market
        output.append({
            "event_id": row["event_id"],
            "symbol": row["symbol"],
            "event_tone": row["event_tone"],
            "abnormal_return_t_minus_1": _round(ar_minus_1),
            "abnormal_return_t0": _round(ar_0),
            "abnormal_return_t_plus_1": _round(ar_plus_1),
            "car_3day": _round(ar_minus_1 + ar_0 + ar_plus_1),
        })
    return output


def _moving_average(values: list[float], window: int, idx: int) -> float | None:
    if idx + 1 < window:
        return None
    sample = values[idx + 1 - window : idx + 1]
    return _mean(sample)


def _analyze_technical_backtest(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    prices = [_as_float(row, "close") for row in rows]
    short_window = int(PROJECT["short_window"])
    long_window = int(PROJECT["long_window"])
    cost_rate = float(PROJECT["transaction_cost"])
    output = []
    previous_signal = 0
    cumulative = 1.0
    for idx, row in enumerate(rows):
        short_ma = _moving_average(prices, short_window, idx)
        long_ma = _moving_average(prices, long_window, idx)
        signal = 1 if short_ma is not None and long_ma is not None and short_ma > long_ma else 0
        daily_return = 0.0 if idx == 0 else prices[idx] / prices[idx - 1] - 1
        turnover = abs(signal - previous_signal)
        strategy_return = previous_signal * daily_return - turnover * cost_rate
        cumulative *= 1 + strategy_return
        output.append({
            "date": row["date"],
            "close": _round(prices[idx]),
            "short_ma": "" if short_ma is None else _round(short_ma),
            "long_ma": "" if long_ma is None else _round(long_ma),
            "signal": signal,
            "strategy_return_after_cost": _round(strategy_return),
            "cumulative_value": _round(cumulative),
        })
        previous_signal = signal
    return output


def run_baseline() -> list[dict[str, object]]:
    rows = _read_rows()
    analysis_type = PROJECT["analysis_type"]
    if analysis_type == "black_scholes":
        return _analyze_black_scholes(rows)
    if analysis_type == "greek":
        return _analyze_greek(rows)
    if analysis_type == "implied_volatility":
        return _analyze_implied_volatility(rows)
    if analysis_type == "monte_carlo":
        return _analyze_monte_carlo(rows)
    if analysis_type == "stock_paths":
        return _analyze_stock_paths(rows)
    if analysis_type == "var":
        return _analyze_var(rows)
    if analysis_type == "covariance":
        return _analyze_covariance(rows)
    if analysis_type == "interest_rate":
        return _analyze_interest_rate(rows)
    if analysis_type == "optimal_portfolio":
        return _analyze_optimal_portfolio(rows)
    if analysis_type == "rebalancing":
        return _analyze_rebalancing(rows)
    if analysis_type == "multi_factor":
        return _analyze_multi_factor(rows)
    if analysis_type == "bab":
        return _analyze_bab(rows)
    if analysis_type == "cppi":
        return _analyze_portfolio_insurance(rows, dynamic_floor=False)
    if analysis_type == "tipp":
        return _analyze_portfolio_insurance(rows, dynamic_floor=True)
    if analysis_type == "big_data":
        return _analyze_big_data(rows)
    if analysis_type == "news_nlp":
        return _analyze_news_nlp(rows)
    if analysis_type == "sentiment_strategy":
        return _analyze_sentiment_strategy(rows)
    if analysis_type == "event_study":
        return _analyze_event_study(rows)
    if analysis_type == "technical_backtest":
        return _analyze_technical_backtest(rows)
    raise ValueError(f"unsupported analysis_type: {analysis_type}")


def write_results(rows: list[dict[str, object]], path: Path = TABLE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    results = run_baseline()
    write_results(results)
    print(f"wrote {len(results)} rows to {TABLE_PATH}")


if __name__ == "__main__":
    main()
