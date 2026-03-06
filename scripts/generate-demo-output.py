#!/usr/bin/env python3
"""generate-demo-output.py — Capture static claw CLI output for docs.

Runs each claw subcommand and saves the output to assets/demo/*.txt.
Commands that fail are captured with their error message — no hard crashes.

Usage:
    .venv/bin/python scripts/generate-demo-output.py
    .venv/bin/python scripts/generate-demo-output.py --output-dir assets/demo
    .venv/bin/python scripts/generate-demo-output.py --claw .venv/bin/claw
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "assets" / "demo"
DEFAULT_CLAW = str(PROJECT_DIR / ".venv" / "bin" / "claw")

# (subcommand_args, output_filename, description)
COMMANDS: list[tuple[list[str], str, str]] = [
    (["status"], "status.txt", "System status overview"),
    (["skill", "list"], "skills.txt", "Registered skills"),
    (["cron", "list"], "cron.txt", "Scheduled cron jobs"),
    (["benchmark", "list"], "benchmarks.txt", "Orchestration benchmarks"),
    (["agent", "list"], "agents.txt", "Available agents"),
    (["workflow", "list"], "workflows.txt", "Available workflows"),
    (["vault", "status"], "vault.txt", "Vault status"),
    (["--version"], "version.txt", "CLI version"),
    (["--help"], "help.txt", "CLI help"),
]

# Optional commands — only captured if they exist
OPTIONAL_COMMANDS: list[tuple[list[str], str, str]] = [
    (["llm", "list"], "llm.txt", "LLM providers"),
    (["pack", "list"], "packs.txt", "Installed packs"),
    (["report", "list"], "reports.txt", "Saved reports"),
    (["dag", "list"], "dag.txt", "DAG tasks"),
]


def run_claw(claw_bin: str, args: list[str], timeout: int = 30) -> tuple[str, int]:
    """Run a claw command and return (output, returncode)."""
    cmd = [claw_bin] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_DIR),
        )
        output = result.stdout
        if result.stderr:
            output += f"\n--- stderr ---\n{result.stderr}"
        return output.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT] Command timed out after {timeout}s", 1
    except FileNotFoundError:
        return f"[ERROR] claw binary not found at {claw_bin}", 127
    except OSError as exc:
        return f"[ERROR] {exc}", 1


def check_command_exists(claw_bin: str, args: list[str]) -> bool:
    """Check if a claw subcommand exists by running --help."""
    cmd = [claw_bin] + args[:1] + ["--help"]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(PROJECT_DIR),
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def generate_header(description: str, cmd_args: list[str], claw_bin: str) -> str:
    """Generate a header block for the output file."""
    cmd_str = f"{claw_bin} {' '.join(cmd_args)}"
    lines = [
        f"# {description}",
        f"# Command: {cmd_str}",
        "#" + "-" * 60,
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate static demo output from claw CLI"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory (default: %(default)s)",
    )
    parser.add_argument(
        "--claw",
        default=DEFAULT_CLAW,
        help="Path to claw binary (default: %(default)s)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Command timeout in seconds (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Demo output generator")
    print(f"  claw binary: {args.claw}")
    print(f"  output dir:  {output_dir}")
    print()

    # Verify claw exists
    claw_path = Path(args.claw)
    if not claw_path.exists():
        print(f"[ERROR] claw binary not found at {args.claw}")
        print("  Make sure the virtualenv is set up: .venv/bin/claw")
        return 1

    captured = 0
    failed = 0

    # Required commands
    for cmd_args, filename, description in COMMANDS:
        print(f"  [{' '.join(cmd_args)}] {description} ...", end=" ")
        output, rc = run_claw(args.claw, cmd_args, timeout=args.timeout)
        header = generate_header(description, cmd_args, args.claw)
        (output_dir / filename).write_text(header + output + "\n")
        if rc == 0:
            print("OK")
            captured += 1
        else:
            print(f"WARN (exit {rc})")
            captured += 1  # Still captured the output

    # Optional commands
    for cmd_args, filename, description in OPTIONAL_COMMANDS:
        if not check_command_exists(args.claw, cmd_args):
            print(f"  [{' '.join(cmd_args)}] {description} ... SKIP (not available)")
            continue
        print(f"  [{' '.join(cmd_args)}] {description} ...", end=" ")
        output, rc = run_claw(args.claw, cmd_args, timeout=args.timeout)
        header = generate_header(description, cmd_args, args.claw)
        (output_dir / filename).write_text(header + output + "\n")
        if rc == 0:
            print("OK")
            captured += 1
        else:
            print(f"WARN (exit {rc})")
            captured += 1

    # Generate index file
    index_lines = ["# Demo Output Index", f"# Generated by generate-demo-output.py", ""]
    for f in sorted(output_dir.glob("*.txt")):
        if f.name == "index.txt":
            continue
        index_lines.append(f"  {f.name}")
    (output_dir / "index.txt").write_text("\n".join(index_lines) + "\n")

    print(f"\nDone. Captured {captured} outputs, {failed} failures.")
    print(f"Files saved to {output_dir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
