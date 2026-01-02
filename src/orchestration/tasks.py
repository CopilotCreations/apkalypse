"""
Prefect tasks for the APKalypse pipeline.

Each task wraps a service operation with proper error handling,
logging, and result persistence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from prefect import task
from prefect.logging import get_run_logger

from ..core.types import ServiceResult
from ..models.apk import APKMetadata
from ..models.behavior import BehaviorModel
from ..models.codegen import AndroidProject
from ..models.spec import ArchitectureSpec, BehavioralSpec
from ..services.ingestion import IngestionService
from ..services.ingestion.service import IngestionInput, IngestionOutput
from ..services.static_analysis import StaticAnalysisService
from ..services.static_analysis.service import StaticAnalysisInput, StaticAnalysisOutput
from ..services.dynamic_analysis import DynamicAnalysisService
from ..services.dynamic_analysis.service import DynamicAnalysisInput, DynamicAnalysisOutput
from ..services.behavior_model import BehaviorModelService
from ..services.behavior_model.service import BehaviorModelInput, BehaviorModelOutput
from ..services.spec_generation import SpecGenerationService
from ..services.spec_generation.service import SpecGenerationInput, SpecGenerationOutput
from ..services.architecture import ArchitectureService
from ..services.architecture.service import ArchitectureInput as ArchServiceInput, ArchitectureOutput
from ..services.codegen import CodegenService
from ..services.codegen.service import CodegenInput, CodegenOutput
from ..services.verification import VerificationService
from ..services.verification.service import VerificationInput, VerificationOutput
from ..services.compliance import ComplianceGuard
from ..services.compliance.service import ComplianceInput, ComplianceOutput
from ..storage import LocalStorageBackend


def get_storage() -> LocalStorageBackend:
    """Get storage backend."""
    from ..core.config import get_config
    config = get_config()
    return LocalStorageBackend(config.storage.base_path)


@task(
    name="ingest_apk",
    description="Ingest APK and extract metadata",
    retries=2,
    retry_delay_seconds=5,
)
async def ingest_apk(
    apk_path: Path,
    play_store_url: str | None = None,
    screenshots: list[Path] | None = None,
) -> IngestionOutput:
    """Ingest an APK file.

    Args:
        apk_path: Path to APK file
        play_store_url: Optional Play Store URL
        screenshots: Optional list of screenshot paths

    Returns:
        IngestionOutput with metadata and storage keys
    """
    logger = get_run_logger()
    logger.info(f"Ingesting APK: {apk_path}")

    storage = get_storage()
    service = IngestionService(storage)

    input_data = IngestionInput(
        apk_path=apk_path,
        play_store_url=play_store_url,
        screenshots=screenshots or [],
    )

    result = await service.ingest(input_data)

    if not result.success:
        raise RuntimeError(f"Ingestion failed: {result.error}")

    logger.info(f"Ingestion complete. APK hash: {result.data.apk_metadata.provenance.sha256_hash[:16]}")
    return result.data


@task(
    name="run_static_analysis",
    description="Run static analysis on APK",
    retries=1,
)
async def run_static_analysis(
    apk_path: str,
    apk_metadata: APKMetadata,
) -> StaticAnalysisOutput:
    """Run static analysis on an APK.

    Args:
        apk_path: Storage key for APK
        apk_metadata: APK metadata from ingestion

    Returns:
        StaticAnalysisOutput with manifest and layout info
    """
    logger = get_run_logger()
    logger.info("Running static analysis")

    storage = get_storage()
    service = StaticAnalysisService(storage)

    input_data = StaticAnalysisInput(
        apk_path=apk_path,
        apk_metadata=apk_metadata,
    )

    result = await service.analyze(input_data)

    if not result.success:
        raise RuntimeError(f"Static analysis failed: {result.error}")

    logger.info(f"Static analysis complete. Found {len(result.data.manifest.activities)} activities")
    return result.data


@task(
    name="run_dynamic_analysis",
    description="Run dynamic analysis with emulator",
    retries=1,
    timeout_seconds=600,
)
async def run_dynamic_analysis(
    apk_path: str,
    apk_metadata: APKMetadata,
    exploration_time: int = 300,
) -> DynamicAnalysisOutput:
    """Run dynamic analysis on an APK.

    Args:
        apk_path: Storage key for APK
        apk_metadata: APK metadata (with manifest from static analysis)
        exploration_time: Max exploration time in seconds

    Returns:
        DynamicAnalysisOutput with screens and transitions
    """
    logger = get_run_logger()
    logger.info("Running dynamic analysis")

    storage = get_storage()
    service = DynamicAnalysisService(storage)

    input_data = DynamicAnalysisInput(
        apk_path=apk_path,
        apk_metadata=apk_metadata,
        exploration_time_seconds=exploration_time,
    )

    result = await service.analyze(input_data)

    if not result.success:
        raise RuntimeError(f"Dynamic analysis failed: {result.error}")

    if result.warnings:
        for warning in result.warnings:
            logger.warning(warning)

    logger.info(f"Dynamic analysis complete. Found {len(result.data.screens)} screens")
    return result.data


@task(
    name="build_behavior_model",
    description="Build canonical behavior model",
)
async def build_behavior_model(
    apk_metadata: APKMetadata,
    static_analysis: StaticAnalysisOutput,
    dynamic_analysis: DynamicAnalysisOutput,
    run_id: str,
) -> BehaviorModelOutput:
    """Build the behavioral model.

    Args:
        apk_metadata: APK metadata
        static_analysis: Static analysis results
        dynamic_analysis: Dynamic analysis results
        run_id: Pipeline run ID

    Returns:
        BehaviorModelOutput with the canonical model
    """
    logger = get_run_logger()
    logger.info("Building behavior model")

    storage = get_storage()
    service = BehaviorModelService(storage)

    input_data = BehaviorModelInput(
        apk_metadata=apk_metadata,
        static_analysis=static_analysis,
        dynamic_analysis=dynamic_analysis,
        run_id=run_id,
    )

    result = await service.build(input_data)

    if not result.success:
        raise RuntimeError(f"Behavior model building failed: {result.error}")

    model = result.data.behavior_model
    logger.info(f"Behavior model built. {model.total_screens} screens, {model.total_transitions} transitions")
    return result.data


@task(
    name="generate_spec",
    description="Generate product specification",
)
async def generate_spec(
    behavior_model: BehaviorModel,
    app_name: str,
    run_id: str,
) -> SpecGenerationOutput:
    """Generate product specification.

    Args:
        behavior_model: Canonical behavior model
        app_name: Name for the generated app
        run_id: Pipeline run ID

    Returns:
        SpecGenerationOutput with behavioral spec
    """
    logger = get_run_logger()
    logger.info("Generating specification")

    storage = get_storage()
    service = SpecGenerationService(storage)

    input_data = SpecGenerationInput(
        behavior_model=behavior_model,
        app_name=app_name,
        run_id=run_id,
    )

    result = await service.generate(input_data)

    if not result.success:
        raise RuntimeError(f"Spec generation failed: {result.error}")

    spec = result.data.behavioral_spec
    logger.info(f"Specification generated. {len(spec.functional_requirements)} requirements")
    return result.data


@task(
    name="synthesize_architecture",
    description="Synthesize technical architecture",
)
async def synthesize_architecture(
    behavioral_spec: BehavioralSpec,
    run_id: str,
) -> ArchitectureOutput:
    """Synthesize technical architecture.

    Args:
        behavioral_spec: Behavioral specification
        run_id: Pipeline run ID

    Returns:
        ArchitectureOutput with architecture spec
    """
    logger = get_run_logger()
    logger.info("Synthesizing architecture")

    storage = get_storage()
    service = ArchitectureService(storage)

    input_data = ArchServiceInput(
        behavioral_spec=behavioral_spec,
        run_id=run_id,
    )

    result = await service.synthesize(input_data)

    if not result.success:
        raise RuntimeError(f"Architecture synthesis failed: {result.error}")

    arch = result.data.architecture_spec
    logger.info(f"Architecture synthesized. {len(arch.modules)} modules, {len(arch.adrs)} ADRs")
    return result.data


@task(
    name="generate_code",
    description="Generate Android application code",
)
async def generate_code(
    behavioral_spec: BehavioralSpec,
    architecture_spec: ArchitectureSpec,
    package_name: str,
    run_id: str,
) -> CodegenOutput:
    """Generate Android application code.

    Args:
        behavioral_spec: Behavioral specification
        architecture_spec: Architecture specification
        package_name: Package name for generated code
        run_id: Pipeline run ID

    Returns:
        CodegenOutput with generated project
    """
    logger = get_run_logger()
    logger.info("Generating code")

    storage = get_storage()
    service = CodegenService(storage)

    input_data = CodegenInput(
        behavioral_spec=behavioral_spec,
        architecture_spec=architecture_spec,
        package_name=package_name,
        run_id=run_id,
    )

    result = await service.generate(input_data)

    if not result.success:
        raise RuntimeError(f"Code generation failed: {result.error}")

    project = result.data.project
    logger.info(f"Code generated. {len(project.modules)} modules at {result.data.output_directory}")
    return result.data


@task(
    name="verify_parity",
    description="Verify behavioral parity",
)
async def verify_parity(
    behavior_model: BehaviorModel,
    generated_project: AndroidProject,
    run_id: str,
) -> VerificationOutput:
    """Verify behavioral parity.

    Args:
        behavior_model: Original behavior model
        generated_project: Generated Android project
        run_id: Pipeline run ID

    Returns:
        VerificationOutput with parity report
    """
    logger = get_run_logger()
    logger.info("Verifying parity")

    storage = get_storage()
    service = VerificationService(storage)

    input_data = VerificationInput(
        behavior_model=behavior_model,
        generated_project=generated_project,
        run_id=run_id,
    )

    result = await service.verify(input_data)

    if not result.success:
        raise RuntimeError(f"Verification failed: {result.error}")

    report = result.data.parity_report
    logger.info(f"Verification complete. Parity score: {report.overall_parity_score:.1%}, Passed: {report.passed}")
    return result.data


@task(
    name="check_compliance",
    description="Check legal compliance",
)
async def check_compliance(
    run_id: str,
    apk_hash: str,
    generated_files: dict[str, str],
) -> ComplianceOutput:
    """Check legal compliance.

    Args:
        run_id: Pipeline run ID
        apk_hash: Original APK hash
        generated_files: Map of file paths to content

    Returns:
        ComplianceOutput with compliance report
    """
    logger = get_run_logger()
    logger.info("Checking compliance")

    storage = get_storage()
    service = ComplianceGuard(storage)

    input_data = ComplianceInput(
        run_id=run_id,
        apk_hash=apk_hash,
        generated_files=generated_files,
    )

    result = await service.check(input_data)

    if not result.success:
        raise RuntimeError(f"Compliance check failed: {result.error}")

    report = result.data.compliance_report
    logger.info(f"Compliance check complete. Passed: {report.passed}, Violations: {len(report.violations)}")
    return result.data
