"""프로젝트별 baseline 분석 공통 엔진.

이 파일은 CSV 샘플 입력을 읽고, 프로젝트 유형별 계산 함수를 실행한 뒤 결과 CSV를 저장한다.
외부 패키지 의존도를 낮추기 위해 표준 라이브러리만 사용하며, 각 계산 단계는 후속 확장을 염두에 두고 함수로 분리했다.
"""

from __future__ import annotations

import csv
import math
import random
import statistics
from pathlib import Path


# 프로젝트 메타데이터는 README/데이터/실행 로직이 같은 분석 맥락을 공유하도록 한곳에 둔다.
PROJECT = {"analysis_type": "technical_backtest", "category": "Market Signals & Event Analytics", "columns": ["date", "close"], "long_window": 5, "methods": ["단기 이동평균이 장기 이동평균을 넘으면 long, 아니면 cash로 둔다.", "신호는 다음 기간 수익률에 적용하고 포지션 변경 비용을 차감한다.", "가격 경로는 이동평균 신호 계산 흐름을 설명하는 합성 데이터다."], "module_name": "technical_backtest_baseline", "objective": "단기/장기 이동평균 신호를 재현 가능한 백테스트 테이블로 변환한다.", "question": "이동평균 교차 신호는 거래비용을 고려해도 단순 보유보다 나은 경로를 만드는가?", "rows": [["2026-03-01", 100.0], ["2026-03-02", 101.2], ["2026-03-03", 100.7], ["2026-03-04", 102.1], ["2026-03-05", 103.4], ["2026-03-06", 102.8], ["2026-03-07", 104.3], ["2026-03-08", 105.1], ["2026-03-09", 103.9], ["2026-03-10", 106.0]], "sample_name": "price_series.csv", "short_window": 3, "title_en": "Technical Indicator Backtest", "title_ko": "기술적 지표 백테스트", "transaction_cost": 0.001}
# 저장소 기준 경로를 먼저 확정해 어느 위치에서 실행해도 동일한 입력/출력 파일을 사용한다.
ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "sample" / PROJECT["sample_name"]
# 모든 baseline 결과는 같은 파일명으로 저장해 레포별 산출물 위치를 표준화한다.
TABLE_PATH = ROOT / "outputs" / "tables" / "baseline_results.csv"


def _read_rows(path: Path = DATA_PATH) -> list[dict[str, str]]:
    """샘플 CSV를 행 단위 딕셔너리 목록으로 읽는다.

    프로젝트마다 입력 컬럼은 다르지만, 첫 행을 컬럼명으로 쓰는 구조는 동일하므로
    공통 DictReader로 읽어 이후 분석 함수가 같은 자료구조를 받을 수 있게 한다.
    """
    with path.open(newline="", encoding="utf-8") as fp:
        # DictReader는 컬럼명을 보존하므로 분석 함수에서 row['컬럼명'] 형태로 명확하게 접근할 수 있다.
        return list(csv.DictReader(fp))


def _as_float(row: dict[str, str], key: str, default: float = 0.0) -> float:
    """CSV에서 읽은 문자열 값을 부동소수점 숫자로 안전하게 변환한다.

    빈 문자열이나 누락값은 기본값으로 처리해 작은 샘플 파일에서도 계산 흐름이 끊기지 않게 한다.
    """
    # CSV는 모든 값을 문자열로 읽기 때문에 계산 전에 숫자형으로 변환한다.
    value = row.get(key, "")
    return default if value in ("", None) else float(value)


def _mean(values: list[float]) -> float:
    """숫자 리스트의 산술평균을 계산한다."""
    return sum(values) / len(values)


def _variance(values: list[float]) -> float:
    """표본분산을 계산한다.

    분모는 n-1을 사용해 작은 샘플에서 표본 추정량의 관례를 따른다.
    """
    if len(values) < 2:
        return 0.0
    avg = _mean(values)
    return sum((x - avg) ** 2 for x in values) / (len(values) - 1)


def _covariance(x: list[float], y: list[float]) -> float:
    """두 수익률 벡터의 표본 공분산을 계산한다."""
    if len(x) < 2:
        return 0.0
    mx, my = _mean(x), _mean(y)
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (len(x) - 1)


def _quantile(values: list[float], pct: float) -> float:
    """정렬된 표본에서 선형보간 방식의 분위수를 계산한다.

    VaR, terminal value 구간, 하방 분위수처럼 tail 지표를 만들 때 사용한다.
    """
    # 분위수는 정렬된 표본에서 위치를 계산한 뒤, 인접한 두 값 사이를 선형보간한다.
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
    """CSV 산출물에 기록할 숫자를 읽기 쉬운 자리수로 정리한다.

    NaN 또는 무한대가 생기면 후속 CSV 소비가 깨지지 않도록 0으로 대체한다.
    """
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return 0.0
    return round(value, digits)


def _norm_cdf(x: float) -> float:
    """표준정규 누적분포함수를 계산한다.

    외부 통계 패키지 없이 Black-Scholes 계산을 수행하기 위해 erf 기반 공식을 사용한다.
    """
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    """표준정규 확률밀도함수를 계산한다."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _bs_core(spot: float, strike: float, rate: float, vol: float, maturity: float) -> tuple[float, float]:
    """Black-Scholes 공식의 핵심 보조변수 d1, d2를 계산한다.

    d1은 위험조정된 moneyness와 변동성을 함께 반영하고, d2는 만기 행사확률 해석에 사용된다.
    """
    if spot <= 0 or strike <= 0 or vol <= 0 or maturity <= 0:
        raise ValueError("spot, strike, volatility, and maturity must be positive")
    sqrt_t = math.sqrt(maturity)
    # d1은 현재 moneyness, 금리, 변동성, 만기를 하나의 표준정규 변수로 압축한다.
    d1 = (math.log(spot / strike) + (rate + 0.5 * vol * vol) * maturity) / (vol * sqrt_t)
    d2 = d1 - vol * sqrt_t
    return d1, d2


def _bs_price(spot: float, strike: float, rate: float, vol: float, maturity: float, option_type: str) -> float:
    """유럽형 콜/풋 옵션의 Black-Scholes 가격을 계산한다."""
    d1, d2 = _bs_core(spot, strike, rate, vol, maturity)
    discount = math.exp(-rate * maturity)
    if option_type == "call":
        # 콜 가격은 주식 보유 성분에서 할인된 행사가 지급 성분을 차감한 값이다.
        return spot * _norm_cdf(d1) - strike * discount * _norm_cdf(d2)
    if option_type == "put":
        return strike * discount * _norm_cdf(-d2) - spot * _norm_cdf(-d1)
    raise ValueError(f"unsupported option_type: {option_type}")


def _bs_greeks(spot: float, strike: float, rate: float, vol: float, maturity: float, option_type: str) -> dict[str, float]:
    """Black-Scholes Greek을 같은 입력 가정에서 계산한다.

    Delta는 가격 방향성, Gamma는 비선형 곡률, Vega는 변동성 민감도,
    Theta는 연율 기준 시간가치 변화를 나타낸다.
    """
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
    # Gamma와 Vega는 콜/풋이 동일한 값을 가지므로 option_type 분기 밖에서 계산한다.
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
    """옵션 시나리오별 가격과 Greek을 한 행의 결과로 요약한다."""
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
        # 결과는 CSV 저장을 위해 평평한 딕셔너리 한 행으로 정리한다.
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
    """옵션 포지션의 Greek 노출을 충격 시나리오 손익으로 변환한다.

    Delta-Gamma-Vega 근사를 사용해 작은 가격/변동성 변화가 포지션 손익에 미치는 영향을 분해한다.
    """
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
    """시장가격을 Black-Scholes 변동성 입력으로 역산한다.

    단조적인 가격-변동성 관계를 이용해 이분법으로 내재변동성을 찾고, 검산 가격을 함께 기록한다.
    """
    output = []
    for row in rows:
        spot = _as_float(row, "spot")
        strike = _as_float(row, "strike")
        rate = _as_float(row, "rate")
        maturity = _as_float(row, "maturity")
        option_type = row["option_type"]
        target = _as_float(row, "market_price")
        low, high = 0.01, 2.0
        # 80회 반복이면 이 구간에서 실무적으로 충분한 소수점 정밀도를 얻는다.
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
    """로그정규 terminal value를 반복 생성해 분포 지표를 계산한다."""
    output = []
    for row in rows:
        rng = random.Random(int(_as_float(row, "seed")))
        base = _as_float(row, "base_value")
        mu = _as_float(row, "annual_mu")
        sigma = _as_float(row, "annual_sigma")
        horizon = _as_float(row, "horizon_days") / 252.0
        n_paths = int(_as_float(row, "n_paths"))
        # GBM 해석해 형태로 terminal value를 직접 생성해 경로 저장 비용을 줄인다.
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
    """GBM 경로 전체를 생성해 terminal 분포와 경로 중 하방 리스크를 요약한다."""
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
            # 각 경로는 현재가에서 시작해 단계별 충격을 누적하고, 동시에 peak와 drawdown을 추적한다.
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
    """Historical VaR, Expected Shortfall, 예외율을 계산한다."""
    returns = [_as_float(row, "portfolio_return") for row in rows]
    # 95% VaR는 수익률 분포의 하위 5% 분위수를 손실 크기로 뒤집어 표현한다.
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
    """공분산 행렬과 가중치로 포트폴리오 리스크 기여도를 분해한다."""
    assets = [row["asset"] for row in rows]
    weights = [_as_float(row, "weight") for row in rows]
    ret_keys = [key for key in rows[0] if key.startswith("ret_")]
    matrix = [[_as_float(row, key) for key in ret_keys] for row in rows]
    # 공분산 행렬은 개별 변동성과 자산 간 동행성을 동시에 담는 리스크 입력이다.
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
    """팩터나 거시 변수 값을 평균 0, 표준편차 1의 점수로 표준화한다."""
    avg = _mean(values)
    sd = statistics.pstdev(values) or 1.0
    return [(v - avg) / sd for v in values]


def _analyze_interest_rate(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    """거시 변수 표준화 점수를 결합해 금리 방향성 압력을 산출한다."""
    features = ["policy_rate", "inflation_yoy", "unemployment_rate", "term_spread", "credit_spread"]
    z = {feature: _z_scores([_as_float(row, feature) for row in rows]) for feature in features}
    output = []
    for idx, row in enumerate(rows):
        # 부호는 직관적 금리 압력을 기준으로 둔다: 물가는 상방, 실업률/신용스프레드는 하방 압력으로 반영한다.
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
    """정해진 간격의 long-only 포트폴리오 가중치 후보를 모두 생성한다.

    최적화 라이브러리 없이도 기준 포트폴리오를 찾기 위한 작은 grid search용 함수다.
    """
    units = 100 // step
    combos: list[list[int]] = []

    def build(prefix: list[int], remaining: int, slots: int) -> None:
        # 재귀적으로 남은 비중 단위를 배분해 합계가 100%인 후보만 만든다.
        if slots == 1:
            combos.append(prefix + [remaining])
            return
        for value in range(remaining + 1):
            build(prefix + [value], remaining - value, slots - 1)

    build([], units, n_assets)
    return [[value * step / 100 for value in combo] for combo in combos]


def _analyze_optimal_portfolio(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    """가중치 후보별 기대수익률, 변동성, Sharpe ratio를 비교해 최적 후보를 찾는다."""
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
    """목표비중 이탈 폭을 기준으로 밴드 리밸런싱을 수행한다."""
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
            # 밴드를 넘은 경우 목표비중으로 되돌리고, 매매금액에 비례한 비용을 차감한다.
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
    """복수 팩터 점수를 표준화하고 동일가중 composite score로 종목 순위를 만든다."""
    # 서로 단위가 다른 팩터를 직접 더하지 않도록 먼저 표준화한다.
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
    """저베타 leg와 고베타 leg를 구성하고 베타 1 기준 수익률 스프레드를 계산한다."""
    betas = [_as_float(row, "beta") for row in rows]
    # 중앙 베타를 기준으로 저베타/고베타 leg를 나누는 단순하고 재현 가능한 규칙을 사용한다.
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
    """CPPI/TIPP 포트폴리오 보험 경로를 계산한다.

    dynamic_floor 인자가 False이면 고정 floor CPPI, True이면 최고가치 연동 TIPP로 동작한다.
    """
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
        # cushion은 floor를 초과하는 여유자본이며, multiplier를 곱해 위험자산 예산을 결정한다.
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
    """간단한 영문 뉴스 텍스트를 소문자 토큰 목록으로 정리한다."""
    # 문장부호는 토큰 경계를 만들기 위해 공백으로 바꾸고, 영숫자만 유지한다.
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
    """소형 금융 감성 사전으로 긍정/부정 단어 수와 label을 계산한다."""
    tokens = _tokenize(text)
    positives = sum(1 for token in tokens if token in POSITIVE_WORDS)
    negatives = sum(1 for token in tokens if token in NEGATIVE_WORDS)
    score = positives - negatives
    label = "positive" if score > 0 else "negative" if score < 0 else "neutral"
    return len(tokens), positives, negatives, label


def _analyze_big_data(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    """체결 이벤트를 심볼 단위 VWAP/거래량/거래대금 지표로 집계한다."""
    grouped: dict[str, dict[str, object]] = {}
    for row in rows:
        symbol = row["symbol"]
        price = _as_float(row, "price")
        quantity = _as_float(row, "quantity")
        # 심볼별 누적 상태를 하나의 딕셔너리에 모아 VWAP 계산에 필요한 분자/분모를 동시에 관리한다.
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
    """뉴스 기사별 토큰 수, 감성 단어 수, 감성 label을 산출한다."""
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
    """뉴스 감성 신호를 다음 거래일 포지션과 전략 수익률로 연결한다."""
    output = []
    cumulative = 1.0
    previous_position = 0
    cost_rate = float(PROJECT["transaction_cost"])
    for row in rows:
        _, positives, negatives, label = _sentiment_score(f"{row['headline']} {row['summary']}")
        score = positives - negatives
        position = 1 if score > 0 else -1 if score < 0 else 0
        turnover = abs(position - previous_position)
        # 신호는 다음 거래일 수익률에 적용하고, 포지션 변화량에는 거래비용을 차감한다.
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
    """이벤트 윈도우의 abnormal return과 3일 누적반응을 계산한다."""
    output = []
    for row in rows:
        market = _as_float(row, "market_return")
        # 단순 시장조정 모형으로 주식수익률에서 같은 기간 시장수익률을 차감한다.
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
    """지정한 window 길이의 이동평균을 계산한다."""
    if idx + 1 < window:
        return None
    sample = values[idx + 1 - window : idx + 1]
    return _mean(sample)


def _analyze_technical_backtest(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    """이동평균 교차 신호를 포지션과 비용 차감 누적성과로 변환한다."""
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
        # 장단기 이동평균이 모두 계산된 뒤에만 long/cash 신호를 만든다.
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
    """프로젝트 메타데이터의 analysis_type에 맞는 분석 함수를 실행한다."""
    rows = _read_rows()
    analysis_type = PROJECT["analysis_type"]
    # analysis_type 값이 레포별로 다른 실행 경로를 선택하는 라우터 역할을 한다.
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
    """분석 결과 딕셔너리 목록을 CSV 파일로 저장한다.

    프로젝트별 결과 컬럼이 다르므로 모든 행의 키를 순서대로 모아 fieldnames를 만든다.
    """
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
    """명령행 실행 시 baseline 계산과 결과 저장을 순서대로 수행한다."""
    results = run_baseline()
    write_results(results)
    print(f"wrote {len(results)} rows to {TABLE_PATH}")


if __name__ == "__main__":
    main()
