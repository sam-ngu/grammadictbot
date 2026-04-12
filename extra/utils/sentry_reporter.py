"""
Sentry Integration for Instagram Login Challenges

Captures screenshots and reports impossible/unknown challenges to Sentry.
Provides a generic interface for reporting any issue with screenshot and context.

Usage:
    from extra.utils.sentry_reporter import (
        init_sentry,
        capture_screenshot,
        report_to_sentry,
        report_challenge_with_screenshot,
    )

    # Initialize Sentry (call once at app startup)
    init_sentry()

    # Generic reporting with screenshot and context
    report_to_sentry(
        message="Login challenge detected",
        context={"challenge_type": "selfie", "username": "example"},
        capture_screenshot_flag=True,
        device=device  # Pass device object if capturing screenshot
    )

    # Convenience function for challenge reporting
    report_challenge_with_screenshot(
        device=device,
        challenge_type="selfie",
        ig_username="example_user",
        additional_context={"stage": "after_password"}
    )
"""

import os
import time
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from dotenv import load_dotenv
from extra.utils.app_state import AppState


load_dotenv(override=True)

# Sentry SDK - lazy import to avoid issues if not installed
_sentry_sdk = None


def _get_sentry_sdk():
    """Lazy load sentry_sdk to avoid import errors if not installed."""
    global _sentry_sdk
    if _sentry_sdk is None:
        try:
            import sentry_sdk
            _sentry_sdk = sentry_sdk
        except ImportError:
            print("Warning: sentry_sdk not installed. Sentry reporting disabled.", flush=True)
            _sentry_sdk = False
    return _sentry_sdk if _sentry_sdk else None


def init_sentry(traces_sample_rate: float = 1.0) -> bool:
    """
    Initialize Sentry SDK.

    Should be called once at application startup.

    Args:
        traces_sample_rate: Sample rate for performance traces (0.0 to 1.0)

    Returns:
        bool: True if initialized successfully, False otherwise
    """
    sentry_sdk = _get_sentry_sdk()
    if not sentry_sdk:
        return False

    sentry_dsn = os.environ.get('SENTRY_DSN')
    if not sentry_dsn:
        print("Warning: SENTRY_DSN not set. Sentry reporting disabled.", flush=True)
        return False

    try:
        sentry_sdk.init(
            dsn=sentry_dsn,
            traces_sample_rate=traces_sample_rate,
            send_default_pii=True,
            add_full_stack=True
        )
        print("Sentry initialized successfully", flush=True)
        return True
    except Exception as e:
        print(f"Failed to initialize Sentry: {e}", flush=True)
        return False


def capture_screenshot(device, filename_prefix: str = "screenshot", ig_username: str = "") -> Optional[str]:
    """
    Capture a screenshot of the current device screen.

    Args:
        device: The device facade object (must have deviceV2.screenshot() method)
        filename_prefix: Prefix for the screenshot filename
        ig_username: Instagram username for context (included in filename)

    Returns:
        str: Path to screenshot file, or None if failed
    """
    try:
        # Create screenshots directory
        screenshots_dir = Path("/tmp/ig_screenshots")
        screenshots_dir.mkdir(exist_ok=True)

        # Generate filename with timestamp and username
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        username_suffix = f"_{ig_username}" if ig_username else ""
        filename = f"{filename_prefix}{username_suffix}_{timestamp}.png"
        filepath = screenshots_dir / filename

        # Capture screenshot using uiautomator2
        device.deviceV2.screenshot(str(filepath))

        print(f"Screenshot saved to {filepath}", flush=True)
        return str(filepath)

    except Exception as e:
        print(f"Failed to capture screenshot: {e}", flush=True)
        return None


def report_to_sentry(
    message: str,
    level: str = "error",
    context: Optional[Dict[str, Any]] = None,
    capture_screenshot_flag: bool = False,
    device=None,
    screenshot_path: Optional[str] = None,
    exception: Optional[Exception] = None,
    tags: Optional[Dict[str, str]] = None,
) -> bool:
    """
    Generic function to report an issue to Sentry with optional screenshot.

    This is the main entry point for all Sentry reporting.

    Args:
        message: The message to report (used as event title)
        level: Log level - "debug", "info", "warning", "error", "fatal"
        context: Additional context data to include
        capture_screenshot_flag: If True and device is provided, capture screenshot
        device: The device facade object (required if capture_screenshot_flag=True)
        screenshot_path: Path to existing screenshot to attach (optional)
        exception: Exception object to capture (optional, for exception reporting)
        tags: Tags to attach to the event for filtering

    Returns:
        bool: True if reported successfully, False otherwise

    Examples:
        # Report with auto-captured screenshot
        report_to_sentry(
            message="Selfie challenge detected",
            context={"challenge_type": "selfie", "stage": "after_2fa"},
            capture_screenshot_flag=True,
            device=device,
            tags={"challenge": "selfie", "username": ig_username}
        )

        # Report exception with existing screenshot
        report_to_sentry(
            message="Login failed",
            exception=e,
            screenshot_path="/tmp/screenshot.png",
            context={"username": ig_username}
        )

        # Simple message report
        report_to_sentry(
            message="Session timeout",
            level="warning",
            context={"duration_seconds": 600}
        )
    """
    sentry_sdk = _get_sentry_sdk()
    if not sentry_sdk:
        print(f"Sentry not available. Would have reported: {message}", flush=True)
        return False

    try:
        # Build extras/context
        extras = {
            "timestamp": datetime.now().isoformat(),
            **(context or {}),
        }

        # Capture screenshot if requested
        actual_screenshot_path = screenshot_path
        if capture_screenshot_flag and device:
            actual_screenshot_path = capture_screenshot(device, filename_prefix="sentry", ig_username=context.get("ig_username", "") if context else "")

        # Get current scope (recommended pattern)
        scope = sentry_sdk.get_current_scope()

        # Add tags
        if tags:
            for key, value in tags.items():
                scope.set_tag(key, value)

        # Add extras
        for key, value in extras.items():
            scope.set_extra(key, value)

        # Add screenshot as attachment if available (use path directly)
        if actual_screenshot_path and os.path.exists(actual_screenshot_path):
            scope.add_attachment(path=actual_screenshot_path)

        # Report
        if exception:
            sentry_sdk.capture_exception(exception)
        else:
            # Map level string to sentry level
            level_map = {
                "debug": "debug",
                "info": "info",
                "warning": "warning",
                "error": "error",
                "fatal": "fatal",
            }
            sentry_sdk.capture_message(message, level=level_map.get(level, "error"))

        print(f"Reported to Sentry: {message}", flush=True)
        return True

    except Exception as e:
        print(f"Failed to report to Sentry: {e}", flush=True)
        return False


def report_challenge_with_screenshot(
    device,
    challenge_type: str,
    ig_username: str,
    additional_context: Optional[Dict[str, Any]] = None,
    stage: str = "",
) -> str:
    """
    Convenience function to report an Instagram login challenge with screenshot.

    This is designed specifically for the challenge handling flow.

    Args:
        device: The device facade object
        challenge_type: Type of challenge (e.g., "selfie", "id_upload", "unknown")
        ig_username: Instagram username
        additional_context: Additional context to include
        stage: Stage where challenge was detected (e.g., "after_password", "after_2fa")

    Returns:
        str: Path to screenshot if captured, empty string otherwise
    """
    # Build context
    context = {
        "challenge_type": challenge_type,
        "ig_username": ig_username,
        "stage": stage,
        **(additional_context or {}),
    }

    # Capture screenshot first (always capture for challenges)
    screenshot_path = capture_screenshot(device, filename_prefix=f"challenge_{challenge_type}", ig_username=ig_username)

    # Report to Sentry
    report_to_sentry(
        message=f"Instagram login challenge: {challenge_type}",
        level="error",
        context=context,
        screenshot_path=screenshot_path,
        tags={
            "challenge_type": challenge_type,
            "username": ig_username,
            "stage": stage
        }
    )

    return screenshot_path or ""


def report_exception_with_screenshot(
    device,
    exception: Exception,
    ig_username: str = "",
    additional_context: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Convenience function to report an exception with screenshot.

    Args:
        device: The device facade object
        exception: The exception to report
        ig_username: Instagram username (optional)
        additional_context: Additional context to include

    Returns:
        bool: True if reported successfully
    """
    if not ig_username:
        ig_username = AppState.configyml.get('username')
    context = {
        "ig_username": ig_username,
        "exception_type": type(exception).__name__,
        **(additional_context or {}),
    }

    return report_to_sentry(
        message=f"Exception: {str(exception)}",
        level="error",
        context=context,
        capture_screenshot_flag=True,
        device=device,
        exception=exception,
        tags={"exception_type": type(exception).__name__},
    )


# ============================================================================
# Utility Functions
# ============================================================================

def is_sentry_enabled() -> bool:
    """Check if Sentry is configured and enabled."""
    return bool(os.environ.get('SENTRY_DSN'))


def get_screenshots_dir() -> Path:
    """Get the directory where screenshots are saved."""
    return Path("/tmp/ig_screenshots")


def cleanup_old_screenshots(max_age_hours: int = 24) -> int:
    """
    Clean up old screenshots to prevent disk space issues.

    Args:
        max_age_hours: Maximum age of screenshots to keep (in hours)

    Returns:
        int: Number of files deleted
    """
    screenshots_dir = get_screenshots_dir()
    if not screenshots_dir.exists():
        return 0

    deleted_count = 0
    cutoff_time = time.time() - (max_age_hours * 3600)

    for screenshot_file in screenshots_dir.glob("*.png"):
        try:
            if screenshot_file.stat().st_mtime < cutoff_time:
                screenshot_file.unlink()
                deleted_count += 1
        except Exception as e:
            print(f"Failed to delete {screenshot_file}: {e}", flush=True)

    if deleted_count > 0:
        print(f"Cleaned up {deleted_count} old screenshots", flush=True)

    return deleted_count


if __name__ == "__main__":
    # Test/demo
    print("Sentry Reporter Module")
    print(f"Sentry enabled: {is_sentry_enabled()}")
    print(f"Screenshots directory: {get_screenshots_dir()}")
