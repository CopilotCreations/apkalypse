"""
APKalypse CLI.

Command-line interface for running the APKalypse pipeline.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .core.config import get_config
from .core.logging import setup_logging

app = typer.Typer(
    name="APKalypse",
    help="Automated APK behavioral analysis and greenfield app generation",
    add_completion=False,
)

console = Console()


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        from . import __version__
        console.print(f"APKalypse v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """APKalypse: APK to greenfield Android app pipeline."""
    pass


@app.command()
def run(
    apk_path: Path = typer.Argument(
        ...,
        help="Path to the APK file to analyze",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
    app_name: str = typer.Option(
        ...,
        "--name",
        "-n",
        help="Name for the generated application",
    ),
    package_name: str = typer.Option(
        ...,
        "--package",
        "-p",
        help="Package name for generated code (e.g., com.example.myapp)",
    ),
    play_store_url: Optional[str] = typer.Option(
        None,
        "--play-store",
        help="Google Play Store URL for additional metadata",
    ),
    output_dir: Path = typer.Option(
        Path("./output"),
        "--output",
        "-o",
        help="Output directory for generated project",
    ),
    exploration_time: int = typer.Option(
        300,
        "--exploration-time",
        "-t",
        help="Dynamic analysis exploration time in seconds",
    ),
    skip_dynamic: bool = typer.Option(
        False,
        "--skip-dynamic",
        help="Skip dynamic analysis (use static-only mode)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Enable verbose logging",
    ),
) -> None:
    """Run the complete APKalypse pipeline.

    Analyzes an APK file, extracts behavioral specifications,
    and generates a greenfield Android application.
    """
    # Setup
    config = get_config()
    if verbose:
        config.log_level = "DEBUG"
    setup_logging(config)

    console.print(Panel.fit(
        "[bold blue]APKalypse[/bold blue]\n"
        "APK → Behavioral Spec → Greenfield Android App",
        border_style="blue",
    ))

    console.print(f"\n[bold]Input APK:[/bold] {apk_path}")
    console.print(f"[bold]App Name:[/bold] {app_name}")
    console.print(f"[bold]Package:[/bold] {package_name}")
    console.print(f"[bold]Output:[/bold] {output_dir}\n")

    # Run pipeline
    async def run_async() -> None:
        from .orchestration import run_pipeline

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Running pipeline...", total=None)

            result = await run_pipeline(
                apk_path=apk_path,
                app_name=app_name,
                package_name=package_name,
                play_store_url=play_store_url,
                exploration_time=exploration_time,
                skip_dynamic_analysis=skip_dynamic,
            )

            progress.update(task, completed=True)

        # Display results
        if result.success:
            console.print("\n[bold green]✓ Pipeline completed successfully![/bold green]\n")

            # Summary table
            table = Table(title="Pipeline Results")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Run ID", result.run_id)
            table.add_row("Duration", f"{(result.completed_at - result.started_at).total_seconds():.1f}s")
            table.add_row("Screens Found", str(result.behavior_model.total_screens if result.behavior_model else 0))
            table.add_row("Requirements", str(len(result.behavioral_spec.functional_requirements) if result.behavioral_spec else 0))
            table.add_row("Modules", str(len(result.architecture_spec.modules) if result.architecture_spec else 0))
            table.add_row("Parity Score", f"{result.parity_score:.1%}")
            table.add_row("Parity Check", "[green]PASSED[/green]" if result.parity_passed else "[red]FAILED[/red]")
            table.add_row("Compliance", "[green]PASSED[/green]" if result.compliance_passed else "[red]FAILED[/red]")

            console.print(table)

            console.print(f"\n[bold]Generated project:[/bold] {result.output_directory}")
            console.print("\nNext steps:")
            console.print("  1. cd " + result.output_directory)
            console.print("  2. ./gradlew build")
            console.print("  3. ./gradlew installDebug")

        else:
            console.print(f"\n[bold red]✗ Pipeline failed![/bold red]")
            console.print(f"Error: {result.error}")
            if result.failed_stage:
                console.print(f"Failed at: {result.failed_stage}")
            raise typer.Exit(1)

    asyncio.run(run_async())


@app.command()
def analyze(
    apk_path: Path = typer.Argument(
        ...,
        help="Path to the APK file to analyze",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
    output: Path = typer.Option(
        Path("./analysis"),
        "--output",
        "-o",
        help="Output directory for analysis results",
    ),
    skip_dynamic: bool = typer.Option(
        False,
        "--skip-dynamic",
        help="Skip dynamic analysis",
    ),
) -> None:
    """Analyze an APK and extract behavioral model (without code generation)."""
    setup_logging(get_config())

    console.print(f"[bold]Analyzing:[/bold] {apk_path}")

    async def run_async() -> None:
        from .storage import LocalStorageBackend
        from .services.ingestion import IngestionService
        from .services.ingestion.service import IngestionInput
        from .services.static_analysis import StaticAnalysisService
        from .services.static_analysis.service import StaticAnalysisInput

        storage = LocalStorageBackend(output)

        # Ingest
        console.print("  [dim]→ Ingesting APK...[/dim]")
        ingestion = IngestionService(storage)
        result = await ingestion.ingest(IngestionInput(apk_path=apk_path))

        if not result.success:
            console.print(f"[red]Ingestion failed: {result.error}[/red]")
            raise typer.Exit(1)

        # Static analysis
        console.print("  [dim]→ Running static analysis...[/dim]")
        static = StaticAnalysisService(storage)
        static_result = await static.analyze(StaticAnalysisInput(
            apk_path=result.data.normalized_apk_path,
            apk_metadata=result.data.apk_metadata,
        ))

        if not static_result.success:
            console.print(f"[red]Static analysis failed: {static_result.error}[/red]")
            raise typer.Exit(1)

        # Display results
        manifest = static_result.data.manifest
        console.print("\n[bold green]✓ Analysis complete![/bold green]\n")

        table = Table(title="APK Analysis")
        table.add_column("Property", style="cyan")
        table.add_column("Value")

        table.add_row("Package", manifest.package_name)
        table.add_row("Version", f"{manifest.version_name} ({manifest.version_code})")
        table.add_row("Min SDK", str(manifest.min_sdk_version))
        table.add_row("Target SDK", str(manifest.target_sdk_version))
        table.add_row("Activities", str(len(manifest.activities)))
        table.add_row("Services", str(len(manifest.services)))
        table.add_row("Permissions", str(len(manifest.permissions)))
        table.add_row("Detected Frameworks", ", ".join(static_result.data.detected_frameworks) or "None")

        console.print(table)

        if manifest.activities:
            console.print("\n[bold]Activities:[/bold]")
            for activity in manifest.activities[:10]:
                launcher = " [launcher]" if activity.is_launcher else ""
                console.print(f"  • {activity.simple_name}{launcher}")

    asyncio.run(run_async())


@app.command()
def config(
    show: bool = typer.Option(
        True,
        "--show",
        help="Show current configuration",
    ),
) -> None:
    """Show or manage configuration."""
    cfg = get_config()

    table = Table(title="Current Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value")

    table.add_row("Log Level", cfg.log_level)
    table.add_row("Storage Backend", cfg.storage.backend)
    table.add_row("Storage Path", str(cfg.storage.base_path))
    table.add_row("Agent Provider", cfg.agent.provider)
    table.add_row("Agent Model", cfg.agent.model)
    table.add_row("Emulator AVD", cfg.emulator.avd_name)
    table.add_row("Emulator API", str(cfg.emulator.api_level))
    table.add_row("Emulator Headless", str(cfg.emulator.headless))
    table.add_row("Compliance Strict", str(cfg.compliance.block_on_violation))
    table.add_row("Similarity Threshold", f"{cfg.compliance.max_source_similarity_threshold:.0%}")

    console.print(table)

    console.print("\n[dim]Configure via environment variables:[/dim]")
    console.print("  B2B_LOG_LEVEL, B2B_AGENT_PROVIDER, B2B_AGENT_MODEL")
    console.print("  OPENAI_API_KEY, ANTHROPIC_API_KEY")


@app.command()
def verify(
    project_dir: Path = typer.Argument(
        ...,
        help="Path to generated project directory",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
) -> None:
    """Verify a generated project can build."""
    console.print(f"[bold]Verifying project:[/bold] {project_dir}")

    import subprocess

    # Check for build.gradle.kts
    build_file = project_dir / "build.gradle.kts"
    if not build_file.exists():
        console.print("[red]Error: No build.gradle.kts found[/red]")
        raise typer.Exit(1)

    # Try to run gradle
    gradlew = project_dir / "gradlew"
    if not gradlew.exists():
        console.print("[yellow]Warning: No gradle wrapper found[/yellow]")
        console.print("Run 'gradle wrapper' to generate it")
        raise typer.Exit(1)

    console.print("  [dim]→ Running gradle check...[/dim]")

    try:
        result = subprocess.run(
            [str(gradlew), "check", "--dry-run"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            console.print("[bold green]✓ Project structure is valid![/bold green]")
        else:
            console.print("[red]Build check failed[/red]")
            console.print(result.stderr)
            raise typer.Exit(1)

    except subprocess.TimeoutExpired:
        console.print("[yellow]Build check timed out[/yellow]")
    except FileNotFoundError:
        console.print("[yellow]Gradle not available for verification[/yellow]")


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
