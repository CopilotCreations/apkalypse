"""
Behavioral data models.

These models represent the canonical internal representation of application behavior,
extracted through static and dynamic analysis. They are implementation-agnostic
and focus on observable user-facing behavior.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    """Types of user actions that can be performed."""

    TAP = "tap"
    LONG_PRESS = "long_press"
    SWIPE = "swipe"
    SCROLL = "scroll"
    TYPE_TEXT = "type_text"
    BACK = "back"
    HOME = "home"
    MENU = "menu"
    PERMISSION_GRANT = "permission_grant"
    PERMISSION_DENY = "permission_deny"
    NOTIFICATION_TAP = "notification_tap"
    DEEP_LINK = "deep_link"


class SideEffectType(str, Enum):
    """Types of side effects an action can produce."""

    NETWORK_REQUEST = "network_request"
    DATABASE_WRITE = "database_write"
    FILE_WRITE = "file_write"
    NOTIFICATION = "notification"
    TOAST = "toast"
    DIALOG = "dialog"
    PERMISSION_REQUEST = "permission_request"
    EXTERNAL_APP = "external_app"
    CLIPBOARD = "clipboard"
    VIBRATION = "vibration"
    SOUND = "sound"


class UIElementType(str, Enum):
    """Types of UI elements."""

    BUTTON = "button"
    TEXT_FIELD = "text_field"
    TEXT_VIEW = "text_view"
    IMAGE = "image"
    LIST = "list"
    LIST_ITEM = "list_item"
    GRID = "grid"
    CARD = "card"
    TAB = "tab"
    NAVIGATION_ITEM = "navigation_item"
    FAB = "fab"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    SWITCH = "switch"
    SLIDER = "slider"
    DROPDOWN = "dropdown"
    DIALOG = "dialog"
    BOTTOM_SHEET = "bottom_sheet"
    APP_BAR = "app_bar"
    TOOLBAR = "toolbar"
    UNKNOWN = "unknown"


class UIElement(BaseModel):
    """Representation of a UI element on screen."""

    element_id: str = Field(description="Unique identifier for this element")
    element_type: UIElementType = Field(description="Type of UI element")
    resource_id: str | None = Field(default=None, description="Android resource ID if available")
    content_description: str | None = Field(default=None, description="Accessibility description")
    text: str | None = Field(default=None, description="Visible text content")
    hint_text: str | None = Field(default=None, description="Hint text for input fields")
    
    # Position and size (normalized 0-1 coordinates)
    bounds_left: float = Field(default=0.0, ge=0.0, le=1.0)
    bounds_top: float = Field(default=0.0, ge=0.0, le=1.0)
    bounds_right: float = Field(default=1.0, ge=0.0, le=1.0)
    bounds_bottom: float = Field(default=1.0, ge=0.0, le=1.0)
    
    # State
    is_clickable: bool = Field(default=False)
    is_focusable: bool = Field(default=False)
    is_editable: bool = Field(default=False)
    is_scrollable: bool = Field(default=False)
    is_enabled: bool = Field(default=True)
    is_visible: bool = Field(default=True)
    
    # Hierarchy
    children: list[UIElement] = Field(default_factory=list)


class ScreenModel(BaseModel):
    """Representation of a unique screen state."""

    screen_id: str = Field(description="Unique identifier for this screen")
    screen_name: str = Field(description="Human-readable screen name")
    activity_name: str | None = Field(default=None, description="Associated activity if known")
    
    title: str | None = Field(default=None, description="Screen title from app bar")
    description: str = Field(default="", description="AI-generated description of screen purpose")
    
    # UI structure
    root_elements: list[UIElement] = Field(default_factory=list)
    interactive_elements: list[str] = Field(default_factory=list, description="IDs of clickable elements")
    
    # Screen characteristics
    has_navigation: bool = Field(default=False, description="Has bottom/side navigation")
    has_app_bar: bool = Field(default=False, description="Has top app bar")
    has_fab: bool = Field(default=False, description="Has floating action button")
    has_tabs: bool = Field(default=False, description="Has tab layout")
    is_dialog: bool = Field(default=False, description="Is a dialog overlay")
    is_bottom_sheet: bool = Field(default=False, description="Is a bottom sheet")
    
    # Screenshots (base64 encoded, stored separately)
    screenshot_hash: str | None = Field(default=None, description="Hash reference to screenshot")
    
    # Metadata
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    discovery_method: str = Field(default="dynamic", description="How screen was discovered")


class UserAction(BaseModel):
    """A user action performed on the UI."""

    action_id: str = Field(description="Unique action identifier")
    action_type: ActionType = Field(description="Type of action")
    target_element_id: str | None = Field(default=None, description="Target UI element ID")
    
    # Action parameters
    text_input: str | None = Field(default=None, description="Text entered for type actions")
    swipe_direction: str | None = Field(default=None, description="up/down/left/right")
    coordinates: tuple[float, float] | None = Field(default=None, description="Normalized tap coordinates")
    
    # Timing
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    duration_ms: int = Field(default=0, description="Action duration in milliseconds")
    
    # Context
    source_screen_id: str = Field(description="Screen where action was performed")
    description: str = Field(default="", description="Human-readable action description")


class SideEffect(BaseModel):
    """Observable side effect of an action."""

    effect_id: str = Field(description="Unique identifier")
    effect_type: SideEffectType = Field(description="Type of side effect")
    
    # Effect details (type-specific)
    network_endpoint: str | None = Field(default=None, description="API endpoint called")
    network_method: str | None = Field(default=None, description="HTTP method")
    network_request_schema: dict[str, Any] | None = Field(default=None, description="Request body schema")
    network_response_schema: dict[str, Any] | None = Field(default=None, description="Response body schema")
    
    toast_message: str | None = Field(default=None)
    dialog_title: str | None = Field(default=None)
    dialog_message: str | None = Field(default=None)
    
    permission_requested: str | None = Field(default=None)
    
    # Timing
    triggered_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationship
    caused_by_action_id: str | None = Field(default=None)


class StateTransition(BaseModel):
    """A transition between screen states."""

    transition_id: str = Field(description="Unique identifier")
    from_screen_id: str = Field(description="Source screen")
    to_screen_id: str = Field(description="Destination screen")
    triggered_by_action: UserAction = Field(description="Action that caused transition")
    
    # Transition characteristics
    transition_type: str = Field(default="navigate", description="navigate/dialog/sheet/replace")
    animation_type: str | None = Field(default=None, description="Observed animation type")
    
    # Side effects during transition
    side_effects: list[SideEffect] = Field(default_factory=list)
    
    # Conditions
    requires_authentication: bool = Field(default=False)
    requires_permissions: list[str] = Field(default_factory=list)
    requires_network: bool = Field(default=False)
    
    # Metadata
    observed_count: int = Field(default=1, description="Times this transition was observed")
    average_duration_ms: float = Field(default=0.0)


class NavigationRule(BaseModel):
    """A high-level navigation rule derived from transitions."""

    rule_id: str = Field(description="Unique identifier")
    name: str = Field(description="Human-readable rule name")
    description: str = Field(default="")
    
    from_screens: list[str] = Field(description="Source screen IDs (can be wildcard)")
    to_screen: str = Field(description="Destination screen ID")
    
    trigger_conditions: list[str] = Field(default_factory=list, description="Conditions to trigger")
    guard_conditions: list[str] = Field(default_factory=list, description="Conditions to allow")
    
    is_back_navigation: bool = Field(default=False)
    is_deep_link: bool = Field(default=False)
    deep_link_pattern: str | None = Field(default=None)


class UserIntent(BaseModel):
    """A high-level user intent (goal) inferred from behavior."""

    intent_id: str = Field(description="Unique identifier")
    name: str = Field(description="Intent name (e.g., 'login', 'purchase_item')")
    description: str = Field(description="Description of user goal")
    
    # Steps to achieve intent
    required_screens: list[str] = Field(default_factory=list)
    required_actions: list[str] = Field(default_factory=list)
    
    # Preconditions
    preconditions: list[str] = Field(default_factory=list)
    
    # Expected outcome
    success_indicators: list[str] = Field(default_factory=list)
    failure_indicators: list[str] = Field(default_factory=list)
    
    # Priority
    is_primary: bool = Field(default=False, description="Is this a primary user journey")
    estimated_frequency: str = Field(default="medium", description="low/medium/high")


class DataFlow(BaseModel):
    """Data flow between components."""

    flow_id: str = Field(description="Unique identifier")
    name: str = Field(description="Flow name")
    
    # Source and destination
    source_type: str = Field(description="user_input/api/database/file")
    source_id: str = Field(description="Identifier of source")
    destination_type: str = Field(description="screen/api/database/file")
    destination_id: str = Field(description="Identifier of destination")
    
    # Data characteristics
    data_type: str = Field(default="unknown", description="Type of data")
    is_sensitive: bool = Field(default=False, description="Contains PII or sensitive data")
    is_persisted: bool = Field(default=False, description="Data is persisted")
    
    # Transformations
    transformations: list[str] = Field(default_factory=list, description="Applied transformations")


class BehaviorModel(BaseModel):
    """Complete behavioral model of an application.

    This is the canonical internal representation that captures all observable
    behaviors without any implementation details.
    """

    model_version: str = Field(default="1.0.0", description="Schema version")
    model_id: str = Field(description="Unique model identifier")
    app_package: str = Field(description="Original app package name")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Core components
    screens: list[ScreenModel] = Field(default_factory=list)
    transitions: list[StateTransition] = Field(default_factory=list)
    navigation_rules: list[NavigationRule] = Field(default_factory=list)
    user_intents: list[UserIntent] = Field(default_factory=list)
    data_flows: list[DataFlow] = Field(default_factory=list)
    
    # Aggregated side effects
    all_side_effects: list[SideEffect] = Field(default_factory=list)
    
    # App-level characteristics
    entry_screen_id: str | None = Field(default=None, description="Initial screen")
    auth_required: bool = Field(default=False)
    offline_capable: bool = Field(default=False)
    
    # Derived statistics
    total_screens: int = Field(default=0)
    total_transitions: int = Field(default=0)
    total_user_intents: int = Field(default=0)
    coverage_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Exploration coverage")

    def update_statistics(self) -> None:
        """Update derived statistics from model data.

        Recalculates total counts for screens, transitions, and user intents
        based on the current model state. Also updates the updated_at timestamp.

        Returns:
            None
        """
        self.total_screens = len(self.screens)
        self.total_transitions = len(self.transitions)
        self.total_user_intents = len(self.user_intents)
        self.updated_at = datetime.utcnow()

    def get_screen(self, screen_id: str) -> ScreenModel | None:
        """Get screen by ID.

        Args:
            screen_id: The unique identifier of the screen to retrieve.

        Returns:
            The ScreenModel with the matching ID, or None if not found.
        """
        for screen in self.screens:
            if screen.screen_id == screen_id:
                return screen
        return None

    def get_transitions_from(self, screen_id: str) -> list[StateTransition]:
        """Get all transitions originating from a screen.

        Args:
            screen_id: The unique identifier of the source screen.

        Returns:
            A list of StateTransition objects that start from the given screen.
        """
        return [t for t in self.transitions if t.from_screen_id == screen_id]

    def get_transitions_to(self, screen_id: str) -> list[StateTransition]:
        """Get all transitions leading to a screen.

        Args:
            screen_id: The unique identifier of the destination screen.

        Returns:
            A list of StateTransition objects that end at the given screen.
        """
        return [t for t in self.transitions if t.to_screen_id == screen_id]

    class Config:
        json_schema_extra = {
            "title": "Behavior Model",
            "description": "Complete behavioral specification of an Android application"
        }
