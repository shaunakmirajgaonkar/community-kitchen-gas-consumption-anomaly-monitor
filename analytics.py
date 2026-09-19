from __future__ import annotations

import math
from typing import Iterable

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = [
    "kitchen_id",
    "community",
    "lpg_kg_used",
    "meals_served",
    "lpg_delivered_kg",
    "days_in_period",
    "delivery_gap_days",
    "stove_condition_score",
    "regulator_condition_score",
    "hose_condition_score",
    "cylinder_change_count",
    "cooking_hours_day",
    "storage_condition_score",
    "equipment_age_years",
    "reported_odor_events",
]

DISPLAY_NAMES = {
    "lpg_kg_used": "LPG used (kg)",
    "meals_served": "Meals served",
    "lpg_delivered_kg": "LPG delivered (kg)",
    "days_in_period": "Period days",
    "delivery_gap_days": "Delivery gap (days)",
    "stove_condition_score": "Stove condition",
    "regulator_condition_score": "Regulator condition",
    "hose_condition_score": "Hose condition",
    "cylinder_change_count": "Cylinder changes",
    "cooking_hours_day": "Cooking hours/day",
    "storage_condition_score": "Storage condition",
    "equipment_age_years": "Equipment age (years)",
    "reported_odor_events": "Reported odor events",
}


def validate_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in REQUIRED_COLUMNS if c not in df.columns]


def _clip(value: pd.Series | float, low: float, high: float) -> pd.Series | float:
    return np.clip(value, low, high)


def _normalize_inverse_score(series: pd.Series, low: float = 0.0, high: float = 100.0) -> pd.Series:
    """Map a positive condition score to risk pressure: low condition -> high risk."""
    s = pd.to_numeric(series, errors="coerce").fillna(0.0)
    return _clip(high - s, low, high)


def classify(score: float) -> str:
    score = float(score)
    if score >= 75:
        return "Critical"
    if score >= 55:
        return "High"
    if score >= 35:
        return "Moderate"
    return "Low"


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denominator = pd.to_numeric(denominator, errors="coerce").replace(0, np.nan)
    numerator = pd.to_numeric(numerator, errors="coerce")
    return (numerator / denominator).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def add_derived_metrics(df: pd.DataFrame) -> pd.DataFrame:
    missing = validate_columns(df)
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))

    out = df.copy()
    numeric_cols = [c for c in REQUIRED_COLUMNS if c not in {"kitchen_id", "community"}]
    for col in numeric_cols:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)

    out["lpg_per_meal"] = _safe_ratio(out["lpg_kg_used"], out["meals_served"])
    out["delivery_utilization_pct"] = _safe_ratio(out["lpg_delivered_kg"], out["lpg_kg_used"]) * 100
    out["lpg_balance_kg"] = out["lpg_delivered_kg"] - out["lpg_kg_used"]

    meal_rate = _safe_ratio(out["meals_served"], out["days_in_period"])
    out["meals_per_day"] = meal_rate

    benchmark = max(float(out["lpg_per_meal"].replace([np.inf, -np.inf], np.nan).median()), 0.02)
    out["consumption_pressure_score"] = _clip((out["lpg_per_meal"] / benchmark) * 50, 0, 100)

    condition_risk = (
        _normalize_inverse_score(out["stove_condition_score"])
        + _normalize_inverse_score(out["regulator_condition_score"])
        + _normalize_inverse_score(out["hose_condition_score"])
        + _normalize_inverse_score(out["storage_condition_score"])
    ) / 4
    age_pressure = _clip(out["equipment_age_years"] / 12 * 100, 0, 100)
    out["equipment_condition_pressure_score"] = _clip(condition_risk * 0.80 + age_pressure * 0.20, 0, 100)

    shortage_ratio = _safe_ratio((out["lpg_kg_used"] - out["lpg_delivered_kg"]).clip(lower=0), out["lpg_delivered_kg"]) * 100
    delivery_pressure = (
        _clip(out["delivery_gap_days"] / 14 * 100, 0, 100) * 0.65
        + _clip(shortage_ratio, 0, 100) * 0.35
    )
    out["supply_pressure_score"] = _clip(delivery_pressure, 0, 100)

    usage_pressure = (
        _clip(out["cooking_hours_day"] / 10 * 100, 0, 100)
        + _clip(out["cylinder_change_count"] / 8 * 100, 0, 100)
        + _clip(out["reported_odor_events"] / 5 * 100, 0, 100)
    ) / 3
    out["usage_signal_score"] = _clip(usage_pressure, 0, 100)

    # Transparent screening model; weights sum to 1.0.
    out["gas_anomaly_screening_score"] = _clip(
        out["consumption_pressure_score"] * 0.35
        + out["equipment_condition_pressure_score"] * 0.30
        + out["supply_pressure_score"] * 0.15
        + out["usage_signal_score"] * 0.20,
        0,
        100,
    ).round(1)
    out["screening_classification"] = out["gas_anomaly_screening_score"].map(classify)

    driver_scores = pd.DataFrame(
        {
            "Consumption": out["consumption_pressure_score"],
            "Equipment": out["equipment_condition_pressure_score"],
            "Supply": out["supply_pressure_score"],
            "Usage signals": out["usage_signal_score"],
        },
        index=out.index,
    )
    out["dominant_driver"] = driver_scores.idxmax(axis=1)
    out["review_priority"] = np.select(
        [
            out["gas_anomaly_screening_score"] >= 75,
            out["gas_anomaly_screening_score"] >= 55,
            out["gas_anomaly_screening_score"] >= 35,
        ],
        ["Immediate review", "Priority review", "Routine review"],
        default="Monitor",
    )

    out["odor_flag"] = out["reported_odor_events"] > 0
    out["supply_flag"] = (out["delivery_gap_days"] >= 10) | (out["lpg_balance_kg"] < -5)
    out["equipment_flag"] = out["equipment_condition_pressure_score"] >= 60
    out["efficiency_flag"] = out["lpg_per_meal"] > max(float(out["lpg_per_meal"].median()), 0.02) * 1.25
    return out


def scenario_score(
    row: pd.Series,
    usage_multiplier: float = 1.0,
    equipment_condition_delta: float = 0.0,
    delivery_gap_delta: float = 0.0,
    odor_events_delta: int = 0,
    benchmark_lpg_per_meal: float | None = None,
) -> float:
    temp = row.copy()
    temp["lpg_kg_used"] = max(float(row["lpg_kg_used"]) * usage_multiplier, 0.0)
    for key in ["stove_condition_score", "regulator_condition_score", "hose_condition_score", "storage_condition_score"]:
        temp[key] = float(np.clip(float(row[key]) + equipment_condition_delta, 0, 100))
    temp["delivery_gap_days"] = max(float(row["delivery_gap_days"]) + delivery_gap_delta, 0.0)
    temp["reported_odor_events"] = max(float(row["reported_odor_events"]) + odor_events_delta, 0.0)
    temp_df = pd.DataFrame([temp])
    scored = add_derived_metrics(temp_df)
    if benchmark_lpg_per_meal is not None:
        benchmark = max(float(benchmark_lpg_per_meal), 0.02)
        scored["consumption_pressure_score"] = _clip((scored["lpg_per_meal"] / benchmark) * 50, 0, 100)
        scored["gas_anomaly_screening_score"] = _clip(
            scored["consumption_pressure_score"] * 0.35
            + scored["equipment_condition_pressure_score"] * 0.30
            + scored["supply_pressure_score"] * 0.15
            + scored["usage_signal_score"] * 0.20,
            0,
            100,
        ).round(1)
    return float(scored["gas_anomaly_screening_score"].iloc[0])


def driver_summary(df: pd.DataFrame) -> pd.DataFrame:
    metrics = {
        "Consumption pressure": float(df["consumption_pressure_score"].mean()),
        "Equipment condition pressure": float(df["equipment_condition_pressure_score"].mean()),
        "Supply pressure": float(df["supply_pressure_score"].mean()),
        "Usage signals": float(df["usage_signal_score"].mean()),
    }
    return pd.DataFrame({"Driver": list(metrics), "Average score": list(metrics.values())}).sort_values(
        "Average score", ascending=False
    ).reset_index(drop=True)


def markdown_table(df: pd.DataFrame, max_rows: int = 15) -> str:
    """Dependency-free Markdown table renderer."""
    if df.empty:
        return "_No rows available._"
    view = df.head(max_rows).copy()
    headers = [str(c) for c in view.columns]
    rows = [[str(v).replace("|", "\\|").replace("\n", " ") for v in row] for row in view.astype(object).values]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    lines.extend("| " + " | ".join(r) + " |" for r in rows)
    return "\n".join(lines)


def make_summary(df: pd.DataFrame) -> dict[str, float | int | str]:
    return {
        "records": int(len(df)),
        "communities": int(df["community"].nunique()),
        "avg_score": round(float(df["gas_anomaly_screening_score"].mean()), 1),
        "priority_count": int((df["review_priority"] != "Monitor").sum()),
        "odor_flags": int(df["odor_flag"].sum()),
        "supply_flags": int(df["supply_flag"].sum()),
        "equipment_flags": int(df["equipment_flag"].sum()),
        "top_driver": str(df["dominant_driver"].mode().iloc[0]) if not df.empty else "None",
    }
