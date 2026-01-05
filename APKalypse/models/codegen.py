"""
Code generation data models.

These models represent the structure of generated Android projects,
including Gradle configuration, Kotlin source files, and resources.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class DependencyScope(str, Enum):
    """Gradle dependency scopes."""

    IMPLEMENTATION = "implementation"
    API = "api"
    TEST_IMPLEMENTATION = "testImplementation"
    ANDROID_TEST_IMPLEMENTATION = "androidTestImplementation"
    KAPT = "kapt"
    KSP = "ksp"
    COMPILE_ONLY = "compileOnly"
    RUNTIME_ONLY = "runtimeOnly"


class GradleDependency(BaseModel):
    """A Gradle dependency declaration."""

    group: str = Field(description="Group ID")
    artifact: str = Field(description="Artifact ID")
    version: str = Field(default="", description="Version (empty for BOM-managed deps)")
    scope: DependencyScope = Field(default=DependencyScope.IMPLEMENTATION)
    is_platform: bool = Field(default=False, description="Whether this is a platform/BOM dependency")
    
    @property
    def notation(self) -> str:
        """Get Gradle dependency notation.

        Returns:
            str: Dependency string in the format "group:artifact:version" or
                "group:artifact" if no version is specified.
        """
        if self.version:
            return f'"{self.group}:{self.artifact}:{self.version}"'
        return f'"{self.group}:{self.artifact}"'

    @property
    def declaration(self) -> str:
        """Get full Gradle declaration.

        Returns:
            str: Complete Gradle dependency declaration including scope,
                wrapped with platform() for BOM dependencies.
        """
        if self.is_platform:
            return f'{self.scope.value}(platform({self.notation}))'
        return f'{self.scope.value}({self.notation})'


class GradlePlugin(BaseModel):
    """A Gradle plugin declaration."""

    plugin_id: str = Field(description="Plugin ID")
    version: str | None = Field(default=None, description="Plugin version")
    apply: bool = Field(default=True, description="Whether to apply the plugin")

    @property
    def declaration(self) -> str:
        """Get plugin declaration for plugins block.

        Returns:
            str: Complete plugin declaration string suitable for use in a
                Gradle plugins block, including version and apply directives.
        """
        version_part = f' version "{self.version}"' if self.version else ""
        apply_part = " apply false" if not self.apply else ""
        return f'id("{self.plugin_id}"){version_part}{apply_part}'


class AndroidConfig(BaseModel):
    """Android Gradle configuration."""

    namespace: str = Field(description="Application namespace")
    compile_sdk: int = Field(default=34)
    min_sdk: int = Field(default=24)
    target_sdk: int = Field(default=34)
    version_code: int = Field(default=1)
    version_name: str = Field(default="1.0.0")
    
    # Build features
    compose_enabled: bool = Field(default=True)
    view_binding_enabled: bool = Field(default=False)
    data_binding_enabled: bool = Field(default=False)
    build_config_enabled: bool = Field(default=True)
    
    # Compose compiler - must match Kotlin version (1.5.14 for Kotlin 1.9.24)
    compose_compiler_version: str = Field(default="1.5.14")
    
    # Kotlin options
    jvm_target: str = Field(default="17")


class BuildType(BaseModel):
    """Android build type configuration."""

    name: str = Field(description="Build type name (debug/release)")
    minify_enabled: bool = Field(default=False)
    shrink_resources: bool = Field(default=False)
    proguard_files: list[str] = Field(default_factory=list)
    debug_signable: bool = Field(default=False)


class GradleModule(BaseModel):
    """A Gradle module in the project."""

    module_name: str = Field(description="Module name (e.g., :app, :core:data)")
    module_path: str = Field(description="Relative path from project root")
    module_type: str = Field(default="android-library", description="android-app/android-library/kotlin-library")
    
    # Configuration
    android_config: AndroidConfig | None = Field(default=None)
    
    # Dependencies
    plugins: list[GradlePlugin] = Field(default_factory=list)
    dependencies: list[GradleDependency] = Field(default_factory=list)
    module_dependencies: list[str] = Field(default_factory=list, description="Project module dependencies")
    
    # Build types
    build_types: list[BuildType] = Field(default_factory=list)


class KotlinVisibility(str, Enum):
    """Kotlin visibility modifiers."""

    PUBLIC = "public"
    INTERNAL = "internal"
    PRIVATE = "private"
    PROTECTED = "protected"


class KotlinClass(BaseModel):
    """A Kotlin class definition."""

    name: str = Field(description="Class name")
    package: str = Field(description="Package name")
    visibility: KotlinVisibility = Field(default=KotlinVisibility.PUBLIC)
    
    # Class type
    is_data_class: bool = Field(default=False)
    is_sealed: bool = Field(default=False)
    is_object: bool = Field(default=False)
    is_interface: bool = Field(default=False)
    is_abstract: bool = Field(default=False)
    is_enum: bool = Field(default=False)
    
    # Annotations
    annotations: list[str] = Field(default_factory=list)
    
    # Inheritance
    extends: str | None = Field(default=None)
    implements: list[str] = Field(default_factory=list)
    
    # Type parameters
    type_parameters: list[str] = Field(default_factory=list)
    
    # Documentation
    kdoc: str = Field(default="", description="KDoc documentation")

    @property
    def full_name(self) -> str:
        """Get fully qualified class name.

        Returns:
            str: The fully qualified class name in the format "package.ClassName".
        """
        return f"{self.package}.{self.name}"


class KotlinProperty(BaseModel):
    """A Kotlin property definition."""

    name: str
    type: str
    visibility: KotlinVisibility = Field(default=KotlinVisibility.PUBLIC)
    
    is_val: bool = Field(default=True, description="val (true) or var (false)")
    is_nullable: bool = Field(default=False)
    is_lateinit: bool = Field(default=False)
    is_lazy: bool = Field(default=False)
    
    default_value: str | None = Field(default=None)
    annotations: list[str] = Field(default_factory=list)
    kdoc: str = Field(default="")


class KotlinParameter(BaseModel):
    """A Kotlin function parameter."""

    name: str
    type: str
    is_nullable: bool = Field(default=False)
    default_value: str | None = Field(default=None)
    annotations: list[str] = Field(default_factory=list)


class KotlinFunction(BaseModel):
    """A Kotlin function definition."""

    name: str
    visibility: KotlinVisibility = Field(default=KotlinVisibility.PUBLIC)
    
    parameters: list[KotlinParameter] = Field(default_factory=list)
    return_type: str = Field(default="Unit")
    is_suspend: bool = Field(default=False)
    is_inline: bool = Field(default=False)
    is_override: bool = Field(default=False)
    is_extension: bool = Field(default=False)
    receiver_type: str | None = Field(default=None, description="Extension receiver type")
    
    annotations: list[str] = Field(default_factory=list)
    type_parameters: list[str] = Field(default_factory=list)
    kdoc: str = Field(default="")
    
    # The function body (can be template or generated)
    body: str = Field(default="", description="Function body code")


class KotlinFile(BaseModel):
    """A complete Kotlin source file."""

    file_name: str = Field(description="File name without extension")
    package: str = Field(description="Package name")
    relative_path: str = Field(description="Relative path from source root")
    
    # Imports
    imports: list[str] = Field(default_factory=list)
    
    # Content
    classes: list[KotlinClass] = Field(default_factory=list)
    top_level_properties: list[KotlinProperty] = Field(default_factory=list)
    top_level_functions: list[KotlinFunction] = Field(default_factory=list)
    
    # File-level annotations
    file_annotations: list[str] = Field(default_factory=list)
    
    # Raw content (if generating from template)
    raw_content: str | None = Field(default=None, description="Pre-generated content")

    @property
    def full_path(self) -> str:
        """Get full file path.

        Returns:
            str: The complete file path including relative path and .kt extension.
        """
        return f"{self.relative_path}/{self.file_name}.kt"


class ResourceType(str, Enum):
    """Android resource types."""

    DRAWABLE = "drawable"
    MIPMAP = "mipmap"
    VALUES = "values"
    LAYOUT = "layout"
    RAW = "raw"
    XML = "xml"
    FONT = "font"
    COLOR = "color"
    NAVIGATION = "navigation"


class ResourceFile(BaseModel):
    """An Android resource file."""

    resource_type: ResourceType = Field(description="Resource type")
    file_name: str = Field(description="File name with extension")
    qualifier: str = Field(default="", description="Resource qualifier (e.g., 'night', 'v26')")
    
    content: str = Field(default="", description="File content")
    is_binary: bool = Field(default=False)
    binary_content_base64: str | None = Field(default=None)

    @property
    def directory_name(self) -> str:
        """Get resource directory name.

        Returns:
            str: The resource directory name, including qualifier suffix
                if present (e.g., "drawable-night" or "values").
        """
        if self.qualifier:
            return f"{self.resource_type.value}-{self.qualifier}"
        return self.resource_type.value


class AndroidProject(BaseModel):
    """Complete Android project structure."""

    project_name: str = Field(description="Project name")
    package_name: str = Field(description="Base package name")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Gradle configuration - AGP 8.5.0 supports Gradle 8.7-8.9 and 9.x
    gradle_version: str = Field(default="8.9")
    agp_version: str = Field(default="8.5.0")
    kotlin_version: str = Field(default="1.9.24")
    
    # Modules
    modules: list[GradleModule] = Field(default_factory=list)
    
    # Source files (organized by module)
    source_files: dict[str, list[KotlinFile]] = Field(default_factory=dict)
    
    # Resource files (organized by module)
    resource_files: dict[str, list[ResourceFile]] = Field(default_factory=dict)
    
    # Root project files
    root_build_gradle: str = Field(default="", description="Root build.gradle.kts content")
    settings_gradle: str = Field(default="", description="settings.gradle.kts content")
    gradle_properties: str = Field(default="", description="gradle.properties content")
    
    # Traceability
    source_architecture_spec_id: str = Field(description="ID of source architecture spec")
    source_behavioral_spec_id: str = Field(description="ID of source behavioral spec")
    
    # Generation metadata
    generation_timestamp: datetime = Field(default_factory=datetime.utcnow)
    generator_version: str = Field(default="1.0.0")

    def get_module(self, name: str) -> GradleModule | None:
        """Get module by name.

        Args:
            name: The module name to search for (e.g., ":app", ":core:data").

        Returns:
            The matching GradleModule if found, None otherwise.
        """
        for module in self.modules:
            if module.module_name == name:
                return module
        return None

    class Config:
        json_schema_extra = {
            "title": "Android Project",
            "description": "Complete Android project structure for code generation"
        }
