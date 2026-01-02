"""
Main pipeline orchestration for Behavior2Build.

Implements the complete pipeline flow using Prefect for orchestration.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from prefect import flow, get_run_logger
from pydantic import BaseModel, Field

from ..core.config import get_config
from ..core.logging import bind_context, setup_logging
from ..core.types import PipelineRun, StageResult, StageStatus
from ..models.apk import APKMetadata
from ..models.behavior import BehaviorModel
from ..models.codegen import AndroidProject
from ..models.spec import ArchitectureSpec, BehavioralSpec
from ..storage import LocalStorageBackend

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


class PipelineConfig(BaseModel):
    """Configuration for a pipeline run."""

    apk_path: Path = Field(description="Path to input APK")
    app_name: str = Field(description="Name for the generated application")
    package_name: str = Field(description="Package name for generated code")
    play_store_url: str | None = Field(default=None)
    screenshots: list[Path] = Field(default_factory=list)
    exploration_time: int = Field(default=300, description="Dynamic analysis time in seconds")
    skip_dynamic_analysis: bool = Field(default=False, description="Skip emulator-based analysis")


class PipelineResult(BaseModel):
    """Result of a complete pipeline run."""

    run_id: str
    success: bool
    started_at: datetime
    completed_at: datetime

    # Outputs
    apk_metadata: APKMetadata | None = None
    behavior_model: BehaviorModel | None = None
    behavioral_spec: BehavioralSpec | None = None
    architecture_spec: ArchitectureSpec | None = None
    generated_project: AndroidProject | None = None

    # Reports
    parity_score: float = 0.0
    parity_passed: bool = False
    compliance_passed: bool = False

    # Output location
    output_directory: str = ""

    # Errors
    error: str | None = None
    failed_stage: str | None = None


@flow(
    name="behavior2build",
    description="Complete APK to greenfield app pipeline",
    version="1.0.0",
    retries=0,
)
async def behavior2build_flow(config: PipelineConfig) -> PipelineResult:
    """Execute the complete Behavior2Build pipeline.

    This flow orchestrates all pipeline stages from APK ingestion
    to verified code generation.

    Args:
        config: Pipeline configuration

    Returns:
        PipelineResult with all outputs and reports
    """
    run_id = str(uuid.uuid4())[:8]
    logger = get_run_logger()
    started_at = datetime.utcnow()

    logger.info(f"Starting Behavior2Build pipeline. Run ID: {run_id}")
    logger.info(f"APK: {config.apk_path}")
    logger.info(f"App name: {config.app_name}")

    try:
        # Stage 1: Ingestion
        logger.info("Stage 1/8: Ingesting APK")
        ingestion_output = await ingest_apk(
            apk_path=config.apk_path,
            play_store_url=config.play_store_url,
            screenshots=config.screenshots,
        )
        apk_metadata = ingestion_output.apk_metadata

        # Stage 2: Static Analysis
        logger.info("Stage 2/8: Running static analysis")
        static_output = await run_static_analysis(
            apk_path=ingestion_output.normalized_apk_path,
            apk_metadata=apk_metadata,
        )

        # Update metadata with manifest from static analysis
        apk_metadata.manifest = static_output.manifest
        apk_metadata.detected_frameworks = static_output.detected_frameworks

        # Stage 3: Dynamic Analysis
        logger.info("Stage 3/8: Running dynamic analysis")
        if config.skip_dynamic_analysis:
            logger.warning("Skipping dynamic analysis (mock mode)")
            from ..services.dynamic_analysis.service import DynamicAnalysisOutput
            dynamic_output = DynamicAnalysisOutput(
                screens=[],
                transitions=[],
                exploration_coverage=0.0,
            )
        else:
            dynamic_output = await run_dynamic_analysis(
                apk_path=ingestion_output.normalized_apk_path,
                apk_metadata=apk_metadata,
                exploration_time=config.exploration_time,
            )

        # Stage 4: Build Behavior Model
        logger.info("Stage 4/8: Building behavior model")
        behavior_output = await build_behavior_model(
            apk_metadata=apk_metadata,
            static_analysis=static_output,
            dynamic_analysis=dynamic_output,
            run_id=run_id,
        )
        behavior_model = behavior_output.behavior_model

        # Stage 5: Generate Specification
        logger.info("Stage 5/8: Generating specification")
        spec_output = await generate_spec(
            behavior_model=behavior_model,
            app_name=config.app_name,
            run_id=run_id,
        )
        behavioral_spec = spec_output.behavioral_spec

        # Stage 6: Synthesize Architecture
        logger.info("Stage 6/8: Synthesizing architecture")
        arch_output = await synthesize_architecture(
            behavioral_spec=behavioral_spec,
            run_id=run_id,
        )
        architecture_spec = arch_output.architecture_spec

        # Stage 7: Generate Code
        logger.info("Stage 7/8: Generating code")
        codegen_output = await generate_code(
            behavioral_spec=behavioral_spec,
            architecture_spec=architecture_spec,
            package_name=config.package_name,
            run_id=run_id,
        )
        generated_project = codegen_output.project

        # Stage 8: Verification
        logger.info("Stage 8/8: Verifying parity")
        verification_output = await verify_parity(
            behavior_model=behavior_model,
            generated_project=generated_project,
            run_id=run_id,
        )

        # Compliance Check
        logger.info("Running compliance check")
        generated_files = {}
        for files in generated_project.source_files.values():
            for f in files:
                if f.raw_content:
                    generated_files[f.full_path] = f.raw_content

        compliance_output = await check_compliance(
            run_id=run_id,
            apk_hash=apk_metadata.provenance.sha256_hash,
            generated_files=generated_files,
        )

        # Build result
        completed_at = datetime.utcnow()
        result = PipelineResult(
            run_id=run_id,
            success=True,
            started_at=started_at,
            completed_at=completed_at,
            apk_metadata=apk_metadata,
            behavior_model=behavior_model,
            behavioral_spec=behavioral_spec,
            architecture_spec=architecture_spec,
            generated_project=generated_project,
            parity_score=verification_output.parity_report.overall_parity_score,
            parity_passed=verification_output.parity_report.passed,
            compliance_passed=compliance_output.compliance_report.passed,
            output_directory=codegen_output.output_directory,
        )

        duration = (completed_at - started_at).total_seconds()
        logger.info(f"Pipeline completed successfully in {duration:.1f}s")
        logger.info(f"Output directory: {codegen_output.output_directory}")
        logger.info(f"Parity score: {result.parity_score:.1%}")
        logger.info(f"Compliance: {'PASSED' if result.compliance_passed else 'FAILED'}")

        return result

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        return PipelineResult(
            run_id=run_id,
            success=False,
            started_at=started_at,
            completed_at=datetime.utcnow(),
            error=str(e),
        )


class Behavior2BuildPipeline:
    """High-level pipeline interface for programmatic use."""

    def __init__(self) -> None:
        """Initialize the pipeline."""
        self.config = get_config()
        setup_logging(self.config)

    async def run(
        self,
        apk_path: Path,
        app_name: str,
        package_name: str,
        play_store_url: str | None = None,
        screenshots: list[Path] | None = None,
        exploration_time: int = 300,
        skip_dynamic_analysis: bool = False,
    ) -> PipelineResult:
        """Run the complete pipeline.

        Args:
            apk_path: Path to input APK
            app_name: Name for generated application
            package_name: Package name for generated code
            play_store_url: Optional Play Store URL
            screenshots: Optional list of screenshot paths
            exploration_time: Dynamic analysis time in seconds
            skip_dynamic_analysis: Skip emulator-based analysis

        Returns:
            PipelineResult with all outputs
        """
        config = PipelineConfig(
            apk_path=apk_path,
            app_name=app_name,
            package_name=package_name,
            play_store_url=play_store_url,
            screenshots=screenshots or [],
            exploration_time=exploration_time,
            skip_dynamic_analysis=skip_dynamic_analysis,
        )

        return await behavior2build_flow(config)


async def run_pipeline(
    apk_path: str | Path,
    app_name: str,
    package_name: str,
    **kwargs: Any,
) -> PipelineResult:
    """Convenience function to run the pipeline.

    Args:
        apk_path: Path to input APK
        app_name: Name for generated application
        package_name: Package name for generated code
        **kwargs: Additional configuration options

    Returns:
        PipelineResult with all outputs
    """
    pipeline = Behavior2BuildPipeline()
    return await pipeline.run(
        apk_path=Path(apk_path),
        app_name=app_name,
        package_name=package_name,
        **kwargs,
    )
