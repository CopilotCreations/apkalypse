"""Unit tests for core models."""

import pytest
from datetime import datetime

from src.models.apk import (
    APKMetadata,
    APKProvenance,
    ManifestData,
    ActivityInfo,
    PermissionInfo,
    PermissionCategory,
)
from src.models.behavior import (
    BehaviorModel,
    ScreenModel,
    StateTransition,
    UserAction,
    ActionType,
    UserIntent,
    NavigationRule,
)
from src.models.spec import (
    BehavioralSpec,
    FunctionalRequirement,
    NonFunctionalRequirement,
    NFRCategory,
    RequirementPriority,
    ScreenSpec,
)


class TestAPKModels:
    """Tests for APK-related models."""

    def test_permission_info_short_name(self):
        """Test permission short name extraction.

        Verifies that PermissionInfo correctly extracts the short name
        from a fully qualified Android permission string.
        """
        perm = PermissionInfo(
            name="android.permission.CAMERA",
            category=PermissionCategory.DANGEROUS,
        )
        assert perm.short_name == "CAMERA"

    def test_activity_info_simple_name(self):
        """Test activity simple name extraction.

        Verifies that ActivityInfo correctly extracts the simple class name
        from a fully qualified activity class name.
        """
        activity = ActivityInfo(
            name="com.example.app.MainActivity",
            exported=True,
        )
        assert activity.simple_name == "MainActivity"

    def test_manifest_launcher_activity(self):
        """Test launcher activity detection.

        Verifies that ManifestData correctly identifies the launcher activity
        from a list of activities.
        """
        manifest = ManifestData(
            package_name="com.example.app",
            activities=[
                ActivityInfo(name="com.example.app.SplashActivity", is_launcher=False),
                ActivityInfo(name="com.example.app.MainActivity", is_launcher=True),
                ActivityInfo(name="com.example.app.SettingsActivity", is_launcher=False),
            ],
        )
        launcher = manifest.launcher_activity
        assert launcher is not None
        assert launcher.name == "com.example.app.MainActivity"

    def test_manifest_dangerous_permissions(self):
        """Test dangerous permissions filtering.

        Verifies that ManifestData correctly filters and returns only
        dangerous permissions from the full permission list.
        """
        manifest = ManifestData(
            package_name="com.example.app",
            permissions=[
                PermissionInfo(name="android.permission.INTERNET", category=PermissionCategory.NORMAL),
                PermissionInfo(name="android.permission.CAMERA", category=PermissionCategory.DANGEROUS),
                PermissionInfo(name="android.permission.LOCATION", category=PermissionCategory.DANGEROUS),
            ],
        )
        dangerous = manifest.dangerous_permissions
        assert len(dangerous) == 2
        assert all(p.category == PermissionCategory.DANGEROUS for p in dangerous)

    def test_apk_metadata_serialization(self):
        """Test APK metadata JSON serialization.

        Verifies that APKMetadata can be serialized to JSON and contains
        the expected package name and hash values.
        """
        metadata = APKMetadata(
            provenance=APKProvenance(
                sha256_hash="abc123" * 10,
                sha1_hash="def456" * 8,
                md5_hash="ghi789" * 5,
                file_size_bytes=1024,
                file_name="app.apk",
            ),
            manifest=ManifestData(package_name="com.example.app"),
        )
        json_str = metadata.model_dump_json()
        assert "com.example.app" in json_str
        assert "abc123" in json_str


class TestBehaviorModels:
    """Tests for behavior models."""

    def test_screen_model_creation(self):
        """Test screen model creation.

        Verifies that ScreenModel can be created with required fields
        and has correct default values.
        """
        screen = ScreenModel(
            screen_id="screen_1",
            screen_name="Home Screen",
            description="Main landing screen",
        )
        assert screen.screen_id == "screen_1"
        assert screen.screen_name == "Home Screen"
        assert screen.discovery_method == "dynamic"

    def test_user_action_creation(self):
        """Test user action creation.

        Verifies that UserAction can be created with the required fields
        and correctly stores action type and source screen.
        """
        action = UserAction(
            action_id="action_1",
            action_type=ActionType.TAP,
            source_screen_id="screen_1",
            description="Tap login button",
        )
        assert action.action_type == ActionType.TAP
        assert action.source_screen_id == "screen_1"

    def test_state_transition_creation(self):
        """Test state transition creation.

        Verifies that StateTransition can be created with source and
        destination screens linked by a triggering action.
        """
        action = UserAction(
            action_id="action_1",
            action_type=ActionType.TAP,
            source_screen_id="screen_1",
            description="Navigate",
        )
        transition = StateTransition(
            transition_id="trans_1",
            from_screen_id="screen_1",
            to_screen_id="screen_2",
            triggered_by_action=action,
        )
        assert transition.from_screen_id == "screen_1"
        assert transition.to_screen_id == "screen_2"

    def test_behavior_model_statistics(self):
        """Test behavior model statistics update.

        Verifies that BehaviorModel correctly updates and calculates
        statistics for screens, intents, and transitions.
        """
        model = BehaviorModel(
            model_id="model_1",
            app_package="com.example.app",
            screens=[
                ScreenModel(screen_id="s1", screen_name="Screen 1"),
                ScreenModel(screen_id="s2", screen_name="Screen 2"),
            ],
            user_intents=[
                UserIntent(
                    intent_id="i1",
                    name="Login",
                    description="User login",
                ),
            ],
        )
        model.update_statistics()
        
        assert model.total_screens == 2
        assert model.total_user_intents == 1
        assert model.total_transitions == 0

    def test_behavior_model_screen_lookup(self):
        """Test screen lookup by ID.

        Verifies that BehaviorModel can retrieve screens by their ID
        and returns None for non-existent screen IDs.
        """
        model = BehaviorModel(
            model_id="model_1",
            app_package="com.example.app",
            screens=[
                ScreenModel(screen_id="s1", screen_name="Screen 1"),
                ScreenModel(screen_id="s2", screen_name="Screen 2"),
            ],
        )
        
        screen = model.get_screen("s1")
        assert screen is not None
        assert screen.screen_name == "Screen 1"
        
        assert model.get_screen("nonexistent") is None

    def test_behavior_model_transition_queries(self):
        """Test transition query methods.

        Verifies that BehaviorModel can query transitions by source
        and destination screen IDs.
        """
        action = UserAction(
            action_id="a1",
            action_type=ActionType.TAP,
            source_screen_id="s1",
        )
        model = BehaviorModel(
            model_id="model_1",
            app_package="com.example.app",
            screens=[
                ScreenModel(screen_id="s1", screen_name="Screen 1"),
                ScreenModel(screen_id="s2", screen_name="Screen 2"),
            ],
            transitions=[
                StateTransition(
                    transition_id="t1",
                    from_screen_id="s1",
                    to_screen_id="s2",
                    triggered_by_action=action,
                ),
            ],
        )
        
        from_s1 = model.get_transitions_from("s1")
        assert len(from_s1) == 1
        
        to_s2 = model.get_transitions_to("s2")
        assert len(to_s2) == 1


class TestSpecModels:
    """Tests for specification models."""

    def test_functional_requirement_creation(self):
        """Test functional requirement creation.

        Verifies that FunctionalRequirement can be created with required
        fields including priority and acceptance criteria.
        """
        req = FunctionalRequirement(
            req_id="FR-001",
            title="User Login",
            description="Users shall be able to login with email and password",
            priority=RequirementPriority.MUST,
            acceptance_criteria=[
                "Email field accepts valid email format",
                "Password field masks input",
            ],
        )
        assert req.req_id == "FR-001"
        assert req.priority == RequirementPriority.MUST
        assert len(req.acceptance_criteria) == 2

    def test_nonfunctional_requirement_creation(self):
        """Test non-functional requirement creation.

        Verifies that NonFunctionalRequirement can be created with
        category, metric, and target value fields.
        """
        req = NonFunctionalRequirement(
            req_id="NFR-001",
            title="App Launch Time",
            description="App shall launch within 2 seconds",
            category=NFRCategory.PERFORMANCE,
            priority=RequirementPriority.SHOULD,
            metric="Cold start time",
            target_value="< 2 seconds",
        )
        assert req.category == NFRCategory.PERFORMANCE
        assert req.metric == "Cold start time"

    def test_behavioral_spec_creation(self):
        """Test behavioral spec creation.

        Verifies that BehavioralSpec can be created with functional
        requirements and screen specifications.
        """
        spec = BehavioralSpec(
            spec_id="spec_1",
            app_name="My App",
            executive_summary="A sample application",
            functional_requirements=[
                FunctionalRequirement(
                    req_id="FR-001",
                    title="Feature 1",
                    description="Description",
                ),
            ],
            screen_specs=[
                ScreenSpec(
                    screen_id="s1",
                    screen_name="Home",
                    description="Home screen",
                ),
            ],
            source_behavior_model_id="model_1",
        )
        assert spec.app_name == "My App"
        assert len(spec.functional_requirements) == 1
        assert len(spec.screen_specs) == 1
