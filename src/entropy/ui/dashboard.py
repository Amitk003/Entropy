"""Streamlit dashboard for Project Entropy - Chaos Engineering Command Center."""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import streamlit as st
import httpx

from entropy.evaluator import EvaluatorAgent
from entropy.models import ExperimentPostmortem


SIGNOZ_UI_URL = os.environ.get("SIGNOZ_UI_URL", "http://localhost:8080")
CHAOS_FAULTS = ["timeout", "rate-limit", "semantic-corruption", "memory-poisoning"]
TRACE_DIR = Path(os.environ.get("ENTROPY_RESULTS_DIR", "reports"))
TRACE_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(
    page_title="Project Entropy - Command Center",
    page_icon="⚡",
    layout="wide",
)


async def _run_experiment(input_text: str, fault: str | None) -> dict:
    """Run an experiment via the CLI and return the result."""
    env = os.environ.copy()
    env["CHAOS_ENABLED"] = "true" if fault else "false"
    if fault:
        env["CHAOS_FAULT_TYPE"] = fault

    cmd = [sys.executable, "-m", "entropy.cli", "run", "--mode", "chaos" if fault else "baseline"]
    if fault:
        cmd.extend(["--fault", fault])

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    output = stdout.decode().strip()
    trace_id = None
    for line in output.split("\n"):
        if "Trace ID:" in line:
            trace_id = line.split("Trace ID:")[-1].strip()
    return {"output": output, "trace_id": trace_id, "error": stderr.decode().strip()}


async def _evaluate(trace_id: str) -> ExperimentPostmortem | None:
    """Evaluate a trace and return the post-mortem report."""
    evaluator = EvaluatorAgent()
    try:
        report = await evaluator.evaluate(trace_id)
        report_path = TRACE_DIR / f"postmortem-{trace_id}.json"
        report_path.write_text(report.model_dump_json(indent=2))
        return report
    except Exception as exc:
        st.error(f"Evaluation failed: {exc}")
        return None
    finally:
        await evaluator.backend.close()


def _render_report(report: ExperimentPostmortem):
    """Render a post-mortem report in the Streamlit UI."""
    col1, col2, col3 = st.columns(3)
    outcome_colors = {
        "full-recovery": "green",
        "graceful-degradation": "orange",
        "partial-completion": "yellow",
        "silent-failure": "red",
    }
    color = outcome_colors.get(report.outcome.value, "grey")

    col1.metric("Survival Score", f"{report.survival_score:.2f}")
    col2.metric("Confidence Score", f"{report.confidence_score:.2f}")
    col3.markdown(
        f"**Outcome:** <span style='color:{color}'>{report.outcome.value}</span>",
        unsafe_allow_html=True,
    )

    st.markdown("### Details")
    st.write(f"**Injected Fault:** {report.injected_fault_type.value}")
    st.write(f"**Recovery Action:** {report.target_recovery_action}")
    if report.evidence_spans:
        st.write(f"**Evidence Spans:** {', '.join(report.evidence_spans[:10])}")
    st.markdown("### Summary")
    st.write(report.summary)


st.title("Project Entropy - Chaos Command Center")
st.markdown("Control chaos experiments, view traces, and read automated post-mortem reports.")

tab_baseline, tab_chaos, tab_results, tab_dashboard = st.tabs(
    ["Baseline Run", "Chaos Experiment", "Post-Mortem Reports", "SigNoz Dashboard"]
)

with tab_baseline:
    st.header("Run a Baseline Test")
    st.markdown("Run the agent without any fault injection to establish a baseline trace.")

    input_text = st.text_input(
        "Agent Input",
        value="Lookup customer C001",
        key="baseline_input",
    )

    if st.button("Run Baseline", type="primary", key="run_baseline"):
        with st.spinner("Running baseline experiment..."):
            result = asyncio.run(_run_experiment(input_text, None))
        st.code(result["output"])
        if result["error"]:
            st.error(f"Stderr: {result['error']}")
        if result["trace_id"]:
            st.session_state["last_trace_id"] = result["trace_id"]
            st.success(f"Trace generated: `{result['trace_id']}`")
            st.link_button(
                "View in SigNoz",
                f"{SIGNOZ_UI_URL}/trace/{result['trace_id']}",
            )

with tab_chaos:
    st.header("Trigger a Chaos Experiment")
    st.markdown("Inject a fault into the agent and evaluate its resilience.")

    chaos_input = st.text_input(
        "Agent Input",
        value="Lookup customer C001",
        key="chaos_input",
    )

    selected_fault = st.selectbox("Fault Type", CHAOS_FAULTS)
    auto_evaluate = st.checkbox("Auto-evaluate after run", value=True)

    if st.button("Inject Chaos", type="primary", key="run_chaos"):
        with st.spinner(f"Injecting `{selected_fault}` fault..."):
            result = asyncio.run(_run_experiment(chaos_input, selected_fault))
        st.code(result["output"])
        if result["error"]:
            st.error(f"Stderr: {result['error']}")

        if result["trace_id"]:
            st.session_state["last_trace_id"] = result["trace_id"]
            st.success(f"Trace generated: `{result['trace_id']}`")
            st.link_button(
                "View in SigNoz",
                f"{SIGNOZ_UI_URL}/trace/{result['trace_id']}",
            )

            if auto_evaluate:
                with st.spinner("Evaluating trace via LLM-as-a-Judge..."):
                    report = asyncio.run(_evaluate(result["trace_id"]))
                if report:
                    st.session_state["last_report"] = report
                    st.markdown("---")
                    _render_report(report)

with tab_results:
    st.header("Post-Mortem Reports")
    st.markdown("View previously generated reports and compare results.")

    saved_reports = sorted(TRACE_DIR.glob("postmortem-*.json"), reverse=True)
    if saved_reports:
        selected = st.selectbox(
            "Select a report",
            saved_reports,
            format_func=lambda p: p.stem.replace("postmortem-", ""),
        )
        if selected:
            data = json.loads(selected.read_text())
            report = ExperimentPostmortem.model_validate(data)
            _render_report(report)
    else:
        st.info("No saved reports yet. Run a chaos experiment to generate one.")

    if "last_report" in st.session_state:
        st.markdown("---")
        st.markdown("### Last Run Report")
        _render_report(st.session_state["last_report"])

with tab_dashboard:
    st.header("SigNoz Command Center Dashboard")
    st.markdown(
        "The full dashboard is hosted in SigNoz. Import the dashboard config from "
        "`dashboards/chaos_command_center.json` to recreate it."
    )
    st.link_button("Open SigNoz Dashboard", f"{SIGNOZ_UI_URL}/dashboard")

    st.markdown("### Quick View: Last 5 Experiment Outcomes")
    recent = sorted(TRACE_DIR.glob("postmortem-*.json"), reverse=True)[:5]
    if recent:
        rows = []
        for p in recent:
            data = json.loads(p.read_text())
            rows.append({
                "Trace": p.stem.replace("postmortem-", "")[:12] + "...",
                "Fault": data.get("injected_fault_type", ""),
                "Survival": f"{data.get('survival_score', 0):.2f}",
                "Confidence": f"{data.get('confidence_score', 0):.2f}",
                "Outcome": data.get("outcome", ""),
            })
        st.dataframe(rows, use_container_width=True)
    else:
        st.info("No reports yet.")
