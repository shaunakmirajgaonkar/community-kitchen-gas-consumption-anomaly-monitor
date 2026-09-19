import pandas as pd

from analytics import REQUIRED_COLUMNS, add_derived_metrics, classify, markdown_table, scenario_score


def make_row():
    return {
        "kitchen_id": "T-001", "community": "Test", "lpg_kg_used": 100,
        "meals_served": 2000, "lpg_delivered_kg": 110, "days_in_period": 30,
        "delivery_gap_days": 3, "stove_condition_score": 90, "regulator_condition_score": 90,
        "hose_condition_score": 90, "cylinder_change_count": 4, "cooking_hours_day": 7,
        "storage_condition_score": 90, "equipment_age_years": 2, "reported_odor_events": 0,
    }


def test_required_columns_count():
    assert len(REQUIRED_COLUMNS) == 15


def test_classify_thresholds():
    assert classify(0) == "Low"
    assert classify(35) == "Moderate"
    assert classify(55) == "High"
    assert classify(75) == "Critical"


def test_metrics_are_created_and_bounded():
    df = add_derived_metrics(pd.DataFrame([make_row()]))
    cols = ["gas_anomaly_screening_score", "consumption_pressure_score", "equipment_condition_pressure_score", "supply_pressure_score", "usage_signal_score"]
    assert all(c in df.columns for c in cols)
    assert df[cols].ge(0).all().all()
    assert df[cols].le(100).all().all()


def test_scenario_changes_with_shared_benchmark_and_markdown_is_dependency_free():
    row = pd.Series(make_row())
    baseline = scenario_score(row, benchmark_lpg_per_meal=0.06)
    stressed = scenario_score(
        row,
        usage_multiplier=1.3,
        equipment_condition_delta=-20,
        delivery_gap_delta=8,
        odor_events_delta=1,
        benchmark_lpg_per_meal=0.06,
    )
    assert stressed > baseline
    text = markdown_table(pd.DataFrame([{"Kitchen": "T-001", "Score": round(stressed, 1)}]))
    assert "| Kitchen | Score |" in text


def test_app_has_no_tabulate_dependency_and_equipment_columns_are_explicit():
    from pathlib import Path

    app_text = (Path(__file__).parents[1] / "app.py").read_text()
    assert ".to_markdown(" not in app_text
    assert "view[\"stove_condition_score\"]" in app_text
    assert "view[\"regulator_condition_score\"]" in app_text
    assert "view[\"hose_condition_score\"]" in app_text
    assert "view[\"storage_condition_score\"]" in app_text
