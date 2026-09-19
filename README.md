# Community Kitchen Gas-Consumption Anomaly Monitor

A 100% local-first Streamlit dashboard for screening possible LPG-use anomalies, equipment-condition pressure, supply issues, and unusual kitchen-consumption signals using locally supplied operational data.

## Features
- Explainable 0–100 screening score with Low / Moderate / High / Critical classification.
- LPG consumption-per-meal and cooking-intensity analytics.
- Stove, regulator, hose, and storage-condition assessment.
- Delivery-gap and LPG-balance analysis.
- Odor-event and cylinder-change signals.
- Priority queue, community profiles, scenario lab, and report-ready exports.
- CSV-only local workflow; no external API is required.
- Local SVG assets are bundled for dashboard presentation.

## Run
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m pytest tests/ -q
streamlit run app.py
```

## Data
Use `data/sample_community_kitchen_gas.csv` for demonstration or `data/community_kitchen_gas_template.csv` as a blank starting point.

The screening model is intentionally transparent and is not a gas-leak detector, safety certification, engineering inspection, or emergency-response system. Suspected gas leaks or unsafe equipment should be handled using applicable local emergency and safety procedures by qualified personnel.
