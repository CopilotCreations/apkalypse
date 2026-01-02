"""
Code Generation Service.

Generates greenfield Android applications from architectural specifications.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ...agents import AgentContext, AndroidImplementationAgent
from ...agents.android_implementation import CodeGenInput, CodeGenOutput
from ...core.logging import get_logger
from ...core.types import ServiceResult
from ...models.codegen import (
    AndroidConfig,
    AndroidProject,
    BuildType,
    DependencyScope,
    GradleDependency,
    GradleModule,
    GradlePlugin,
    KotlinFile,
    ResourceFile,
    ResourceType,
)
from ...models.spec import ArchitectureSpec, BehavioralSpec, ModuleType
from ...storage import StorageBackend

logger = get_logger(__name__)


class CodegenInput(BaseModel):
    """Input for code generation."""

    behavioral_spec: BehavioralSpec
    architecture_spec: ArchitectureSpec
    package_name: str = Field(description="Base package name for generated code")
    run_id: str = Field(description="Pipeline run ID")


class CodegenOutput(BaseModel):
    """Output from code generation."""

    project: AndroidProject
    output_directory: str = Field(description="Storage key for generated project")


class CodegenService:
    """Service for generating Android applications.

    Generates a complete, buildable Android project from specifications.
    Code is generated fresh with no similarity to original source.
    """

    def __init__(self, storage: StorageBackend) -> None:
        """Initialize the codegen service."""
        self.storage = storage
        self.impl_agent = AndroidImplementationAgent()

    def _create_root_build_gradle(self, project: AndroidProject) -> str:
        """Generate root build.gradle.kts content."""
        return f'''// Top-level build file for {project.project_name}
plugins {{
    id("com.android.application") version "{project.agp_version}" apply false
    id("com.android.library") version "{project.agp_version}" apply false
    id("org.jetbrains.kotlin.android") version "{project.kotlin_version}" apply false
    id("org.jetbrains.kotlin.plugin.serialization") version "{project.kotlin_version}" apply false
    id("com.google.dagger.hilt.android") version "2.48" apply false
    id("com.google.devtools.ksp") version "{project.kotlin_version}-1.0.16" apply false
}}

tasks.register("clean", Delete::class) {{
    delete(rootProject.layout.buildDirectory)
}}
'''

    def _create_settings_gradle(self, project: AndroidProject) -> str:
        """Generate settings.gradle.kts content."""
        module_includes = "\n".join([
            f'include("{m.module_name}")'
            for m in project.modules
        ])

        return f'''pluginManagement {{
    repositories {{
        google()
        mavenCentral()
        gradlePluginPortal()
    }}
}}

dependencyResolutionManagement {{
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {{
        google()
        mavenCentral()
    }}
}}

rootProject.name = "{project.project_name}"

{module_includes}
'''

    def _create_gradle_properties(self) -> str:
        """Generate gradle.properties content."""
        return '''# Project-wide Gradle settings
org.gradle.jvmargs=-Xmx4096m -Dfile.encoding=UTF-8
org.gradle.parallel=true
org.gradle.caching=true
org.gradle.configuration-cache=true

# Android settings
android.useAndroidX=true
android.enableJetifier=false
android.nonTransitiveRClass=true

# Kotlin settings
kotlin.code.style=official
kotlin.incremental=true

# Compose settings
kotlin.compiler.extension.version=1.5.8
'''

    def _create_module_build_gradle(self, module: GradleModule, package_name: str) -> str:
        """Generate module build.gradle.kts content."""
        is_app = module.module_type == "android-app"

        plugins_list = [f'id("{p.plugin_id}")' for p in module.plugins]
        plugins_block = "\n    ".join(plugins_list)

        android_block = ""
        if module.android_config:
            config = module.android_config
            app_id_line = f'applicationId = "{config.namespace}"' if is_app else ""
            version_code_line = f"versionCode = {config.version_code}" if is_app else ""
            version_name_line = f'versionName = "{config.version_name}"' if is_app else ""
            
            android_block = f'''
android {{
    namespace = "{config.namespace}"
    compileSdk = {config.compile_sdk}

    defaultConfig {{
        {app_id_line}
        minSdk = {config.min_sdk}
        targetSdk = {config.target_sdk}
        {version_code_line}
        {version_name_line}

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables {{
            useSupportLibrary = true
        }}
    }}

    buildTypes {{
        release {{
            isMinifyEnabled = {"true" if is_app else "false"}
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }}
    }}

    compileOptions {{
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }}

    kotlinOptions {{
        jvmTarget = "{config.jvm_target}"
    }}

    buildFeatures {{
        compose = {str(config.compose_enabled).lower()}
        buildConfig = {str(config.build_config_enabled).lower()}
    }}

    composeOptions {{
        kotlinCompilerExtensionVersion = "{config.compose_compiler_version}"
    }}

    packaging {{
        resources {{
            excludes += "/META-INF/AL2.0"
            excludes += "/META-INF/LGPL2.1"
        }}
    }}
}}
'''

        deps_list = [d.declaration for d in module.dependencies]
        deps_block = "\n    ".join(deps_list)

        module_deps_list = [f'implementation(project("{dep}"))' for dep in module.module_dependencies]
        module_deps = "\n    ".join(module_deps_list)

        return f'''plugins {{
    {plugins_block}
}}
{android_block}
dependencies {{
    {deps_block}
    {module_deps}
}}
'''

    def _create_app_module(self, package_name: str) -> GradleModule:
        """Create the main app module."""
        return GradleModule(
            module_name=":app",
            module_path="app",
            module_type="android-app",
            android_config=AndroidConfig(
                namespace=package_name,
                compile_sdk=34,
                min_sdk=24,
                target_sdk=34,
            ),
            plugins=[
                GradlePlugin(plugin_id="com.android.application"),
                GradlePlugin(plugin_id="org.jetbrains.kotlin.android"),
                GradlePlugin(plugin_id="org.jetbrains.kotlin.plugin.serialization"),
                GradlePlugin(plugin_id="com.google.dagger.hilt.android"),
                GradlePlugin(plugin_id="com.google.devtools.ksp"),
            ],
            dependencies=[
                # Core Android
                GradleDependency(group="androidx.core", artifact="core-ktx", version="1.12.0"),
                GradleDependency(group="androidx.lifecycle", artifact="lifecycle-runtime-ktx", version="2.6.2"),
                GradleDependency(group="androidx.activity", artifact="activity-compose", version="1.8.2"),

                # Compose
                GradleDependency(group="androidx.compose", artifact="compose-bom", version="2024.01.00"),
                GradleDependency(group="androidx.compose.ui", artifact="ui", version=""),
                GradleDependency(group="androidx.compose.ui", artifact="ui-graphics", version=""),
                GradleDependency(group="androidx.compose.ui", artifact="ui-tooling-preview", version=""),
                GradleDependency(group="androidx.compose.material3", artifact="material3", version=""),

                # Navigation
                GradleDependency(group="androidx.navigation", artifact="navigation-compose", version="2.7.6"),
                GradleDependency(group="androidx.hilt", artifact="hilt-navigation-compose", version="1.1.0"),

                # Hilt
                GradleDependency(group="com.google.dagger", artifact="hilt-android", version="2.48"),
                GradleDependency(group="com.google.dagger", artifact="hilt-compiler", version="2.48", scope=DependencyScope.KSP),

                # ViewModel
                GradleDependency(group="androidx.lifecycle", artifact="lifecycle-viewmodel-compose", version="2.6.2"),
                GradleDependency(group="androidx.lifecycle", artifact="lifecycle-runtime-compose", version="2.6.2"),

                # Testing
                GradleDependency(group="junit", artifact="junit", version="4.13.2", scope=DependencyScope.TEST_IMPLEMENTATION),
                GradleDependency(group="androidx.test.ext", artifact="junit", version="1.1.5", scope=DependencyScope.ANDROID_TEST_IMPLEMENTATION),
            ],
            module_dependencies=[":core:ui", ":core:domain"],
        )

    def _create_core_ui_module(self, package_name: str) -> GradleModule:
        """Create the core UI module."""
        return GradleModule(
            module_name=":core:ui",
            module_path="core/ui",
            module_type="android-library",
            android_config=AndroidConfig(
                namespace=f"{package_name}.core.ui",
                compose_enabled=True,
            ),
            plugins=[
                GradlePlugin(plugin_id="com.android.library"),
                GradlePlugin(plugin_id="org.jetbrains.kotlin.android"),
            ],
            dependencies=[
                GradleDependency(group="androidx.compose", artifact="compose-bom", version="2024.01.00"),
                GradleDependency(group="androidx.compose.ui", artifact="ui", version=""),
                GradleDependency(group="androidx.compose.material3", artifact="material3", version=""),
                GradleDependency(group="androidx.compose.ui", artifact="ui-tooling-preview", version=""),
            ],
        )

    def _create_core_domain_module(self, package_name: str) -> GradleModule:
        """Create the core domain module."""
        return GradleModule(
            module_name=":core:domain",
            module_path="core/domain",
            module_type="android-library",
            android_config=AndroidConfig(
                namespace=f"{package_name}.core.domain",
                compose_enabled=False,
            ),
            plugins=[
                GradlePlugin(plugin_id="com.android.library"),
                GradlePlugin(plugin_id="org.jetbrains.kotlin.android"),
                GradlePlugin(plugin_id="com.google.dagger.hilt.android"),
                GradlePlugin(plugin_id="com.google.devtools.ksp"),
            ],
            dependencies=[
                GradleDependency(group="javax.inject", artifact="javax.inject", version="1"),
                GradleDependency(group="org.jetbrains.kotlinx", artifact="kotlinx-coroutines-core", version="1.7.3"),
                GradleDependency(group="com.google.dagger", artifact="hilt-android", version="2.48"),
                GradleDependency(group="com.google.dagger", artifact="hilt-compiler", version="2.48", scope=DependencyScope.KSP),
            ],
            module_dependencies=[":core:data"],
        )

    def _create_core_data_module(self, package_name: str) -> GradleModule:
        """Create the core data module."""
        return GradleModule(
            module_name=":core:data",
            module_path="core/data",
            module_type="android-library",
            android_config=AndroidConfig(
                namespace=f"{package_name}.core.data",
                compose_enabled=False,
            ),
            plugins=[
                GradlePlugin(plugin_id="com.android.library"),
                GradlePlugin(plugin_id="org.jetbrains.kotlin.android"),
                GradlePlugin(plugin_id="org.jetbrains.kotlin.plugin.serialization"),
                GradlePlugin(plugin_id="com.google.dagger.hilt.android"),
                GradlePlugin(plugin_id="com.google.devtools.ksp"),
            ],
            dependencies=[
                # Networking
                GradleDependency(group="com.squareup.retrofit2", artifact="retrofit", version="2.9.0"),
                GradleDependency(group="com.squareup.okhttp3", artifact="okhttp", version="4.12.0"),
                GradleDependency(group="com.squareup.okhttp3", artifact="logging-interceptor", version="4.12.0"),
                GradleDependency(group="org.jetbrains.kotlinx", artifact="kotlinx-serialization-json", version="1.6.2"),
                GradleDependency(group="com.jakewharton.retrofit", artifact="retrofit2-kotlinx-serialization-converter", version="1.0.0"),

                # Room
                GradleDependency(group="androidx.room", artifact="room-runtime", version="2.6.1"),
                GradleDependency(group="androidx.room", artifact="room-ktx", version="2.6.1"),
                GradleDependency(group="androidx.room", artifact="room-compiler", version="2.6.1", scope=DependencyScope.KSP),

                # DataStore
                GradleDependency(group="androidx.datastore", artifact="datastore-preferences", version="1.0.0"),

                # Hilt
                GradleDependency(group="com.google.dagger", artifact="hilt-android", version="2.48"),
                GradleDependency(group="com.google.dagger", artifact="hilt-compiler", version="2.48", scope=DependencyScope.KSP),

                # Coroutines
                GradleDependency(group="org.jetbrains.kotlinx", artifact="kotlinx-coroutines-core", version="1.7.3"),
                GradleDependency(group="org.jetbrains.kotlinx", artifact="kotlinx-coroutines-android", version="1.7.3"),
            ],
        )

    def _generate_application_class(self, package_name: str, app_name: str) -> KotlinFile:
        """Generate the Application class."""
        class_name = self._to_pascal_case(app_name) + "Application"

        content = f'''package {package_name}

import android.app.Application
import dagger.hilt.android.HiltAndroidApp

/**
 * Main Application class for {app_name}.
 * Annotated with @HiltAndroidApp to enable Hilt dependency injection.
 */
@HiltAndroidApp
class {class_name} : Application() {{

    override fun onCreate() {{
        super.onCreate()
        // Initialize any application-wide components here
    }}
}}
'''

        return KotlinFile(
            file_name=class_name,
            package=package_name,
            relative_path=f"app/src/main/kotlin/{package_name.replace('.', '/')}",
            raw_content=content,
        )

    def _generate_main_activity(self, package_name: str, app_name: str) -> KotlinFile:
        """Generate the MainActivity."""
        content = f'''package {package_name}

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import dagger.hilt.android.AndroidEntryPoint
import {package_name}.navigation.AppNavigation
import {package_name}.core.ui.theme.AppTheme

/**
 * Main entry point Activity for {app_name}.
 */
@AndroidEntryPoint
class MainActivity : ComponentActivity() {{

    override fun onCreate(savedInstanceState: Bundle?) {{
        super.onCreate(savedInstanceState)
        setContent {{
            AppTheme {{
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {{
                    AppNavigation()
                }}
            }}
        }}
    }}
}}
'''

        return KotlinFile(
            file_name="MainActivity",
            package=package_name,
            relative_path=f"app/src/main/kotlin/{package_name.replace('.', '/')}",
            raw_content=content,
        )

    def _generate_navigation(self, package_name: str, screens: list[Any]) -> KotlinFile:
        """Generate the navigation graph."""
        screen_routes = []
        screen_composables = []

        for screen in screens[:10]:  # Limit to 10 screens
            route_name = self._to_camel_case(screen.screen_name)
            screen_name = self._to_pascal_case(screen.screen_name) + "Screen"

            screen_routes.append(f'    const val {route_name} = "{route_name}"')
            screen_composables.append(f'''        composable(Routes.{route_name}) {{
            {screen_name}()
        }}''')

        routes = "\n".join(screen_routes)
        composables = "\n".join(screen_composables)

        content = f'''package {package_name}.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import {package_name}.feature.home.HomeScreen

/**
 * Navigation routes for the application.
 */
object Routes {{
{routes}
}}

/**
 * Main navigation composable.
 */
@Composable
fun AppNavigation() {{
    val navController = rememberNavController()

    NavHost(
        navController = navController,
        startDestination = Routes.home
    ) {{
        composable(Routes.home) {{
            HomeScreen(
                onNavigate = {{ route -> navController.navigate(route) }}
            )
        }}
{composables}
    }}
}}
'''

        return KotlinFile(
            file_name="AppNavigation",
            package=f"{package_name}.navigation",
            relative_path=f"app/src/main/kotlin/{package_name.replace('.', '/')}/navigation",
            raw_content=content,
        )

    def _generate_theme(self, package_name: str) -> KotlinFile:
        """Generate the theme file."""
        content = f'''package {package_name}.core.ui.theme

import android.app.Activity
import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

private val DarkColorScheme = darkColorScheme(
    primary = Purple80,
    secondary = PurpleGrey80,
    tertiary = Pink80
)

private val LightColorScheme = lightColorScheme(
    primary = Purple40,
    secondary = PurpleGrey40,
    tertiary = Pink40
)

/**
 * Application theme composable.
 */
@Composable
fun AppTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = true,
    content: @Composable () -> Unit
) {{
    val colorScheme = when {{
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {{
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }}
        darkTheme -> DarkColorScheme
        else -> LightColorScheme
    }}

    val view = LocalView.current
    if (!view.isInEditMode) {{
        SideEffect {{
            val window = (view.context as Activity).window
            window.statusBarColor = colorScheme.primary.toArgb()
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = darkTheme
        }}
    }}

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content
    )
}}
'''

        return KotlinFile(
            file_name="Theme",
            package=f"{package_name}.core.ui.theme",
            relative_path=f"core/ui/src/main/kotlin/{package_name.replace('.', '/')}/core/ui/theme",
            raw_content=content,
        )

    def _generate_color(self, package_name: str) -> KotlinFile:
        """Generate the color file."""
        content = f'''package {package_name}.core.ui.theme

import androidx.compose.ui.graphics.Color

val Purple80 = Color(0xFFD0BCFF)
val PurpleGrey80 = Color(0xFFCCC2DC)
val Pink80 = Color(0xFFEFB8C8)

val Purple40 = Color(0xFF6650a4)
val PurpleGrey40 = Color(0xFF625b71)
val Pink40 = Color(0xFF7D5260)
'''

        return KotlinFile(
            file_name="Color",
            package=f"{package_name}.core.ui.theme",
            relative_path=f"core/ui/src/main/kotlin/{package_name.replace('.', '/')}/core/ui/theme",
            raw_content=content,
        )

    def _generate_typography(self, package_name: str) -> KotlinFile:
        """Generate the typography file."""
        content = f'''package {package_name}.core.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

val Typography = Typography(
    bodyLarge = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Normal,
        fontSize = 16.sp,
        lineHeight = 24.sp,
        letterSpacing = 0.5.sp
    ),
    titleLarge = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Normal,
        fontSize = 22.sp,
        lineHeight = 28.sp,
        letterSpacing = 0.sp
    ),
    labelSmall = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Medium,
        fontSize = 11.sp,
        lineHeight = 16.sp,
        letterSpacing = 0.5.sp
    )
)
'''

        return KotlinFile(
            file_name="Typography",
            package=f"{package_name}.core.ui.theme",
            relative_path=f"core/ui/src/main/kotlin/{package_name.replace('.', '/')}/core/ui/theme",
            raw_content=content,
        )

    def _generate_home_screen(self, package_name: str, app_name: str) -> KotlinFile:
        """Generate the home screen."""
        content = f'''package {package_name}.feature.home

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle

/**
 * Home screen composable.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    onNavigate: (String) -> Unit = {{}},
    viewModel: HomeViewModel = hiltViewModel()
) {{
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {{
            TopAppBar(
                title = {{ Text("{app_name}") }},
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer,
                    titleContentColor = MaterialTheme.colorScheme.onPrimaryContainer
                )
            )
        }}
    ) {{ paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {{
            when (val state = uiState) {{
                is HomeUiState.Loading -> {{
                    CircularProgressIndicator()
                }}
                is HomeUiState.Success -> {{
                    Text(
                        text = "Welcome to {app_name}!",
                        style = MaterialTheme.typography.headlineMedium,
                        textAlign = TextAlign.Center
                    )
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(
                        text = state.message,
                        style = MaterialTheme.typography.bodyLarge,
                        textAlign = TextAlign.Center
                    )
                }}
                is HomeUiState.Error -> {{
                    Text(
                        text = "Error: ${{state.message}}",
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.error
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Button(onClick = {{ viewModel.retry() }}) {{
                        Text("Retry")
                    }}
                }}
            }}
        }}
    }}
}}

@Preview(showBackground = true)
@Composable
private fun HomeScreenPreview() {{
    MaterialTheme {{
        HomeScreen()
    }}
}}
'''

        return KotlinFile(
            file_name="HomeScreen",
            package=f"{package_name}.feature.home",
            relative_path=f"app/src/main/kotlin/{package_name.replace('.', '/')}/feature/home",
            raw_content=content,
        )

    def _generate_home_viewmodel(self, package_name: str) -> KotlinFile:
        """Generate the home view model."""
        content = f'''package {package_name}.feature.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * UI state for the home screen.
 */
sealed interface HomeUiState {{
    data object Loading : HomeUiState
    data class Success(val message: String) : HomeUiState
    data class Error(val message: String) : HomeUiState
}}

/**
 * ViewModel for the home screen.
 */
@HiltViewModel
class HomeViewModel @Inject constructor() : ViewModel() {{

    private val _uiState = MutableStateFlow<HomeUiState>(HomeUiState.Loading)
    val uiState: StateFlow<HomeUiState> = _uiState.asStateFlow()

    init {{
        loadData()
    }}

    private fun loadData() {{
        viewModelScope.launch {{
            _uiState.value = HomeUiState.Loading
            try {{
                // Simulate loading
                delay(1000)
                _uiState.value = HomeUiState.Success(
                    message = "Your app is ready to use!"
                )
            }} catch (e: Exception) {{
                _uiState.value = HomeUiState.Error(
                    message = e.message ?: "Unknown error"
                )
            }}
        }}
    }}

    fun retry() {{
        loadData()
    }}
}}
'''

        return KotlinFile(
            file_name="HomeViewModel",
            package=f"{package_name}.feature.home",
            relative_path=f"app/src/main/kotlin/{package_name.replace('.', '/')}/feature/home",
            raw_content=content,
        )

    def _generate_manifest(self, package_name: str, app_name: str) -> ResourceFile:
        """Generate AndroidManifest.xml."""
        app_class = self._to_pascal_case(app_name) + "Application"

        content = f'''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <uses-permission android:name="android.permission.INTERNET" />

    <application
        android:name=".{app_class}"
        android:allowBackup="true"
        android:icon="@mipmap/ic_launcher"
        android:label="@string/app_name"
        android:roundIcon="@mipmap/ic_launcher_round"
        android:supportsRtl="true"
        android:theme="@style/Theme.App">

        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:label="@string/app_name"
            android:theme="@style/Theme.App">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>

    </application>

</manifest>
'''

        return ResourceFile(
            resource_type=ResourceType.XML,
            file_name="AndroidManifest.xml",
            content=content,
        )

    def _generate_strings_xml(self, app_name: str) -> ResourceFile:
        """Generate strings.xml."""
        content = f'''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">{app_name}</string>
</resources>
'''

        return ResourceFile(
            resource_type=ResourceType.VALUES,
            file_name="strings.xml",
            content=content,
        )

    def _generate_themes_xml(self) -> ResourceFile:
        """Generate themes.xml."""
        content = '''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <style name="Theme.App" parent="android:Theme.Material.Light.NoActionBar" />
</resources>
'''

        return ResourceFile(
            resource_type=ResourceType.VALUES,
            file_name="themes.xml",
            content=content,
        )

    def _to_pascal_case(self, text: str) -> str:
        """Convert text to PascalCase."""
        words = re.split(r'[\s_\-]+', text)
        return ''.join(word.capitalize() for word in words)

    def _to_camel_case(self, text: str) -> str:
        """Convert text to camelCase."""
        pascal = self._to_pascal_case(text)
        return pascal[0].lower() + pascal[1:] if pascal else ""

    async def generate(self, input_data: CodegenInput) -> ServiceResult[CodegenOutput]:
        """Generate Android application.

        Args:
            input_data: Codegen input

        Returns:
            ServiceResult containing CodegenOutput
        """
        import time

        start_time = time.perf_counter()

        try:
            logger.info("Generating Android project", run_id=input_data.run_id)

            package_name = input_data.package_name
            app_name = input_data.behavioral_spec.app_name

            # Create modules
            modules = [
                self._create_app_module(package_name),
                self._create_core_ui_module(package_name),
                self._create_core_domain_module(package_name),
                self._create_core_data_module(package_name),
            ]

            # Create project
            project = AndroidProject(
                project_name=self._to_camel_case(app_name),
                package_name=package_name,
                modules=modules,
                source_architecture_spec_id=input_data.architecture_spec.spec_id,
                source_behavioral_spec_id=input_data.behavioral_spec.spec_id,
            )

            # Generate root files
            project.root_build_gradle = self._create_root_build_gradle(project)
            project.settings_gradle = self._create_settings_gradle(project)
            project.gradle_properties = self._create_gradle_properties()

            # Generate source files
            source_files: dict[str, list[KotlinFile]] = {":app": [], ":core:ui": []}

            # App module sources
            source_files[":app"].append(self._generate_application_class(package_name, app_name))
            source_files[":app"].append(self._generate_main_activity(package_name, app_name))
            source_files[":app"].append(self._generate_navigation(package_name, input_data.behavioral_spec.screen_specs))
            source_files[":app"].append(self._generate_home_screen(package_name, app_name))
            source_files[":app"].append(self._generate_home_viewmodel(package_name))

            # Core UI sources
            source_files[":core:ui"].append(self._generate_theme(package_name))
            source_files[":core:ui"].append(self._generate_color(package_name))
            source_files[":core:ui"].append(self._generate_typography(package_name))

            project.source_files = source_files

            # Generate resource files
            resource_files: dict[str, list[ResourceFile]] = {":app": []}
            resource_files[":app"].append(self._generate_manifest(package_name, app_name))
            resource_files[":app"].append(self._generate_strings_xml(app_name))
            resource_files[":app"].append(self._generate_themes_xml())

            project.resource_files = resource_files

            # Store project
            output_dir = f"generated/{input_data.run_id}/{project.project_name}"
            await self._write_project_to_storage(project, output_dir)

            output = CodegenOutput(
                project=project,
                output_directory=output_dir,
            )

            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                "Android project generated",
                modules=len(modules),
                files=sum(len(files) for files in source_files.values()),
                duration_ms=duration_ms,
            )

            return ServiceResult.ok(output, duration_ms=duration_ms)

        except Exception as e:
            logger.error("Code generation failed", error=str(e))
            return ServiceResult.fail(str(e))

    async def _write_project_to_storage(self, project: AndroidProject, output_dir: str) -> None:
        """Write project files to storage."""
        # Root files
        await self.storage.store_text(f"{output_dir}/build.gradle.kts", project.root_build_gradle)
        await self.storage.store_text(f"{output_dir}/settings.gradle.kts", project.settings_gradle)
        await self.storage.store_text(f"{output_dir}/gradle.properties", project.gradle_properties)

        # Module build files
        for module in project.modules:
            build_content = self._create_module_build_gradle(module, project.package_name)
            await self.storage.store_text(f"{output_dir}/{module.module_path}/build.gradle.kts", build_content)

        # Source files
        for module_name, files in project.source_files.items():
            for kotlin_file in files:
                if kotlin_file.raw_content:
                    path = f"{output_dir}/{kotlin_file.relative_path}/{kotlin_file.file_name}.kt"
                    await self.storage.store_text(path, kotlin_file.raw_content)

        # Resource files
        for module_name, files in project.resource_files.items():
            module = project.get_module(module_name)
            if not module:
                continue

            for resource_file in files:
                if resource_file.file_name == "AndroidManifest.xml":
                    path = f"{output_dir}/{module.module_path}/src/main/AndroidManifest.xml"
                else:
                    path = f"{output_dir}/{module.module_path}/src/main/res/{resource_file.directory_name}/{resource_file.file_name}"
                await self.storage.store_text(path, resource_file.content)

        # Store project model
        await self.storage.store_model(f"{output_dir}/project.json", project)
