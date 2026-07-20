# Dashboard Guide

Project Entropy has two dashboards: a **SigNoz Command Center** for live observability data and a **Streamlit Operator UI** for running experiments and viewing post-mortem reports.

## SigNoz Command Center Dashboard

The SigNoz dashboard is exported as `dashboards/chaos_command_center.json`. Import it from the SigNoz UI under Dashboards -> Import.

### Panels

| Panel | Type | What It Shows |
|-------|------|---------------|
| **Chaos Survival Rate** | Gauge | Weighted survival score (0.0-1.0) across all experiments |
| **P95 Latency by Fault Type** | Time Series | 95th percentile span duration grouped by fault type |
| **Token Cost Inefficiency** | Bar Chart | Total token usage by survival score tier |
| **Fault Distribution** | Pie Chart | Breakdown of injected fault types |
| **Error Message Analysis** | Table | Most frequent error messages from failed spans |
| **Evaluator Confidence Trend** | Time Series | Confidence scores over time to detect trace quality issues |

### Weighted Survival Score

Outcomes are weighted to reward graceful degradation over silent failure:

| Outcome | Weight | Meaning |
|---------|--------|---------|
| Full recovery | 1.0 | Agent retried and completed correctly |
| Graceful degradation | 0.7 | Agent logged the error and returned a fallback |
| Partial completion | 0.4 | Agent produced a degraded but non-hallucinated output |
| Silent failure | 0.0 | Agent accepted corrupted data and produced wrong output |

Aggregate score = sum(weight * count) / total experiments.

## Streamlit Operator UI

The Streamlit UI (`src/entropy/ui/dashboard.py`) provides a control panel for:

- **Baseline Run** - Run the agent without faults to capture a clean trace
- **Chaos Experiment** - Inject a specific fault and auto-evaluate the result
- **Post-Mortem Reports** - Browse and compare saved reports
- **SigNoz Dashboard** - Quick link to the live SigNoz dashboard

### Launch

```bash
streamlit run src/entropy/ui/dashboard.py
```

Configure with environment variables:

- `SIGNOZ_UI_URL` - URL of the SigNoz UI (default: `http://localhost:8080`)
- `ENTROPY_RESULTS_DIR` - Directory for saved reports (default: `reports/`)
