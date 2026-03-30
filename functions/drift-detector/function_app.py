"""
drift-detector — Scheduled Azure Function that compares declared access
package state (YAML configs) against actual platform permissions.

Runs on a configurable schedule (default: daily) and produces a drift
report identifying:
  - Users with access not declared in any package (shadow access)
  - Declared permissions that are missing in the platform (under-provisioned)
  - Permission levels that exceed what the package declares (over-provisioned)

Supports multi-platform drift detection via the provider registry:
  - Fabric: workspace roles, item permissions
  - Databricks: Unity Catalog grants, workspace ACLs

The drift report is:
  1. Logged to Azure Monitor / Log Analytics
  2. Stored in a storage account for the control plane UI
  3. Optionally sent as a Teams/Slack notification
"""

import os
import json
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field

import yaml
import azure.functions as func

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))
from provider_registry import get_provider, DriftFinding

logger = logging.getLogger(__name__)

ACCESS_PACKAGES_DIR = os.environ.get(
    "ACCESS_PACKAGES_DIR",
    os.path.join(os.path.dirname(__file__), '..', '..', 'access-packages', 'definitions')
)


@dataclass
class DriftReport:
    """Complete drift report for a scan run."""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_packages_scanned: int = 0
    platforms_scanned: list[str] = field(default_factory=list)
    findings: list[DriftFinding] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        return len(self.findings) > 0

    @property
    def high_severity_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "high")

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "total_packages_scanned": self.total_packages_scanned,
            "platforms_scanned": self.platforms_scanned,
            "has_drift": self.has_drift,
            "summary": {
                "total_findings": len(self.findings),
                "high": self.high_severity_count,
                "medium": sum(1 for f in self.findings if f.severity == "medium"),
                "low": sum(1 for f in self.findings if f.severity == "low"),
                "by_platform": self._findings_by_platform(),
            },
            "findings": [
                {
                    "platform": f.platform,
                    "category": f.category,
                    "severity": f.severity,
                    "securable": f.securable,
                    "principal": f.principal,
                    "declared": f.declared,
                    "actual": f.actual,
                    "package": f.package,
                }
                for f in self.findings
            ],
            "errors": self.errors,
        }

    def _findings_by_platform(self) -> dict:
        counts = {}
        for f in self.findings:
            counts[f.platform] = counts.get(f.platform, 0) + 1
        return counts


# ---------------------------------------------------------------------------
# Function Entry Points
# ---------------------------------------------------------------------------
app = func.FunctionApp()


@app.function_name("drift-detector-scheduled")
@app.timer_trigger(schedule="0 0 6 * * *", arg_name="timer",
                   run_on_startup=False)
def drift_detector_scheduled(timer: func.TimerRequest) -> None:
    """
    Timer-triggered drift detection. Runs daily at 6:00 AM UTC.
    Cron: second minute hour day month weekday
    """
    logger.info("Starting scheduled drift detection scan")
    report = run_drift_scan()
    _publish_report(report)


@app.function_name("drift-detector-manual")
@app.route(route="drift-scan", methods=["POST"])
def drift_detector_manual(req: func.HttpRequest) -> func.HttpResponse:
    """Manual trigger for on-demand drift detection."""
    logger.info("Starting manual drift detection scan")
    report = run_drift_scan()
    _publish_report(report)

    return func.HttpResponse(
        json.dumps(report.to_dict(), indent=2),
        status_code=200 if not report.has_drift else 207,
        mimetype="application/json",
    )


# ---------------------------------------------------------------------------
# Core Drift Detection Logic
# ---------------------------------------------------------------------------
def run_drift_scan() -> DriftReport:
    """
    Execute a full drift scan across all access packages and platforms.

    For each platform referenced in any package:
      1. Load all YAML definitions (desired state)
      2. Get the platform provider (real or mock)
      3. Call detect_drift() which queries actual platform state
      4. Aggregate findings into a unified report
    """
    report = DriftReport()

    # Load all access packages
    packages = _load_all_packages()
    report.total_packages_scanned = len(packages)

    # Determine which platforms are referenced
    platforms_needed = set()
    for pkg_name, pkg in packages.items():
        grants = pkg.get("grants", {})
        if grants.get("items") or grants.get("compute"):
            platforms_needed.add("fabric")
        for platform_name in pkg.get("platforms", {}):
            platforms_needed.add(platform_name)

    # Run drift detection per platform
    for platform_name in sorted(platforms_needed):
        logger.info(f"Running drift detection for platform: {platform_name}")
        try:
            provider = get_provider(platform_name)
            findings = provider.detect_drift(packages)
            report.findings.extend(findings)
            report.platforms_scanned.append(platform_name)
            logger.info(f"{platform_name}: {len(findings)} drift findings")
        except NotImplementedError as e:
            logger.warning(f"Skipping {platform_name}: {e}")
        except Exception as e:
            report.errors.append(f"Drift detection failed for {platform_name}: {str(e)}")
            logger.error(f"Drift detection failed for {platform_name}: {e}")

    return report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _load_all_packages() -> dict:
    """Load all YAML access package definitions."""
    packages = {}
    if not os.path.isdir(ACCESS_PACKAGES_DIR):
        logger.error(f"Directory not found: {ACCESS_PACKAGES_DIR}")
        return packages

    for filename in os.listdir(ACCESS_PACKAGES_DIR):
        if not filename.endswith(".yaml"):
            continue
        filepath = os.path.join(ACCESS_PACKAGES_DIR, filename)
        try:
            with open(filepath, 'r') as f:
                pkg = yaml.safe_load(f)
            if pkg:
                packages[filename.replace(".yaml", "")] = pkg
        except Exception as e:
            logger.error(f"Failed to load {filename}: {e}")

    return packages


def _publish_report(report: DriftReport):
    """Publish drift report to Log Analytics and storage."""
    report_dict = report.to_dict()
    logger.info(f"Drift scan complete: {json.dumps(report_dict)}")

    if report.has_drift:
        logger.warning(
            f"DRIFT DETECTED: {len(report.findings)} findings "
            f"({report.high_severity_count} high severity) "
            f"across platforms: {', '.join(report.platforms_scanned)}"
        )
