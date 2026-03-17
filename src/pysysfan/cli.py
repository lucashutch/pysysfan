"""pysysfan CLI entry point."""

import logging

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from pysysfan import __version__

# Ensure stdout/stderr use UTF-8 with a replace policy where supported so
# printing Unicode glyphs (e.g. check marks) does not raise a
# UnicodeEncodeError on consoles using legacy encodings (common on Windows).
import sys

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    # Best-effort only; if reconfigure isn't available or fails, fall back.
    pass

console = Console()


def check_admin():
    """Check if we're running with Administrator privileges."""
    try:
        import ctypes

        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def _print_version(ctx, _param, value):
    if not value or ctx.resilient_parsing:
        return
    click.echo(f"pysysfan, version {__version__}")
    ctx.exit()


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "-v",
    "--version",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=_print_version,
    help="Show the version and exit.",
)
@click.option("--verbose", is_flag=True, help="Enable verbose logging.")
def main(verbose: bool):
    """pysysfan — Python fan control daemon for Windows.

    Controls system fan speeds based on temperature curves using
    LibreHardwareMonitor.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# ── Scan command ──────────────────────────────────────────────────────


@main.command()
@click.option(
    "--type",
    "-t",
    "sensor_type",
    type=click.Choice(["all", "temp", "fan", "control"], case_sensitive=False),
    default="all",
    help="Filter by sensor type.",
)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def scan(sensor_type: str, as_json: bool):
    """Scan and display all detected hardware sensors.

    Requires administrator privileges and PawnIO driver.
    """
    if not check_admin():
        console.print(
            "[bold yellow]⚠ Warning:[/] Not running as Administrator. "
            "Hardware access may fail.\n"
            "  Run PowerShell as Admin and try again."
        )

    from pysysfan.hardware import HardwareManager

    try:
        with HardwareManager() as hw:
            result = hw.scan()
    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/] {e}")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[bold red]Error accessing hardware:[/] {e}")
        console.print(
            "\n[dim]Common causes:[/]\n"
            "  • Not running as Administrator\n"
            "  • PawnIO driver not installed (winget install PawnIO)\n"
            "  • LibreHardwareMonitorLib.dll not found (pysysfan lhm download)\n"
        )
        raise SystemExit(1)

    from pysysfan.config import DEFAULT_CONFIG_DIR
    import json

    scan_data = _get_scan_dict(result, sensor_type)

    # Always save the JSON dump to ~/.pysysfan/scan.json
    scan_dir = DEFAULT_CONFIG_DIR
    scan_dir.mkdir(parents=True, exist_ok=True)
    scan_file = scan_dir / "scan.json"
    try:
        scan_file.write_text(json.dumps(scan_data, indent=2))
        if not as_json:
            console.print(f"[dim]Saved scan results to {scan_file}[/]")
    except Exception as e:
        if not as_json:
            console.print(f"[yellow]Failed to save {scan_file}: {e}[/]")

    if as_json:
        click.echo(json.dumps(scan_data, indent=2))
    else:
        _output_scan_tables(result, sensor_type)


def _get_scan_dict(result, sensor_type: str) -> dict:
    """Return scan results as a dictionary."""

    data = {}
    if sensor_type in ("all", "temp"):
        data["temperatures"] = [
            {
                "hardware": s.hardware_name,
                "sensor": s.sensor_name,
                "value": s.value,
                "identifier": s.identifier,
            }
            for s in result.temperatures
        ]
    if sensor_type in ("all", "fan"):
        data["fans"] = [
            {
                "hardware": s.hardware_name,
                "sensor": s.sensor_name,
                "value": s.value,
                "identifier": s.identifier,
            }
            for s in result.fans
        ]
    if sensor_type in ("all", "control"):
        data["controls"] = [
            {
                "hardware": c.hardware_name,
                "sensor": c.sensor_name,
                "value": c.current_value,
                "identifier": c.identifier,
                "controllable": c.has_control,
            }
            for c in result.controls
        ]

    return data


def _output_scan_tables(result, sensor_type: str):
    """Output scan results as rich tables."""
    if sensor_type in ("all", "temp"):
        table = Table(
            title="🌡️  Temperature Sensors",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Hardware", style="dim")
        table.add_column("Sensor")
        table.add_column("Value", justify="right")
        table.add_column("Identifier", style="dim")

        for s in result.temperatures:
            value_str = f"{s.value:.1f}°C" if s.value is not None else "N/A"
            table.add_row(s.hardware_name, s.sensor_name, value_str, s.identifier)

        console.print(table)
        console.print()

    if sensor_type in ("all", "fan"):
        table = Table(
            title="🌀  Fan Speeds",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Hardware", style="dim")
        table.add_column("Sensor")
        table.add_column("RPM", justify="right")
        table.add_column("Identifier", style="dim")

        for s in result.fans:
            value_str = f"{s.value:.0f}" if s.value is not None else "N/A"
            table.add_row(s.hardware_name, s.sensor_name, value_str, s.identifier)

        console.print(table)
        console.print()

    if sensor_type in ("all", "control"):
        table = Table(
            title="🎛️  Fan Controls",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Hardware", style="dim")
        table.add_column("Control")
        table.add_column("Current %", justify="right")
        table.add_column("Controllable", justify="center")
        table.add_column("Identifier", style="dim")

        for c in result.controls:
            value_str = (
                f"{c.current_value:.1f}%" if c.current_value is not None else "N/A"
            )
            ctrl_str = "[green]✓[/]" if c.has_control else "[red]✗[/]"
            table.add_row(
                c.hardware_name, c.sensor_name, value_str, ctrl_str, c.identifier
            )

        console.print(table)
        console.print()

    # Summary
    summary = Text()
    summary.append("Found: ", style="bold")
    summary.append(f"{len(result.temperatures)} temps", style="yellow")
    summary.append(", ")
    summary.append(f"{len(result.fans)} fans", style="cyan")
    summary.append(", ")
    controllable = sum(1 for c in result.controls if c.has_control)
    summary.append(
        f"{controllable}/{len(result.controls)} controllable outputs", style="green"
    )
    console.print(Panel(summary, title="Summary"))


# ── Config subcommand group ───────────────────────────────────────────


def _generate_example_config(config_path):
    """Generate example config with placeholder sensor IDs."""

    # Try to scan for real sensor IDs to use as examples
    temp_ids: dict[str, str] = {}
    control_ids: dict[str, str] = {}

    try:
        from pysysfan.hardware import HardwareManager

        with HardwareManager() as hw:
            result = hw.scan()
        for s in result.temperatures:
            key = s.hardware_name.replace(" ", "_").lower()
            temp_ids[key] = s.identifier
        for c in result.controls:
            if c.has_control:
                key = c.sensor_name.replace(" ", "_").lower()
                control_ids[key] = c.identifier
    except Exception:
        pass  # Fall back to placeholder IDs if scan fails

    # Build a commented-up example config manually so YAML has nice comments
    first_temp = next(iter(temp_ids.values()), "/amdcpu/0/temperature/0")
    first_ctrl = next(iter(control_ids.values()), "/motherboard/control/0")

    config_path.write_text(f"""\
# pysysfan Configuration
# Run 'pysysfan scan' to discover sensor identifiers for your hardware.

general:
    poll_interval: 1  # seconds between control updates

fans:
  # Example: map a fan header to temperature sources and curve
  cpu_fan:
    # Sensor identifier from 'pysysfan scan --type control'
    fan_id: "{first_ctrl}"
    # Which temperature curve to use (see 'curves' below)
    curve: balanced
    # Temperature sensor identifiers from 'pysysfan scan --type temp'
    # You can specify multiple sensors - they will be aggregated
    temp_ids:
      - "{first_temp}"
    # How to aggregate multiple temperature sensors
    # Options: max (hottest), min (coolest), average, median
    aggregation: max

curves:
  silent:
    hysteresis: 3
    points:
      - [30, 20]  # 30°C -> 20%
      - [50, 40]
      - [70, 70]
      - [85, 100]

  balanced:
    hysteresis: 3
    points:
      - [30, 30]
      - [60, 60]
      - [75, 85]
      - [85, 100]

  performance:
    hysteresis: 2
    points:
      - [30, 50]
      - [50, 70]
      - [65, 90]
      - [75, 100]
""")
    console.print(f"[bold green]Config written:[/] {config_path}")
    if temp_ids or control_ids:
        console.print("[dim]Sensor identifiers were populated from a live scan.[/]")
    else:
        console.print(
            "[yellow]Tip:[/] Run as Administrator then [bold]pysysfan scan[/] to find "
            "your actual sensor identifiers."
        )


def _generate_auto_config(config_path):
    """Auto-detect hardware and generate config."""

    console.print("[bold]Scanning hardware...[/]")

    try:
        from pysysfan.hardware import HardwareManager
        from pysysfan.config import auto_populate_config

        with HardwareManager() as hw:
            result = hw.scan()
    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/] {e}")
        console.print(
            "\n[dim]Run [bold]pysysfan lhm download[/] to install LibreHardwareMonitor."
        )
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[bold red]Error accessing hardware:[/] {e}")
        console.print(
            "\n[dim]Common causes:[/]\n"
            "  • Not running as Administrator\n"
            "  • PawnIO driver not installed (winget install PawnIO)\n"
            "  • LibreHardwareMonitorLib.dll not found (pysysfan lhm download)\n"
        )
        console.print(
            "[yellow]Falling back to example config with placeholder IDs...[/]"
        )
        _generate_example_config(config_path)
        return

    # Check if we found any fans
    if not result.controls:
        console.print(
            "[yellow]Warning:[/] No fan sensors detected.\n"
            "  Generating example config instead."
        )
        _generate_example_config(config_path)
        return

    # Check if we found temperature sensors
    if not result.temperatures:
        console.print(
            "[red]Error:[/] No temperature sensors found.\n"
            "  Cannot create config without temperature sources."
        )
        raise SystemExit(1)

    # Generate config
    try:
        config = auto_populate_config(result)
    except ValueError as e:
        console.print(f"[red]Error:[/] {e}")
        raise SystemExit(1)

    # Count controllable vs read-only fans
    controllable = sum(1 for c in result.controls if c.has_control)
    total_fans = len(result.controls)

    # Generate YAML with comments
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    yaml_content = f"""# pysysfan Configuration (Auto-generated)
# Generated on: {timestamp}
# Detected {total_fans} fans ({controllable} controllable, {total_fans - controllable} read-only)
# All fans mapped to CPU temperature sensor(s)

general:
    poll_interval: 1

fans:
"""

    for name, fan in config.fans.items():
        control_info = next(
            (c for c in result.controls if c.identifier == fan.fan_id), None
        )
        is_controllable = control_info.has_control if control_info else False
        status = (
            "Controllable" if is_controllable else "Read Only (no control available)"
        )

        # Build temp_ids list for YAML
        temp_ids_yaml = "\n".join(f'      - "{tid}"' for tid in fan.temp_ids)
        multi_sensor_note = ""
        if len(fan.temp_ids) > 1:
            multi_sensor_note = f"\n    # Using {len(fan.temp_ids)} temperature sensors with '{fan.aggregation}' aggregation"

        yaml_content += f"""  # {fan.header_name} - {status}{multi_sensor_note}
  {name}:
    fan_id: "{fan.fan_id}"
    curve: {fan.curve}
    temp_ids:
{temp_ids_yaml}
    aggregation: {fan.aggregation}
    header_name: "{fan.header_name}"

"""

    yaml_content += """curves:
  # Preset curves - customize as needed
  silent:
    hysteresis: 3
    points:
      - [30, 20]  # 30°C -> 20%
      - [50, 40]
      - [70, 70]
      - [85, 100]

  balanced:  # Default curve
    hysteresis: 3
    points:
      - [30, 30]
      - [60, 60]
      - [75, 85]
      - [85, 100]

  performance:
    hysteresis: 2
    points:
      - [30, 50]
      - [50, 70]
      - [65, 90]
      - [75, 100]

# Tips:
# - Edit temp_ids to use multiple temperature sensors (e.g., all CPU cores)
# - Change aggregation to 'average' for smoother fan curves
# - Use 'max' aggregation to respond to the hottest sensor (recommended for CPU)
# - Change curve to 'silent' or 'performance' for individual fans
# - Read-only fans will be monitored but cannot be controlled
# - Run 'pysysfan scan' to see all available sensors
"""

    config_path.write_text(yaml_content)
    console.print(f"[bold green]Config written:[/] {config_path}")
    console.print(
        f"  [cyan]Fans detected:[/] {total_fans} ({controllable} controllable)"
    )

    if total_fans - controllable > 0:
        console.print(
            f"  [yellow]⚠[/]  {total_fans - controllable} fans are read-only (monitoring only)"
        )

    console.print(
        "\n[dim]💡 Tip: Edit the config file to customize curves and temperature sources[/]"
    )


@main.group()
@click.option(
    "--path",
    "-p",
    type=click.Path(),
    default=None,
    envvar="PYSYSFAN_CONFIG",
    help="Path to config file. Default: ~/.pysysfan/config.yaml",
)
@click.pass_context
def config(ctx, path):
    """Manage pysysfan configuration."""
    from pysysfan.config import DEFAULT_CONFIG_PATH
    from pathlib import Path

    ctx.ensure_object(dict)
    ctx.obj["config_path"] = Path(path) if path else DEFAULT_CONFIG_PATH


@config.command("init")
@click.option("--force", is_flag=True, help="Overwrite existing config file.")
@click.option(
    "--example", is_flag=True, help="Generate example config with placeholder IDs."
)
@click.pass_context
def config_init(ctx, force: bool, example: bool):
    """Generate a configuration file.

    By default, auto-detects all fans and maps them to CPU temperature.
    Use --example to generate a starter config with placeholder IDs instead.
    """
    from pathlib import Path

    config_path: Path = ctx.obj["config_path"]

    if config_path.is_file() and not force:
        console.print(
            f"[yellow]Config already exists:[/] {config_path}\n"
            "Use --force to overwrite."
        )
        raise SystemExit(0)

    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Example mode: generate placeholder config
    if example:
        _generate_example_config(config_path)
        return

    # Auto mode: detect hardware and generate config
    _generate_auto_config(config_path)


@config.command("validate")
@click.pass_context
def config_validate(ctx):
    """Validate the config file and check sensors exist on this hardware."""
    from pathlib import Path
    from pysysfan.config import Config

    config_path: Path = ctx.obj["config_path"]

    if not config_path.is_file():
        console.print(
            f"[red]Config not found:[/] {config_path}. Run 'pysysfan config init' first."
        )
        raise SystemExit(1)

    # Load and parse config
    try:
        cfg = Config.load(config_path)
    except Exception as e:
        console.print(f"[red]Config parse error:[/] {e}")
        raise SystemExit(1)

    console.print(f"[bold green]Config OK:[/] {config_path}")
    console.print(f"  Fans defined   : {len(cfg.fans)}")
    console.print(f"  Curves defined : {len(cfg.curves)}")
    console.print(f"  Poll interval  : {cfg.poll_interval}s")

    # Validate curve references and aggregation methods
    from pysysfan.curves import parse_curve, InvalidCurveError
    from pysysfan.temperature import get_valid_aggregation_methods

    errors = []
    valid_aggregations = get_valid_aggregation_methods()
    for fan_name, fan in cfg.fans.items():
        # Check if it's a special curve first
        try:
            special = parse_curve(fan.curve)
            if special is None and fan.curve not in cfg.curves:
                # Not a special curve and not in config
                errors.append(
                    f"Fan '{fan_name}' references unknown curve '{fan.curve}'"
                )
        except InvalidCurveError as e:
            errors.append(f"Fan '{fan_name}' has invalid curve '{fan.curve}': {e}")

        # Validate aggregation method
        if fan.aggregation not in valid_aggregations:
            errors.append(
                f"Fan '{fan_name}' has invalid aggregation '{fan.aggregation}'. "
                f"Valid options: {valid_aggregations}"
            )

        # Validate temp_ids list
        if not fan.temp_ids:
            errors.append(f"Fan '{fan_name}' has no temperature sensors configured")

    if errors:
        for e in errors:
            console.print(f"  [red]✗[/] {e}")
        raise SystemExit(1)

    # Optionally verify sensor IDs against live hardware
    try:
        from pysysfan.hardware import HardwareManager

        with HardwareManager() as hw:
            result = hw.scan()
        all_ids = {s.identifier for s in result.all_sensors}
        all_ids |= {c.identifier for c in result.controls}

        for fan_name, fan in cfg.fans.items():
            # Check all temperature sensors
            missing_temps = [tid for tid in fan.temp_ids if tid not in all_ids]
            if missing_temps:
                if len(missing_temps) == len(fan.temp_ids):
                    console.print(
                        f"  [yellow]⚠[/]  Fan '{fan_name}': none of the temperature sensors found"
                    )
                else:
                    console.print(
                        f"  [yellow]⚠[/]  Fan '{fan_name}': {len(missing_temps)}/{len(fan.temp_ids)} "
                        f"temperature sensors not found (aggregation: {fan.aggregation})"
                    )
            if fan.fan_id not in all_ids:
                console.print(
                    f"  [yellow]⚠[/]  Fan '{fan_name}': fan_id '{fan.fan_id}' not found in current hardware scan"
                )
        console.print("  [green]Hardware check complete.[/]")
    except Exception:
        console.print(
            "  [dim]Hardware check skipped (run as admin for full validation).[/]"
        )


@config.command("show")
@click.pass_context
def config_show(ctx):
    """Display the current config file contents."""
    from pathlib import Path

    config_path: Path = ctx.obj["config_path"]

    if not config_path.is_file():
        console.print(
            f"[red]Config not found:[/] {config_path}. Run 'pysysfan config init' first."
        )
        raise SystemExit(1)

    raw = config_path.read_text()
    console.print(f"[bold]Config:[/] {config_path}\n")
    # Use rich syntax highlighting
    from rich.syntax import Syntax

    console.print(Syntax(raw, "yaml", theme="monokai", line_numbers=True))


@config.command("reload")
@click.pass_context
def config_reload(ctx):
    """Validate and reload the configuration file.

    Checks for syntax errors and validates all fan references.
    Reports any configuration issues without applying changes.
    """
    from pathlib import Path
    from pysysfan.config import Config
    from pysysfan.curves import parse_curve, InvalidCurveError

    config_path: Path = ctx.obj["config_path"]

    if not config_path.is_file():
        console.print(
            f"[red]Config not found:[/] {config_path}. Run 'pysysfan config init' first."
        )
        raise SystemExit(1)

    # Load and parse config
    try:
        cfg = Config.load(config_path)
    except Exception as e:
        console.print(f"[red]Config parse error:[/] {e}")
        raise SystemExit(1)

    console.print(f"[bold green]Config reloaded successfully:[/] {config_path}")
    console.print(f"  Fans defined   : {len(cfg.fans)}")
    console.print(f"  Curves defined : {len(cfg.curves)}")
    console.print(f"  Poll interval  : {cfg.poll_interval}s")

    # Validate curve references and aggregation methods
    from pysysfan.temperature import get_valid_aggregation_methods

    errors = []
    valid_aggregations = get_valid_aggregation_methods()
    for fan_name, fan in cfg.fans.items():
        try:
            special = parse_curve(fan.curve)
            if special is None and fan.curve not in cfg.curves:
                errors.append(
                    f"Fan '{fan_name}' references unknown curve '{fan.curve}'"
                )
        except InvalidCurveError as e:
            errors.append(f"Fan '{fan_name}' has invalid curve '{fan.curve}': {e}")

        # Validate aggregation method
        if fan.aggregation not in valid_aggregations:
            errors.append(
                f"Fan '{fan_name}' has invalid aggregation '{fan.aggregation}'. "
                f"Valid options: {valid_aggregations}"
            )

        # Validate temp_ids list
        if not fan.temp_ids:
            errors.append(f"Fan '{fan_name}' has no temperature sensors configured")

    if errors:
        console.print("\n[red]Validation errors found:[/]")
        for error in errors:
            console.print(f"  [red]-[/] {error}")
        raise SystemExit(1)

    console.print("\n[green]All fan references are valid.[/]")
    console.print(
        "[dim]Note: If the daemon is running, the new configuration "
        "will be applied on the next poll cycle.[/]"
    )


# ── Run command ───────────────────────────────────────────────────────


@main.command()
@click.option(
    "--once",
    is_flag=True,
    help="Run a single control pass then exit (useful for testing).",
)
@click.option(
    "--config",
    "-c",
    "config_path",
    type=click.Path(exists=False),
    default=None,
    envvar="PYSYSFAN_CONFIG",
    help="Path to config file. Default: ~/.pysysfan/config.yaml",
)
def run(
    once: bool,
    config_path: str | None,
):
    """Start the fan control daemon.

    Requires administrator privileges and PawnIO driver.
    """
    from pathlib import Path
    from pysysfan.config import DEFAULT_CONFIG_PATH
    from pysysfan.daemon import FanDaemon

    if not check_admin():
        console.print(
            "[bold yellow]⚠ Warning:[/] Not running as Administrator.\n"
            "  Motherboard sensors and fan controls require admin privileges.\n"
            "  Re-launch in an elevated PowerShell for full functionality."
        )

    cfg_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH

    if not cfg_path.is_file():
        console.print(
            f"[red]Config not found:[/] {cfg_path}\n"
            "Run [bold]pysysfan config init[/] first."
        )
        raise SystemExit(1)

    daemon = FanDaemon(config_path=cfg_path)

    if once:
        console.print("[bold]Running single control pass...[/]")
        try:
            applied = daemon.run_once()
            if applied:
                for fan, pct in applied.items():
                    console.print(f"  [green]✓[/] {fan}: set to {pct:.1f}%")
            else:
                console.print(
                    "[yellow]No fans were controlled.[/] Check sensor IDs in config."
                )
        except Exception as e:
            console.print(f"[red]Error:[/] {e}")
            raise SystemExit(1)
    else:
        console.print(f"[bold green]Starting pysysfan daemon[/] (config: {cfg_path})")
        console.print("Press Ctrl+C to stop and restore BIOS fan control.\n")
        try:
            daemon.run()
        except KeyboardInterrupt:
            pass  # daemon.run() already handles cleanup
        except Exception as e:
            console.print(f"[red]Daemon error:[/] {e}")
            raise SystemExit(1)


# ── Service subcommand group ──────────────────────────────────────────


@main.group()
def service():
    """Manage pysysfan as a Windows service via Task Scheduler."""
    pass


def _require_service_admin(action: str) -> None:
    """Exit when a service action requires Administrator privileges."""
    if check_admin():
        return

    console.print(f"[red]Error:[/] {action} requires Administrator privileges.")
    raise SystemExit(1)


@service.command("install")
@click.option(
    "--config",
    "-c",
    "config_path",
    type=click.Path(),
    default=None,
    help="Config file path to pass to the daemon. Default: ~/.pysysfan/config.yaml",
)
def service_install(config_path: str | None):
    """Install pysysfan as a startup service.

    Creates a Windows Task Scheduler task that runs at system startup.
    """
    from pysysfan.platforms import windows_service

    _require_service_admin("Installing a startup service")

    try:
        windows_service.install_task(config_path=config_path)
        console.print("[bold green]✓ Startup task installed.[/]")
        console.print("  pysysfan will now start automatically at boot.")
        console.print("  Use [bold]pysysfan service status[/] to check.")
    except Exception as e:
        console.print(f"[red]Failed to install service:[/] {e}")
        raise SystemExit(1)


@service.command("uninstall")
def service_uninstall():
    """Remove the pysysfan startup service."""
    from pysysfan.platforms import windows_service

    _require_service_admin("Removing a startup service")

    try:
        windows_service.uninstall_task()
        console.print("[bold green]✓ Startup service removed.[/]")
    except Exception as e:
        console.print(f"[red]Failed to remove service:[/] {e}")
        raise SystemExit(1)


@service.command("enable")
def service_enable():
    """Enable the pysysfan startup service."""
    from pysysfan.platforms import windows_service

    _require_service_admin("Enabling the startup service")

    try:
        windows_service.enable_task()
        console.print("[bold green]✓ Startup service enabled.[/]")
    except Exception as e:
        console.print(f"[red]Failed to enable service:[/] {e}")
        raise SystemExit(1)


@service.command("disable")
def service_disable():
    """Disable the pysysfan startup service."""
    from pysysfan.platforms import windows_service

    _require_service_admin("Disabling the startup service")

    try:
        windows_service.disable_task()
        console.print("[bold green]✓ Startup service disabled.[/]")
    except Exception as e:
        console.print(f"[red]Failed to disable service:[/] {e}")
        raise SystemExit(1)


@service.command("start")
def service_start():
    """Start the pysysfan startup service immediately."""
    from pysysfan.platforms import windows_service

    _require_service_admin("Starting the startup service")

    try:
        windows_service.start_task()
        console.print("[bold green]✓ Startup service started.[/]")
    except Exception as e:
        console.print(f"[red]Failed to start service:[/] {e}")
        raise SystemExit(1)


@service.command("stop")
def service_stop():
    """Stop the pysysfan startup service if it is running."""
    from pysysfan.platforms import windows_service

    _require_service_admin("Stopping the startup service")

    try:
        windows_service.stop_task()
        console.print("[bold green]✓ Startup service stopped.[/]")
    except Exception as e:
        console.print(f"[red]Failed to stop service:[/] {e}")
        raise SystemExit(1)


@service.command("restart")
def service_restart():
    """Restart the pysysfan startup service."""
    import time
    from pysysfan.platforms import windows_service

    _require_service_admin("Restarting the startup service")

    try:
        windows_service.stop_task()
        time.sleep(1.0)
        windows_service.start_task()
        console.print("[bold green]✓ Startup service restarted.[/]")
    except Exception as e:
        console.print(f"[red]Failed to restart service:[/] {e}")
        raise SystemExit(1)


@service.command("status")
def service_status():
    """Check whether the pysysfan service is installed and running."""
    from pysysfan.platforms import windows_service

    status = windows_service.get_task_status()
    if status is None:
        console.print(
            "[yellow]Task not installed.[/] Run [bold]pysysfan service install[/]."
        )
    else:
        console.print(f"[bold]Task status:[/] {status}")


@service.command("clean")
def service_clean():
    """Remove all pysysfan service artefacts for a clean-slate reinstall.

    Kills running processes, deletes the scheduled task, and removes
    state/history/log files.
    """
    from pysysfan.platforms import windows_service

    _require_service_admin("Cleaning service artefacts")

    messages = windows_service.clean_all()
    for msg in messages:
        console.print(f"  {msg}")
    console.print("[bold green]✓ Service clean complete.[/]")


# ── Update subcommand group ──────────────────────────────────────────


@main.group()
def update():
    """Check for and apply pysysfan updates."""
    pass


@update.command("check")
def update_check():
    """Check if a newer version of pysysfan is available."""
    from pysysfan.updater import check_for_update

    try:
        info = check_for_update()
    except Exception as e:
        console.print(f"[red]Error checking for updates:[/] {e}")
        raise SystemExit(1)

    console.print(f"  Installed version : [bold]{info.current_version}[/]")
    console.print(f"  Latest version    : [bold]{info.latest_version}[/]")

    if info.available:
        console.print(
            "\n[bold green]✓ Update available![/]  Run [bold]pysysfan update apply[/] to upgrade."
        )
        if info.release_url:
            console.print(f"  Release: {info.release_url}")
    else:
        console.print("\n[dim]You are running the latest version.[/]")


@update.command("apply")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
def update_apply(yes: bool):
    """Download and install the latest version of pysysfan."""
    from pysysfan.updater import check_for_update, perform_update

    try:
        info = check_for_update()
    except Exception as e:
        console.print(f"[red]Error checking for updates:[/] {e}")
        raise SystemExit(1)

    if not info.available:
        console.print(f"[dim]Already up-to-date ({info.current_version}).[/]")
        return

    console.print(
        f"  Upgrade: [bold]{info.current_version}[/] → [bold green]{info.latest_version}[/]"
    )
    if not yes:
        click.confirm("  Proceed with update?", abort=True)

    try:
        console.print(f"\n  Installing {info.latest_version}...")
        perform_update(info.latest_version)
        console.print(
            f"[bold green]✓ pysysfan updated to {info.latest_version}.[/]\n"
            "  Restart the daemon/service for the new version to take effect."
        )
    except Exception as e:
        console.print(f"[red]Update failed:[/] {e}")
        raise SystemExit(1)


@update.command("auto")
@click.argument("state", type=click.Choice(["on", "off"], case_sensitive=False))
def update_auto(state: str):
    """Enable or disable automatic update checks on daemon startup.

    STATE must be 'on' or 'off'.
    """
    from pysysfan.config import Config, DEFAULT_CONFIG_PATH

    config_path = DEFAULT_CONFIG_PATH
    if not config_path.is_file():
        console.print(
            f"[red]Config not found:[/] {config_path}. Run 'pysysfan config init' first."
        )
        raise SystemExit(1)

    cfg = Config.load(config_path)
    cfg.update.auto_check = state.lower() == "on"
    cfg.save(config_path)

    label = "[green]enabled[/]" if cfg.update.auto_check else "[yellow]disabled[/]"
    console.print(f"  Automatic update checks: {label}")


# ── Status / Monitor commands ─────────────────────────────────────────


def _is_valid_temperature_sensor(sensor) -> bool:
    """Filter out non-useful temperature sensors.

    Excludes sensors that are metadata rather than actual temperature readings,
    such as resolution, limits, critical thresholds, or warning temperatures.
    """
    invalid_keywords = ["resolution", "limit", "critical", "warning"]
    sensor_name_lower = sensor.sensor_name.lower()
    return not any(kw in sensor_name_lower for kw in invalid_keywords)


def _match_fans_with_controls(fans, controls) -> list[tuple]:
    """Match fan RPM sensors with their corresponding PWM controls.

    Returns a list of (fan_sensor, control_info) tuples, where control_info
    may be None if no matching control is found.
    """
    control_map: dict[str, object] = {}

    for ctrl in controls:
        parts = ctrl.identifier.split("/")
        try:
            ctrl_idx = parts.index("control")
            if ctrl_idx + 1 < len(parts):
                control_map[parts[ctrl_idx + 1]] = ctrl
        except ValueError:
            continue

    matched = []
    for fan in fans:
        parts = fan.identifier.split("/")
        try:
            fan_idx = parts.index("fan")
            if fan_idx + 1 < len(parts):
                fan_key = parts[fan_idx + 1]
                matched.append((fan, control_map.get(fan_key)))
            else:
                matched.append((fan, None))
        except ValueError:
            matched.append((fan, None))

    return matched


def _build_status_table(result) -> Table:
    """Build a rich Table from a hardware scan result."""
    from rich.table import Table

    table = Table(
        title="pysysfan Sensor Status",
        show_header=True,
        header_style="bold cyan",
        expand=True,
    )
    table.add_column("Type", style="dim", width=8)
    table.add_column("Hardware")
    table.add_column("Sensor")
    table.add_column("RPM", justify="right")
    table.add_column("PWM %", justify="right")

    valid_temps = [s for s in result.temperatures if _is_valid_temperature_sensor(s)]
    for s in valid_temps:
        val = f"{s.value:.1f} °C" if s.value is not None else "N/A"
        table.add_row("Temp", s.hardware_name, s.sensor_name, val, "")

    matched_fans = _match_fans_with_controls(result.fans, result.controls)
    for fan, ctrl in matched_fans:
        rpm_val = f"{fan.value:.0f}" if fan.value is not None else "N/A"
        pwm_val = (
            f"{ctrl.current_value:.1f}%"
            if ctrl and ctrl.current_value is not None
            else "N/A"
        )
        ctrl_indicator = "[green]✓[/]" if ctrl and ctrl.has_control else "[dim]✗[/]"
        sensor_name = f"{fan.sensor_name} {ctrl_indicator}"
        table.add_row(
            "Fan",
            fan.hardware_name,
            sensor_name,
            f"[cyan]{rpm_val}[/]",
            f"[green]{pwm_val}[/]",
        )

    return table


@main.command()
def status():
    """Show a snapshot of current hardware sensor readings."""
    if not check_admin():
        console.print(
            "[bold yellow]⚠[/] Not running as Administrator — "
            "motherboard sensors may not appear."
        )

    from pysysfan.hardware import HardwareManager

    try:
        with HardwareManager() as hw:
            result = hw.scan()
    except Exception as e:
        console.print(f"[red]Error accessing hardware:[/] {e}")
        raise SystemExit(1)

    table = _build_status_table(result)
    console.print(table)


@main.command()
@click.option(
    "--interval",
    "-i",
    type=float,
    default=1.0,
    show_default=True,
    help="Refresh interval in seconds.",
)
def monitor(interval: float):
    """Live-updating sensor dashboard. Press Ctrl+C to exit."""
    import time
    from rich.live import Live
    from rich.panel import Panel
    from pysysfan.hardware import HardwareManager

    if not check_admin():
        console.print(
            "[bold yellow]⚠[/] Not running as Administrator — "
            "motherboard sensors may not appear."
        )

    try:
        hw = HardwareManager()
        hw.open()
    except Exception as e:
        console.print(f"[red]Error:[/] {e}")
        raise SystemExit(1)

    try:
        with Live(
            console=console,
            refresh_per_second=1,
            screen=True,
            vertical_overflow="visible",
        ) as live:
            while True:
                try:
                    result = hw.scan()
                    table = _build_status_table(result)
                    import datetime

                    ts = datetime.datetime.now().strftime("%H:%M:%S")
                    live.update(
                        Panel(
                            table,
                            title=f"[bold green]pysysfan Monitor[/] — [dim]updated {ts}, Ctrl+C to exit[/]",
                        )
                    )
                except Exception as e:
                    live.update(f"[red]Error:[/] {e}")

                time.sleep(interval)
    except KeyboardInterrupt:
        pass
    finally:
        hw.close()
