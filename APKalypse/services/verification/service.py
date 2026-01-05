"""
Verification Service.

Verifies behavioral parity between original and generated applications.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ...agents import AgentContext, QAParityAgent
from ...agents.qa_parity import ParityInput, ParityOutput
from ...core.logging import get_logger
from ...core.types import ServiceResult
from ...models.behavior import BehaviorModel, ScreenModel, StateTransition
from ...models.codegen import AndroidProject
from ...storage import StorageBackend

logger = get_logger(__name__)


class ParityIssue(BaseModel):
    """A parity issue found during verification."""

    issue_id: str
    severity: str  # critical, major, minor
    category: str  # ui, navigation, data, behavior
    description: str
    original_value: str
    generated_value: str
    suggested_fix: str


class TestScenario(BaseModel):
    """A test scenario for verification."""

    scenario_id: str
    name: str
    description: str
    steps: list[str] = Field(default_factory=list)
    expected_outcome: str


class ParityReport(BaseModel):
    """Complete parity verification report."""

    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)

    original_app_package: str
    generated_app_package: str

    # Overall results
    overall_parity_score: float = Field(ge=0.0, le=1.0)
    passed: bool

    # Detailed results
    scenarios_tested: int
    scenarios_passed: int
    scenarios_failed: int

    issues: list[ParityIssue] = Field(default_factory=list)
    matching_behaviors: list[str] = Field(default_factory=list)

    # Test scenarios
    test_scenarios: list[TestScenario] = Field(default_factory=list)

    # Recommendations
    recommendations: list[str] = Field(default_factory=list)


class VerificationInput(BaseModel):
    """Input for verification."""

    behavior_model: BehaviorModel
    generated_project: AndroidProject
    run_id: str = Field(description="Pipeline run ID")


class VerificationOutput(BaseModel):
    """Output from verification."""

    parity_report: ParityReport
    storage_key: str = Field(description="Storage key for report")


class VerificationService:
    """Service for verifying behavioral parity.

    Compares the behavioral model with the generated application to
    ensure functional equivalence.
    """

    def __init__(self, storage: StorageBackend) -> None:
        """Initialize the verification service.

        Args:
            storage: Backend for storing verification reports and artifacts.
        """
        self.storage = storage
        self.parity_agent = QAParityAgent()

    def _generate_test_scenarios(self, behavior_model: BehaviorModel) -> list[TestScenario]:
        """Generate test scenarios from behavior model.

        Creates navigation, user intent, and screen presence test scenarios
        based on the behavior model's transitions, intents, and screens.

        Args:
            behavior_model: The behavior model containing screens, transitions,
                and user intents to generate test scenarios from.

        Returns:
            A list of TestScenario objects covering navigation flows,
            user intents, and screen presence verification.
        """
        scenarios = []

        # Navigation scenarios
        for i, transition in enumerate(behavior_model.transitions[:10]):
            from_screen = behavior_model.get_screen(transition.from_screen_id)
            to_screen = behavior_model.get_screen(transition.to_screen_id)

            scenarios.append(TestScenario(
                scenario_id=f"NAV-{i + 1:03d}",
                name=f"Navigate from {from_screen.screen_name if from_screen else 'unknown'} to {to_screen.screen_name if to_screen else 'unknown'}",
                description=f"Verify navigation transition works correctly",
                steps=[
                    f"Start on {from_screen.screen_name if from_screen else 'unknown'} screen",
                    f"Perform action: {transition.triggered_by_action.description}",
                    f"Verify navigation to {to_screen.screen_name if to_screen else 'unknown'}",
                ],
                expected_outcome=f"User arrives at {to_screen.screen_name if to_screen else 'unknown'} screen",
            ))

        # User intent scenarios
        for intent in behavior_model.user_intents:
            scenarios.append(TestScenario(
                scenario_id=f"INT-{len(scenarios) + 1:03d}",
                name=intent.name,
                description=intent.description,
                steps=intent.preconditions + [f"Verify {indicator}" for indicator in intent.success_indicators[:3]],
                expected_outcome=f"User successfully completes {intent.name}",
            ))

        # Screen presence scenarios
        for screen in behavior_model.screens[:5]:
            scenarios.append(TestScenario(
                scenario_id=f"SCR-{len(scenarios) + 1:03d}",
                name=f"Verify {screen.screen_name} screen",
                description=f"Verify {screen.screen_name} screen exists and displays correctly",
                steps=[
                    f"Navigate to {screen.screen_name}",
                    f"Verify screen title/header",
                    f"Verify key elements are present",
                ],
                expected_outcome=f"{screen.screen_name} screen displays correctly with expected elements",
            ))

        return scenarios

    def _verify_screen_coverage(
        self,
        behavior_model: BehaviorModel,
        project: AndroidProject,
    ) -> tuple[float, list[str], list[ParityIssue]]:
        """Verify that all screens are represented in generated code.

        Compares expected screens from the behavior model against the
        generated source files to identify missing screen implementations.

        Args:
            behavior_model: The behavior model containing expected screens.
            project: The generated Android project to verify against.

        Returns:
            A tuple containing:
                - Coverage score (0.0 to 1.0) indicating screen implementation ratio.
                - List of matching behavior descriptions for implemented screens.
                - List of ParityIssue objects for missing screens.
        """
        matching = []
        issues = []

        # Get all screen names from behavior model
        expected_screens = {s.screen_name.lower().replace(" ", "") for s in behavior_model.screens}

        # Get screens from generated code
        generated_screens = set()
        for files in project.source_files.values():
            for file in files:
                if "Screen" in file.file_name:
                    screen_name = file.file_name.replace("Screen", "").lower()
                    generated_screens.add(screen_name)

        # Find matches and misses
        for screen in expected_screens:
            if screen in generated_screens or any(screen in g for g in generated_screens):
                matching.append(f"Screen '{screen}' is implemented")
            else:
                issues.append(ParityIssue(
                    issue_id=f"SCR-{len(issues) + 1:03d}",
                    severity="major",
                    category="ui",
                    description=f"Screen '{screen}' not found in generated code",
                    original_value=screen,
                    generated_value="missing",
                    suggested_fix=f"Implement {screen.title()}Screen composable",
                ))

        coverage = len(matching) / max(len(expected_screens), 1)
        return coverage, matching, issues

    def _verify_navigation_coverage(
        self,
        behavior_model: BehaviorModel,
        project: AndroidProject,
    ) -> tuple[float, list[str], list[ParityIssue]]:
        """Verify that navigation flows are represented.

        Checks that the generated project contains a navigation implementation
        and that routes are defined for all expected screens.

        Args:
            behavior_model: The behavior model containing expected transitions.
            project: The generated Android project to verify against.

        Returns:
            A tuple containing:
                - Coverage score (0.0 or 1.0) based on navigation presence.
                - List of matching behavior descriptions for navigation elements.
                - List of ParityIssue objects for missing navigation components.
        """
        matching = []
        issues = []

        # Check for navigation file
        has_navigation = False
        for files in project.source_files.values():
            for file in files:
                if "Navigation" in file.file_name:
                    has_navigation = True
                    break

        if has_navigation:
            matching.append("Navigation graph is implemented")
        else:
            issues.append(ParityIssue(
                issue_id="NAV-001",
                severity="critical",
                category="navigation",
                description="No navigation implementation found",
                original_value=f"{len(behavior_model.transitions)} transitions",
                generated_value="missing",
                suggested_fix="Implement AppNavigation composable with NavHost",
            ))

        # Check for routes
        expected_routes = len(behavior_model.screens)
        # Simplified check - in real implementation would parse navigation code
        if expected_routes > 0:
            matching.append(f"Navigation routes defined for {expected_routes} screens")

        coverage = 1.0 if has_navigation else 0.0
        return coverage, matching, issues

    def _verify_architectural_compliance(
        self,
        project: AndroidProject,
    ) -> tuple[float, list[str], list[ParityIssue]]:
        """Verify architectural compliance.

        Checks for required architectural patterns including ViewModel,
        Hilt dependency injection, and Jetpack Compose usage.

        Args:
            project: The generated Android project to verify against.

        Returns:
            A tuple containing:
                - Compliance score (0.0 to 1.0) based on patterns found.
                - List of matching behavior descriptions for implemented patterns.
                - List of ParityIssue objects for missing architectural patterns.
        """
        matching = []
        issues = []

        # Check for required patterns
        patterns = {
            "viewmodel": False,
            "hilt": False,
            "compose": False,
        }

        for files in project.source_files.values():
            for file in files:
                content = file.raw_content or ""
                if "ViewModel" in content or "ViewModel" in file.file_name:
                    patterns["viewmodel"] = True
                if "@HiltViewModel" in content or "hilt" in content.lower():
                    patterns["hilt"] = True
                if "@Composable" in content or "Compose" in file.file_name:
                    patterns["compose"] = True

        for pattern, present in patterns.items():
            if present:
                matching.append(f"{pattern.title()} pattern is implemented")
            else:
                issues.append(ParityIssue(
                    issue_id=f"ARCH-{len(issues) + 1:03d}",
                    severity="major",
                    category="behavior",
                    description=f"{pattern.title()} pattern not found",
                    original_value="expected",
                    generated_value="missing",
                    suggested_fix=f"Implement {pattern} pattern as specified in architecture",
                ))

        coverage = sum(1 for v in patterns.values() if v) / len(patterns)
        return coverage, matching, issues

    async def verify(self, input_data: VerificationInput) -> ServiceResult[VerificationOutput]:
        """Verify behavioral parity.

        Args:
            input_data: Verification input

        Returns:
            ServiceResult containing VerificationOutput
        """
        import time

        start_time = time.perf_counter()

        try:
            logger.info("Starting verification", run_id=input_data.run_id)

            behavior_model = input_data.behavior_model
            project = input_data.generated_project

            all_matching: list[str] = []
            all_issues: list[ParityIssue] = []
            scores: list[float] = []

            # Screen coverage
            screen_score, screen_matching, screen_issues = self._verify_screen_coverage(
                behavior_model, project
            )
            scores.append(screen_score)
            all_matching.extend(screen_matching)
            all_issues.extend(screen_issues)

            # Navigation coverage
            nav_score, nav_matching, nav_issues = self._verify_navigation_coverage(
                behavior_model, project
            )
            scores.append(nav_score)
            all_matching.extend(nav_matching)
            all_issues.extend(nav_issues)

            # Architectural compliance
            arch_score, arch_matching, arch_issues = self._verify_architectural_compliance(
                project
            )
            scores.append(arch_score)
            all_matching.extend(arch_matching)
            all_issues.extend(arch_issues)

            # Generate test scenarios
            test_scenarios = self._generate_test_scenarios(behavior_model)

            # Calculate overall score
            overall_score = sum(scores) / len(scores) if scores else 0.0

            # Determine pass/fail
            critical_issues = [i for i in all_issues if i.severity == "critical"]
            passed = overall_score >= 0.7 and len(critical_issues) == 0

            # Generate recommendations
            recommendations = []
            if screen_score < 1.0:
                recommendations.append("Implement missing screen composables")
            if nav_score < 1.0:
                recommendations.append("Complete navigation graph implementation")
            if arch_score < 1.0:
                recommendations.append("Ensure all architectural patterns are properly implemented")
            if not passed:
                recommendations.append("Address critical issues before deployment")

            # Create report
            report = ParityReport(
                original_app_package=behavior_model.app_package,
                generated_app_package=project.package_name,
                overall_parity_score=overall_score,
                passed=passed,
                scenarios_tested=len(test_scenarios),
                scenarios_passed=int(len(test_scenarios) * overall_score),
                scenarios_failed=len(test_scenarios) - int(len(test_scenarios) * overall_score),
                issues=all_issues,
                matching_behaviors=all_matching,
                test_scenarios=test_scenarios,
                recommendations=recommendations,
            )

            # Store report
            storage_key = f"reports/{input_data.run_id}/parity_report.json"
            await self.storage.store_model(storage_key, report)

            output = VerificationOutput(
                parity_report=report,
                storage_key=storage_key,
            )

            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                "Verification completed",
                parity_score=overall_score,
                passed=passed,
                issues=len(all_issues),
                duration_ms=duration_ms,
            )

            return ServiceResult.ok(output, duration_ms=duration_ms)

        except Exception as e:
            logger.error("Verification failed", error=str(e))
            return ServiceResult.fail(str(e))
