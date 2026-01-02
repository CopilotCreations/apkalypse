"""Orchestration module for APKalypse."""

from .pipeline import APKalypsePipeline, run_pipeline
from .tasks import (
    ingest_apk,
    run_static_analysis,
    run_dynamic_analysis,
    build_behavior_model,
    generate_spec,
    synthesize_architecture,
    generate_code,
    verify_parity,
    check_compliance,
)

__all__ = [
    "APKalypsePipeline",
    "run_pipeline",
    "ingest_apk",
    "run_static_analysis",
    "run_dynamic_analysis",
    "build_behavior_model",
    "generate_spec",
    "synthesize_architecture",
    "generate_code",
    "verify_parity",
    "check_compliance",
]
