#!/usr/bin/env python3
"""Security Sentinel — brutal security guardian for claude-superpowers.

Performs:
  - Dependency CVE scanning via OSV API
  - Static code analysis (AST + regex) for dangerous patterns
  - Docker security auditing
  - Zero-day patch advising with auto-generated diffs
  - SARIF output for GitHub Advanced Security integration

Exit codes:
  0 = clean
  1 = warnings only
  2 = critical findings (blocks PR)
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

Severity = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]

SEVERITY_RANK: dict[str, int] = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
    "INFO": 0,
}


@dataclass
class Finding:
    """A single security finding."""

    title: str
    description: str
    severity: Severity
    category: str
    file: str = ""
    line: int = 0
    column: int = 0
    cve: str = ""
    fix: str = ""
    cwe: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class ScanReport:
    """Full scan report."""

    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    project: str = ""
    scan_duration_seconds: float = 0.0
    findings: list[Finding] = field(default_factory=list)
    checks_run: int = 0
    summary: dict[str, int] = field(default_factory=dict)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "CRITICAL")

    @property
    def high_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "HIGH")

    @property
    def exit_code(self) -> int:
        if self.critical_count > 0:
            return 2
        if self.high_count > 0:
            return 2
        if any(f.severity == "MEDIUM" for f in self.findings):
            return 1
        return 0

    def compute_summary(self) -> None:
        self.summary = {}
        for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
            count = sum(1 for f in self.findings if f.severity == sev)
            if count:
                self.summary[sev] = count

    def to_dict(self) -> dict[str, Any]:
        self.compute_summary()
        return {
            "timestamp": self.timestamp,
            "project": self.project,
            "scan_duration_seconds": self.scan_duration_seconds,
            "checks_run": self.checks_run,
            "summary": self.summary,
            "findings": [f.to_dict() for f in self.findings],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def to_markdown(self) -> str:
        self.compute_summary()
        lines = [
            "# Security Sentinel Report",
            "",
            f"**Scan time:** {self.timestamp}",
            f"**Project:** {self.project}",
            f"**Duration:** {self.scan_duration_seconds:.2f}s",
            f"**Checks run:** {self.checks_run}",
            "",
        ]

        if not self.findings:
            lines.append("All clear. No security findings.")
            return "\n".join(lines)

        lines.append("## Summary")
        lines.append("")
        lines.append("| Severity | Count |")
        lines.append("|----------|-------|")
        for sev, count in self.summary.items():
            lines.append(f"| {sev} | {count} |")
        lines.append("")

        lines.append("## Findings")
        lines.append("")
        for i, f in enumerate(
            sorted(self.findings, key=lambda x: SEVERITY_RANK.get(x.severity, 0), reverse=True),
            1,
        ):
            loc = f"{f.file}:{f.line}" if f.file else "N/A"
            lines.append(f"### {i}. [{f.severity}] {f.title}")
            lines.append("")
            lines.append(f"- **Location:** `{loc}`")
            lines.append(f"- **Category:** {f.category}")
            if f.cve:
                lines.append(f"- **CVE:** {f.cve}")
            if f.cwe:
                lines.append(f"- **CWE:** {f.cwe}")
            lines.append(f"- **Description:** {f.description}")
            if f.fix:
                lines.append(f"- **Fix:** {f.fix}")
            lines.append("")

        return "\n".join(lines)

    def to_sarif(self) -> dict[str, Any]:
        """Generate SARIF 2.1.0 output for GitHub Advanced Security."""
        rules = []
        results = []
        rule_ids: dict[str, int] = {}

        for f in self.findings:
            rule_id = re.sub(r"[^a-zA-Z0-9_-]", "-", f.title).lower()
            if rule_id not in rule_ids:
                rule_ids[rule_id] = len(rules)
                severity_map = {
                    "CRITICAL": "error",
                    "HIGH": "error",
                    "MEDIUM": "warning",
                    "LOW": "note",
                    "INFO": "note",
                }
                rules.append({
                    "id": rule_id,
                    "name": f.title,
                    "shortDescription": {"text": f.title},
                    "fullDescription": {"text": f.description},
                    "defaultConfiguration": {"level": severity_map.get(f.severity, "warning")},
                    "properties": {"security-severity": str(SEVERITY_RANK.get(f.severity, 0) * 2.5)},
                })

            result: dict[str, Any] = {
                "ruleId": rule_id,
                "ruleIndex": rule_ids[rule_id],
                "message": {"text": f.description},
                "level": {"CRITICAL": "error", "HIGH": "error", "MEDIUM": "warning"}.get(
                    f.severity, "note"
                ),
            }

            if f.file:
                result["locations"] = [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": f.file, "uriBaseId": "%SRCROOT%"},
                            "region": {"startLine": max(f.line, 1), "startColumn": max(f.column, 1)},
                        }
                    }
                ]

            results.append(result)

        return {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "Security Sentinel",
                            "version": "1.0.0",
                            "informationUri": "https://github.com/your-org/claude-superpowers",
                            "rules": rules,
                        }
                    },
                    "results": results,
                }
            ],
        }


# ---------------------------------------------------------------------------
# OSV cache (offline-first)
# ---------------------------------------------------------------------------

_OSV_CACHE_DIR = Path(os.environ.get("SENTINEL_CACHE_DIR", Path.home() / ".cache" / "security-sentinel"))


def _cache_key(package: str, version: str, ecosystem: str = "PyPI") -> Path:
    h = hashlib.sha256(f"{ecosystem}:{package}:{version}".encode()).hexdigest()[:16]
    return _OSV_CACHE_DIR / f"{h}.json"


def _cache_get(package: str, version: str, ecosystem: str = "PyPI", max_age: int = 86400) -> list[dict] | None:
    path = _cache_key(package, version, ecosystem)
    if not path.exists():
        return None
    age = time.time() - path.stat().st_mtime
    if age > max_age:
        return None
    try:
        data = json.loads(path.read_text())
        return data.get("vulns", [])
    except (json.JSONDecodeError, OSError):
        return None


def _cache_put(package: str, version: str, vulns: list[dict], ecosystem: str = "PyPI") -> None:
    _OSV_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_key(package, version, ecosystem)
    path.write_text(json.dumps({"vulns": vulns}))


# ---------------------------------------------------------------------------
# Dependency CVE scanner
# ---------------------------------------------------------------------------

def _parse_dependencies(project_root: Path) -> list[tuple[str, str]]:
    """Extract (package, version_spec) from pyproject.toml and requirements.txt."""
    deps: list[tuple[str, str]] = []

    # pyproject.toml
    pyproject = project_root / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text()
        # Simple TOML parser for dependencies array
        in_deps = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("dependencies") and "=" in stripped:
                in_deps = True
                continue
            if in_deps:
                if stripped == "]":
                    in_deps = False
                    continue
                match = re.match(r'"([a-zA-Z0-9_-]+)\s*([><=!~]+\s*[\d.]+(?:,\s*[><=!~]+\s*[\d.]+)*)?', stripped)
                if match:
                    pkg = match.group(1)
                    ver = match.group(2) or ""
                    # Extract minimum version from spec like >=6.0
                    ver_match = re.search(r"[\d]+(?:\.[\d]+)*", ver)
                    ver_str = ver_match.group(0) if ver_match else ""
                    deps.append((pkg, ver_str))

    # requirements.txt files
    for req_file in project_root.glob("**/requirements*.txt"):
        if ".venv" in str(req_file) or "node_modules" in str(req_file):
            continue
        try:
            for line in req_file.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                match = re.match(r"([a-zA-Z0-9_-]+)\s*([><=!~]+\s*[\d.]+)?", line)
                if match:
                    pkg = match.group(1)
                    ver = match.group(2) or ""
                    ver_match = re.search(r"[\d]+(?:\.[\d]+)*", ver)
                    ver_str = ver_match.group(0) if ver_match else ""
                    deps.append((pkg, ver_str))
        except OSError:
            continue

    return deps


def _query_osv(package: str, version: str, ecosystem: str = "PyPI") -> list[dict]:
    """Query OSV API for known vulnerabilities. Returns list of vuln dicts."""
    # Check cache first
    cached = _cache_get(package, version, ecosystem)
    if cached is not None:
        return cached

    payload: dict[str, Any] = {
        "package": {"name": package, "ecosystem": ecosystem},
    }
    if version:
        payload["version"] = version

    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            "https://api.osv.dev/v1/query",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            vulns = result.get("vulns", [])
            _cache_put(package, version, vulns, ecosystem)
            return vulns
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError):
        # Offline or API error -- degrade gracefully
        return []


def scan_dependencies(project_root: Path, offline: bool = False) -> list[Finding]:
    """Scan all project dependencies for known CVEs."""
    findings: list[Finding] = []
    deps = _parse_dependencies(project_root)

    for pkg, ver in deps:
        if offline:
            continue
        vulns = _query_osv(pkg, ver)
        for vuln in vulns:
            vuln_id = vuln.get("id", "UNKNOWN")
            summary = vuln.get("summary", "No summary available")
            aliases = vuln.get("aliases", [])
            cve_id = next((a for a in aliases if a.startswith("CVE-")), vuln_id)

            # Determine severity from database_specific or severity field
            severity: Severity = "HIGH"
            if "database_specific" in vuln:
                db_sev = vuln["database_specific"].get("severity", "").upper()
                if db_sev in SEVERITY_RANK:
                    severity = db_sev  # type: ignore[assignment]
            if "severity" in vuln:
                for sev_entry in vuln["severity"]:
                    score_str = sev_entry.get("score", "")
                    # CVSS score parsing
                    cvss_match = re.search(r"AV:[NALP]/.*", score_str)
                    if cvss_match:
                        # Rough severity from CVSS vector
                        if "AV:N" in score_str:
                            severity = "CRITICAL"

            # Find patched version
            fix_ver = ""
            for affected in vuln.get("affected", []):
                for rng in affected.get("ranges", []):
                    for evt in rng.get("events", []):
                        if "fixed" in evt:
                            fix_ver = evt["fixed"]

            fix_msg = f"Upgrade {pkg} to >= {fix_ver}" if fix_ver else f"No patch available for {cve_id}. Consider pinning to an unaffected version or adding a WAF rule."

            findings.append(Finding(
                title=f"Vulnerable dependency: {pkg}",
                description=f"{cve_id}: {summary}",
                severity=severity,
                category="dependency-cve",
                file="pyproject.toml",
                line=1,
                cve=cve_id,
                fix=fix_msg,
                cwe="CWE-1395",
            ))

    return findings


# ---------------------------------------------------------------------------
# Static code analyzer (AST-based)
# ---------------------------------------------------------------------------

class _DangerousPatternVisitor(ast.NodeVisitor):
    """AST visitor that detects dangerous code patterns."""

    def __init__(self, filepath: str, source_lines: list[str]) -> None:
        self.filepath = filepath
        self.source_lines = source_lines
        self.findings: list[Finding] = []

    # -- subprocess with shell=True --
    def visit_Call(self, node: ast.Call) -> None:
        func_name = self._get_func_name(node)

        # subprocess.call/Popen/run with shell=True
        if func_name in (
            "subprocess.call", "subprocess.Popen", "subprocess.run",
            "subprocess.check_call", "subprocess.check_output",
        ):
            for kw in node.keywords:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    self.findings.append(Finding(
                        title="subprocess with shell=True",
                        description=f"{func_name}() called with shell=True enables shell injection",
                        severity="CRITICAL",
                        category="code-injection",
                        file=self.filepath,
                        line=node.lineno,
                        column=node.col_offset,
                        cwe="CWE-78",
                        fix="Use a list of arguments instead of a shell string, and set shell=False",
                    ))

        # os.system()
        if func_name == "os.system":
            self.findings.append(Finding(
                title="os.system() usage",
                description="os.system() is vulnerable to shell injection. Use subprocess with shell=False.",
                severity="CRITICAL",
                category="code-injection",
                file=self.filepath,
                line=node.lineno,
                column=node.col_offset,
                cwe="CWE-78",
                fix="Replace os.system() with subprocess.run([...], shell=False)",
            ))

        # eval() / exec()
        if func_name in ("eval", "exec"):
            # Check if the argument could be user-controlled (not a literal)
            is_literal = (
                len(node.args) > 0
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            )
            severity: Severity = "MEDIUM" if is_literal else "CRITICAL"
            self.findings.append(Finding(
                title=f"{func_name}() usage detected",
                description=f"{func_name}() can execute arbitrary code. Verify input is trusted.",
                severity=severity,
                category="code-injection",
                file=self.filepath,
                line=node.lineno,
                column=node.col_offset,
                cwe="CWE-95",
                fix=f"Avoid {func_name}(). Use ast.literal_eval() for data parsing or a proper parser.",
            ))

        # pickle.loads / pickle.load
        if func_name in ("pickle.loads", "pickle.load", "cPickle.loads", "cPickle.load"):
            self.findings.append(Finding(
                title="Insecure deserialization (pickle)",
                description=f"{func_name}() can execute arbitrary code during deserialization",
                severity="CRITICAL",
                category="insecure-deserialization",
                file=self.filepath,
                line=node.lineno,
                column=node.col_offset,
                cwe="CWE-502",
                fix="Use json or a safe serialization format. Never unpickle untrusted data.",
            ))

        # yaml.load without SafeLoader
        if func_name == "yaml.load":
            has_safe_loader = False
            for kw in node.keywords:
                if kw.arg == "Loader":
                    loader_name = self._get_func_name_from_node(kw.value)
                    if loader_name and "Safe" in loader_name:
                        has_safe_loader = True
            if len(node.args) >= 2:
                loader_name = self._get_func_name_from_node(node.args[1])
                if loader_name and "Safe" in loader_name:
                    has_safe_loader = True
            if not has_safe_loader:
                self.findings.append(Finding(
                    title="yaml.load() without SafeLoader",
                    description="yaml.load() without SafeLoader can execute arbitrary Python objects",
                    severity="CRITICAL",
                    category="insecure-deserialization",
                    file=self.filepath,
                    line=node.lineno,
                    column=node.col_offset,
                    cwe="CWE-502",
                    fix="Use yaml.safe_load() or yaml.load(data, Loader=yaml.SafeLoader)",
                ))

        # requests with verify=False
        if func_name in ("requests.get", "requests.post", "requests.put",
                         "requests.delete", "requests.patch", "requests.head"):
            for kw in node.keywords:
                if kw.arg == "verify" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                    self.findings.append(Finding(
                        title="TLS verification disabled",
                        description=f"{func_name}() with verify=False disables SSL certificate verification",
                        severity="HIGH",
                        category="insecure-transport",
                        file=self.filepath,
                        line=node.lineno,
                        column=node.col_offset,
                        cwe="CWE-295",
                        fix="Remove verify=False to enable TLS certificate verification",
                    ))

        # marshal.loads
        if func_name in ("marshal.loads", "marshal.load"):
            self.findings.append(Finding(
                title="Insecure deserialization (marshal)",
                description=f"{func_name}() can crash the interpreter with malformed data",
                severity="HIGH",
                category="insecure-deserialization",
                file=self.filepath,
                line=node.lineno,
                column=node.col_offset,
                cwe="CWE-502",
                fix="Use json or another safe format for untrusted data",
            ))

        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        """Detect f-strings in SQL-like contexts by checking surrounding assignment/call."""
        # We check the source line for SQL keywords
        if node.lineno <= len(self.source_lines):
            line = self.source_lines[node.lineno - 1]
            sql_pattern = re.compile(
                r"(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC)\s",
                re.IGNORECASE,
            )
            if sql_pattern.search(line) and "{" in line:
                self.findings.append(Finding(
                    title="SQL injection via f-string",
                    description="F-string used in SQL query construction enables SQL injection",
                    severity="CRITICAL",
                    category="sql-injection",
                    file=self.filepath,
                    line=node.lineno,
                    column=node.col_offset,
                    cwe="CWE-89",
                    fix="Use parameterized queries (e.g., cursor.execute('SELECT ? ...', (param,)))",
                ))
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        """Detect % formatting in SQL contexts."""
        if isinstance(node.op, ast.Mod) and isinstance(node.left, ast.Constant):
            val = str(node.left.value)
            if re.search(r"(SELECT|INSERT|UPDATE|DELETE|DROP)\s", val, re.IGNORECASE):
                self.findings.append(Finding(
                    title="SQL injection via string formatting",
                    description="% string formatting in SQL query enables SQL injection",
                    severity="CRITICAL",
                    category="sql-injection",
                    file=self.filepath,
                    line=node.lineno,
                    column=node.col_offset,
                    cwe="CWE-89",
                    fix="Use parameterized queries instead of string formatting",
                ))
        self.generic_visit(node)

    def _get_func_name(self, node: ast.Call) -> str:
        return self._get_func_name_from_node(node.func)

    def _get_func_name_from_node(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = self._get_func_name_from_node(node.value)
            if parent:
                return f"{parent}.{node.attr}"
            return node.attr
        return ""


# Regex-based checks that complement AST analysis
_REGEX_CHECKS: list[tuple[str, re.Pattern[str], Severity, str, str, str]] = [
    # (title, pattern, severity, category, cwe, fix)
    (
        "Hardcoded secret",
        re.compile(
            r"""(?:API_KEY|SECRET_KEY|PASSWORD|TOKEN|PRIVATE_KEY|AWS_SECRET|DB_PASSWORD)\s*[=:]\s*['\"][^'\"]{8,}['\"]""",
            re.IGNORECASE,
        ),
        "CRITICAL",
        "hardcoded-secret",
        "CWE-798",
        "Move secrets to environment variables or a vault (e.g., claw vault)",
    ),
    (
        "Binding to 0.0.0.0",
        re.compile(r"""(?:host|bind)\s*[=:]\s*['"]0\.0\.0\.0['"]""", re.IGNORECASE),
        "MEDIUM",
        "network-exposure",
        "CWE-668",
        "Bind to 127.0.0.1 or a specific interface unless public access is intended",
    ),
    (
        "Debug mode enabled",
        re.compile(r"""(?:DEBUG|VERBOSE)\s*=\s*(?:True|1|['"]true['"])""", re.IGNORECASE),
        "LOW",
        "debug-mode",
        "CWE-489",
        "Disable debug/verbose mode in production",
    ),
    (
        "Path traversal risk",
        re.compile(r"""(?:open|Path)\s*\([^)]*\.\.[/\\]"""),
        "HIGH",
        "path-traversal",
        "CWE-22",
        "Validate and sanitize file paths. Use pathlib.resolve() and check against an allowed base.",
    ),
]


def scan_code_static(project_root: Path) -> list[Finding]:
    """Run static analysis on all Python files in the project."""
    findings: list[Finding] = []

    py_files = list(project_root.rglob("*.py"))
    # Filter out venvs, caches, etc.
    py_files = [
        f for f in py_files
        if not any(
            part in f.parts
            for part in (".venv", "venv", "__pycache__", "node_modules", ".git", "site-packages", "site")
        )
    ]

    for py_file in py_files:
        rel_path = str(py_file.relative_to(project_root))
        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        source_lines = source.splitlines()

        # AST-based analysis
        try:
            tree = ast.parse(source, filename=rel_path)
            visitor = _DangerousPatternVisitor(rel_path, source_lines)
            visitor.visit(tree)
            findings.extend(visitor.findings)
        except SyntaxError:
            # Can't parse -- skip AST checks, still do regex
            pass

        # Regex-based checks
        for title, pattern, severity, category, cwe, fix in _REGEX_CHECKS:
            for i, line in enumerate(source_lines, 1):
                if pattern.search(line):
                    # Skip if it's a comment or part of test/documentation
                    stripped = line.lstrip()
                    if stripped.startswith("#"):
                        continue
                    findings.append(Finding(
                        title=title,
                        description=f"Pattern matched: {pattern.pattern[:60]}...",
                        severity=severity,  # type: ignore[arg-type]
                        category=category,
                        file=rel_path,
                        line=i,
                        cwe=cwe,
                        fix=fix,
                    ))

    return findings


# ---------------------------------------------------------------------------
# Docker security checker
# ---------------------------------------------------------------------------

def _parse_yaml_simple(content: str) -> dict[str, Any]:
    """Parse YAML without external dependencies. Falls back to PyYAML if available."""
    try:
        import yaml
        return yaml.safe_load(content) or {}
    except ImportError:
        pass

    # Minimal parser for docker-compose files -- just extract what we need via regex
    result: dict[str, Any] = {}
    result["_raw"] = content
    return result


def scan_docker(project_root: Path) -> list[Finding]:
    """Audit docker-compose files for security issues."""
    findings: list[Finding] = []
    compose_files = (
        list(project_root.glob("docker-compose*.yml"))
        + list(project_root.glob("docker-compose*.yaml"))
        + list(project_root.glob("compose*.yml"))
        + list(project_root.glob("compose*.yaml"))
    )

    for compose_file in compose_files:
        rel_path = str(compose_file.relative_to(project_root))
        try:
            content = compose_file.read_text()
        except OSError:
            continue

        try:
            import yaml
            data = yaml.safe_load(content) or {}
        except ImportError:
            data = {}

        services = data.get("services", {})
        if not isinstance(services, dict):
            continue

        lines = content.splitlines()

        def _find_line(text: str, start: int = 0) -> int:
            for i, line in enumerate(lines[start:], start + 1):
                if text in line:
                    return i
            return 1

        for svc_name, svc_config in services.items():
            if not isinstance(svc_config, dict):
                continue

            svc_line = _find_line(f"{svc_name}:")

            # Privileged mode
            if svc_config.get("privileged") is True:
                findings.append(Finding(
                    title=f"Docker: privileged mode ({svc_name})",
                    description=f"Service '{svc_name}' runs in privileged mode, giving full host access",
                    severity="CRITICAL",
                    category="docker-security",
                    file=rel_path,
                    line=_find_line("privileged", svc_line),
                    cwe="CWE-250",
                    fix="Remove 'privileged: true'. Use specific capabilities instead.",
                ))

            # Host network
            if svc_config.get("network_mode") == "host":
                findings.append(Finding(
                    title=f"Docker: host network ({svc_name})",
                    description=f"Service '{svc_name}' uses host networking, bypassing Docker network isolation",
                    severity="HIGH",
                    category="docker-security",
                    file=rel_path,
                    line=_find_line("network_mode", svc_line),
                    cwe="CWE-668",
                    fix="Use a bridge network with explicit port mappings",
                ))

            # Unpinned images
            image = svc_config.get("image", "")
            if image and ":" not in image:
                findings.append(Finding(
                    title=f"Docker: unpinned image ({svc_name})",
                    description=f"Service '{svc_name}' uses unpinned image '{image}' (defaults to :latest)",
                    severity="MEDIUM",
                    category="docker-security",
                    file=rel_path,
                    line=_find_line(f"image:", svc_line),
                    cwe="CWE-829",
                    fix=f"Pin the image to a specific version: {image}:<version>",
                ))
            elif image and image.endswith(":latest"):
                findings.append(Finding(
                    title=f"Docker: :latest tag ({svc_name})",
                    description=f"Service '{svc_name}' uses :latest tag which is mutable and unpredictable",
                    severity="MEDIUM",
                    category="docker-security",
                    file=rel_path,
                    line=_find_line(f"image:", svc_line),
                    cwe="CWE-829",
                    fix=f"Pin to a specific version hash or semver tag",
                ))

            # Missing healthcheck
            if "healthcheck" not in svc_config:
                findings.append(Finding(
                    title=f"Docker: no healthcheck ({svc_name})",
                    description=f"Service '{svc_name}' has no healthcheck defined",
                    severity="LOW",
                    category="docker-security",
                    file=rel_path,
                    line=svc_line,
                    fix="Add a healthcheck to detect and restart unhealthy containers",
                ))

            # Running as root (no user specified)
            if "user" not in svc_config:
                findings.append(Finding(
                    title=f"Docker: running as root ({svc_name})",
                    description=f"Service '{svc_name}' has no 'user' directive, defaults to root",
                    severity="MEDIUM",
                    category="docker-security",
                    file=rel_path,
                    line=svc_line,
                    cwe="CWE-250",
                    fix="Add 'user: 1000:1000' or a non-root user",
                ))

            # Exposed ports
            ports = svc_config.get("ports", [])
            for port in ports:
                port_str = str(port)
                # Check if binding to all interfaces (no host IP specified)
                if re.match(r"^\d+:\d+$", port_str):
                    findings.append(Finding(
                        title=f"Docker: port exposed on all interfaces ({svc_name})",
                        description=f"Port mapping '{port_str}' exposes on 0.0.0.0. Bind to 127.0.0.1 if local only.",
                        severity="MEDIUM",
                        category="docker-security",
                        file=rel_path,
                        line=_find_line(str(port), svc_line),
                        cwe="CWE-668",
                        fix=f"Use '127.0.0.1:{port_str}' to restrict to localhost",
                    ))

            # Writable secrets via environment
            env = svc_config.get("environment", {})
            if isinstance(env, dict):
                for key, val in env.items():
                    if val and isinstance(val, str) and any(
                        s in key.upper() for s in ("PASSWORD", "SECRET", "TOKEN", "API_KEY")
                    ):
                        findings.append(Finding(
                            title=f"Docker: secret in environment ({svc_name})",
                            description=f"Secret '{key}' is hardcoded in docker-compose environment",
                            severity="HIGH",
                            category="docker-security",
                            file=rel_path,
                            line=_find_line(key, svc_line),
                            cwe="CWE-798",
                            fix="Use Docker secrets or .env files excluded from version control",
                        ))
            elif isinstance(env, list):
                for item in env:
                    if isinstance(item, str) and "=" in item:
                        key = item.split("=", 1)[0]
                        val = item.split("=", 1)[1]
                        if val and any(
                            s in key.upper() for s in ("PASSWORD", "SECRET", "TOKEN", "API_KEY")
                        ):
                            findings.append(Finding(
                                title=f"Docker: secret in environment ({svc_name})",
                                description=f"Secret '{key}' is hardcoded in docker-compose environment",
                                severity="HIGH",
                                category="docker-security",
                                file=rel_path,
                                line=_find_line(key, svc_line),
                                cwe="CWE-798",
                                fix="Use Docker secrets or .env files excluded from version control",
                            ))

    return findings


# ---------------------------------------------------------------------------
# Zero-day patch advisor
# ---------------------------------------------------------------------------

def generate_patch_diff(project_root: Path, findings: list[Finding]) -> str:
    """Generate a PR-ready diff for dependency upgrades."""
    pyproject = project_root / "pyproject.toml"
    if not pyproject.exists():
        return ""

    content = pyproject.read_text()
    patched = content

    for f in findings:
        if f.category != "dependency-cve" or not f.fix:
            continue
        # Extract upgrade target from fix message
        match = re.search(r"Upgrade (\S+) to >= (\S+)", f.fix)
        if not match:
            continue
        pkg, target_ver = match.group(1), match.group(2)
        # Replace the version spec in pyproject.toml
        dep_pattern = re.compile(
            rf'("{pkg}\s*)(>=\s*[\d.]+)',
            re.IGNORECASE,
        )
        patched = dep_pattern.sub(rf'\g<1>>={target_ver}', patched)

    if patched == content:
        return ""

    # Generate unified diff
    original_lines = content.splitlines(keepends=True)
    patched_lines = patched.splitlines(keepends=True)

    diff_lines = ["--- a/pyproject.toml\n", "+++ b/pyproject.toml\n"]
    for i, (old, new) in enumerate(zip(original_lines, patched_lines)):
        if old != new:
            diff_lines.append(f"@@ -{i+1},1 +{i+1},1 @@\n")
            diff_lines.append(f"-{old}")
            diff_lines.append(f"+{new}")

    return "".join(diff_lines) if len(diff_lines) > 2 else ""


# ---------------------------------------------------------------------------
# Main scanner orchestrator
# ---------------------------------------------------------------------------

def run_full_scan(
    project_root: Path,
    *,
    offline: bool = False,
    skip_docker: bool = False,
    skip_code: bool = False,
    skip_deps: bool = False,
) -> ScanReport:
    """Run all security checks and return a unified report."""
    start = time.monotonic()
    report = ScanReport(project=str(project_root))
    checks = 0

    # 1. Dependency CVE scan
    if not skip_deps:
        checks += 1
        dep_findings = scan_dependencies(project_root, offline=offline)
        report.findings.extend(dep_findings)

    # 2. Static code analysis
    if not skip_code:
        checks += 1
        code_findings = scan_code_static(project_root)
        report.findings.extend(code_findings)

    # 3. Docker security audit
    if not skip_docker:
        checks += 1
        docker_findings = scan_docker(project_root)
        report.findings.extend(docker_findings)

    # 4. Generate patch diff for CVE findings
    if not skip_deps:
        checks += 1
        patch = generate_patch_diff(project_root, report.findings)
        if patch:
            report.findings.append(Finding(
                title="Auto-generated patch available",
                description="A pyproject.toml patch is available to fix vulnerable dependencies",
                severity="INFO",
                category="patch-available",
                fix=patch,
            ))

    report.checks_run = checks
    report.scan_duration_seconds = round(time.monotonic() - start, 3)
    report.compute_summary()

    return report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="security-sentinel",
        description="Brutal security scanner for claude-superpowers",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root directory to scan (default: cwd)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown", "sarif"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="",
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip OSV API queries (use cache only)",
    )
    parser.add_argument(
        "--skip-docker",
        action="store_true",
        help="Skip Docker security checks",
    )
    parser.add_argument(
        "--skip-code",
        action="store_true",
        help="Skip static code analysis",
    )
    parser.add_argument(
        "--skip-deps",
        action="store_true",
        help="Skip dependency CVE scanning",
    )
    parser.add_argument(
        "--sarif-output",
        type=str,
        default="",
        help="Additional SARIF output file (generated alongside primary format)",
    )

    args = parser.parse_args()

    report = run_full_scan(
        args.project_root,
        offline=args.offline,
        skip_docker=args.skip_docker,
        skip_code=args.skip_code,
        skip_deps=args.skip_deps,
    )

    # Format output
    if args.format == "json":
        output = report.to_json()
    elif args.format == "sarif":
        output = json.dumps(report.to_sarif(), indent=2)
    else:
        output = report.to_markdown()

    # Write output
    if args.output:
        Path(args.output).write_text(output)
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(output)

    # Write SARIF if requested separately
    if args.sarif_output:
        sarif_data = json.dumps(report.to_sarif(), indent=2)
        Path(args.sarif_output).write_text(sarif_data)
        print(f"SARIF written to {args.sarif_output}", file=sys.stderr)

    # Also write SARIF as security-report.sarif for GitHub Actions
    sarif_path = args.project_root / "security-report.sarif"
    sarif_data = json.dumps(report.to_sarif(), indent=2)
    sarif_path.write_text(sarif_data)

    sys.exit(report.exit_code)


if __name__ == "__main__":
    main()
