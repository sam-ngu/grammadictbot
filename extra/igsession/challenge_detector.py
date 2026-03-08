"""
Instagram Challenge Detector - Enums, Patterns, and Detector Class

Contains:
- ChallengeCategory and ChallengeType enums
- ChallengeInfo dataclass
- SCREEN_PATTERNS and TWO_FACTOR_PATTERNS
- ChallengeDetector class (state-machine-based detector)
- detect_selfie_challenge utility
"""

import time
import logging
from enum import Enum
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

from GramAddict.core.device_facade import Timeout
from GramAddict.core.views import case_insensitive_re
from GramAddict.core.webhook import send_webhook
from extra.utils.sentry_reporter import report_challenge_with_screenshot

logger = logging.getLogger(__name__)


# ============================================================================
# TIMEOUT CONSTANTS
# ============================================================================

DEFAULT_2FA_TIMEOUT = 600        # 10 minutes - for TOTP, SMS, WhatsApp 2FA
DEFAULT_CAPTCHA_TIMEOUT = 300    # 5 minutes - for captcha challenges
DEFAULT_REVIEW_TIMEOUT = 600     # 10 minutes - for device review, suspicious activity
DEFAULT_REACTIVATION_TIMEOUT = 300  # 5 minutes - for account reactivation
DEFAULT_TOTAL_TIMEOUT = 1200     # 20 minutes - maximum total login time


class ChallengeCategory(Enum):
    """Challenge category for handling strategy"""
    AUTO_HANDLE = "auto_handle"      # Can be automatically handled
    USER_WAIT = "user_wait"          # Requires user input with timeout
    IMPOSSIBLE = "impossible"        # Cannot be automated, needs manual intervention


class ChallengeType(Enum):
    """All known challenge types"""
    # Category A: AUTO_HANDLE
    CONSENT = "consent"
    TRUSTED_DEVICE = "trusted_device"
    SUSPECT_SCREEN = "suspect_screen"
    SAVE_PROFILE = "save_profile"
    DISMISS_BUTTON = "dismiss_button"

    # Category B: USER_WAIT
    TWO_FACTOR_TOTP = "2fa_totp"
    TWO_FACTOR_SMS = "2fa_sms"
    TWO_FACTOR_WHATSAPP = "2fa_whatsapp"
    CAPTCHA = "captcha"
    NEW_DEVICE_REVIEW = "new_device_review"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    ACCOUNT_REACTIVATION = "account_reactivation"
    OTHER_DEVICE_APPROVAL = "other_device_approval"

    # Category C: IMPOSSIBLE
    SELFIE = "selfie"
    ID_UPLOAD = "id_upload"
    AGE_VERIFICATION = "age_verification"
    PASSWORD_CHANGE = "password_change"
    WRONG_PASSWORD = "wrong_password"  # Parent type for wrong password variants
    WRONG_PASSWORD_CHECK_EMAIL = "wrong_password_check_email"
    WRONG_PASSWORD_TRY_ANOTHER = "wrong_password_try_another"
    ACCOUNT_SUSPENDED = "account_suspended"
    ACCOUNT_DISABLED = "account_disabled"
    ACCOUNT_HACKED = "account_hacked"
    UNKNOWN = "unknown"

    def to_error_string(self) -> str:
        """Convert challenge type to error return string."""
        mapping = {
            ChallengeType.SELFIE: 'unable_to_login_due_to_selfie_challenge',
            ChallengeType.ID_UPLOAD: 'unable_to_login_due_to_id_verification',
            ChallengeType.AGE_VERIFICATION: 'unable_to_login_due_to_age_verification',
            ChallengeType.PASSWORD_CHANGE: 'unable_to_login_due_to_password_change',
            ChallengeType.WRONG_PASSWORD: 'unable_to_login_due_to_wrong_password',
            ChallengeType.WRONG_PASSWORD_CHECK_EMAIL: 'unable_to_login_due_to_wrong_password',
            ChallengeType.WRONG_PASSWORD_TRY_ANOTHER: 'unable_to_login_due_to_wrong_password',
            ChallengeType.ACCOUNT_SUSPENDED: 'unable_to_login_due_to_account_suspended',
            ChallengeType.ACCOUNT_DISABLED: 'unable_to_login_due_to_account_disabled',
            ChallengeType.ACCOUNT_HACKED: 'unable_to_login_due_to_account_hacked',
            ChallengeType.UNKNOWN: 'unable_to_login_due_to_unknown_challenge',
        }
        return mapping.get(self, 'unable_to_login_due_to_unknown_challenge')


@dataclass
class ChallengeInfo:
    """Information about a detected challenge.

    Attributes:
        challenge_type: The specific type of challenge detected (e.g., SELFIE, TWO_FACTOR_SMS)
        category: The handling strategy category (AUTO_HANDLE, USER_WAIT, or IMPOSSIBLE)
        patterns_matched: List of text patterns that matched to identify this challenge
        timeout_seconds: Maximum time to wait for user input (0 for immediate action)
        action: Suggested action to take (e.g., "click_dismiss", "wait_for_code")
    """
    challenge_type: ChallengeType
    category: ChallengeCategory
    patterns_matched: list
    timeout_seconds: int
    action: str = ""

    def to_dict(self) -> dict:
        """Convert to dict with enum values serialized as strings."""
        return {
            'challenge_type': self.challenge_type.value,
            'category': self.category.value,
            'patterns_matched': self.patterns_matched,
            'timeout_seconds': self.timeout_seconds,
            'action': self.action,
        }


# ============================================================================
# DETECTION PATTERNS (from CHALLENGE_SCREENS_ANALYSIS.md)
# ============================================================================

SCREEN_PATTERNS = {
    # ==================== Category A: AUTO-HANDLE ====================
    "CONSENT": {
        # NOTE: Patterns are specific to avoid false positives on generic "accept" buttons
        "patterns": ["terms of service", "privacy policy", "accept & continue", "i agree to the terms", "agree & continue", "i agree"],
        "category": ChallengeCategory.AUTO_HANDLE,
        "timeout": 0,
        "action": "click_accept",
    },
    "TRUSTED_DEVICE": {
        "patterns": ["trust this device", "remember this device", "don't ask again", "save this device"],
        "category": ChallengeCategory.AUTO_HANDLE,
        "timeout": 0,
        "action": "click_trust",
    },

    # ==================== Category B: USER-WAIT ====================
    "TWO_FACTOR_TOTP": {
        # Authenticator app specific patterns - must NOT match SMS patterns
        "patterns": ["authentication app", "authenticator app", "google authenticator", "verification app", "totp code", "get code from app"],
        "category": ChallengeCategory.USER_WAIT,
        "timeout": DEFAULT_2FA_TIMEOUT,
        "action": "wait_for_code",
    },
    "TWO_FACTOR_SMS": {
        # SMS specific patterns - must NOT match authenticator app patterns
        "patterns": ["we sent a code to your phone", "sent to your phone", "sms verification", "text message verification", "check your sms", "resend sms", "SMS"],
        "category": ChallengeCategory.USER_WAIT,
        "timeout": DEFAULT_2FA_TIMEOUT,
        "action": "wait_for_code",
    },
    "TWO_FACTOR_WHATSAPP": {
        "patterns": ["whatsapp", "wa_key", "whatsapp verification", "whatsapp code"],
        "category": ChallengeCategory.USER_WAIT,
        "timeout": DEFAULT_2FA_TIMEOUT,
        "action": "wait_for_code",
    },
    "CAPTCHA": {
        "patterns": ["captcha", "not a robot", "select all images", "verify you're human", "i'm not a robot"],
        "category": ChallengeCategory.USER_WAIT,
        "timeout": DEFAULT_CAPTCHA_TIMEOUT,
        "action": "wait_for_captcha",
    },
    "NEW_DEVICE_REVIEW": {
        "patterns": ["new device", "unrecognized device", "verify it's you", "was this you", "confirm your identity"],
        "category": ChallengeCategory.USER_WAIT,
        "timeout": DEFAULT_REVIEW_TIMEOUT,
        "action": "wait_for_confirmation",
    },
    "SUSPICIOUS_ACTIVITY": {
        "patterns": ["unusual activity", "suspicious login", "we noticed something unusual"],
        "category": ChallengeCategory.USER_WAIT,
        "timeout": DEFAULT_REVIEW_TIMEOUT,
        "action": "wait_for_confirmation",
    },
    "ACCOUNT_REACTIVATION": {
        "patterns": ["reactivate", "account deactivated", "log in to reactivate"],
        "category": ChallengeCategory.USER_WAIT,
        "timeout": DEFAULT_REACTIVATION_TIMEOUT,
        "action": "wait_for_reactivation",
    },
    "OTHER_DEVICE_APPROVAL": {
        "patterns": ["check your notifications on another device", "waiting for approval", "another device"],
        "category": ChallengeCategory.USER_WAIT,
        "timeout": DEFAULT_2FA_TIMEOUT,
        "action": "wait_for_another_device_approval",
    },

    # ==================== Category C: IMPOSSIBLE ====================
    "SELFIE": {
        "patterns": ["take a selfie", "video selfie", "face verification", "record a video", "turn your head", "blink"],
        "category": ChallengeCategory.IMPOSSIBLE,
        "timeout": 0,
        "action": "manual_intervention",
    },
    "ID_UPLOAD": {
        "patterns": ["upload", "id card", "identity document", "government id", "passport", "driver's license"],
        "category": ChallengeCategory.IMPOSSIBLE,
        "timeout": 0,
        "action": "manual_intervention",
    },
    "AGE_VERIFICATION": {
        "patterns": ["verify your age", "birthday", "you must be", "13 years", "under 18", "age restriction"],
        "category": ChallengeCategory.IMPOSSIBLE,
        "timeout": 0,
        "action": "manual_intervention",
    },
    "PASSWORD_CHANGE": {
        "patterns": ["change password", "update password", "new password", "create new password", "your password has expired"],
        "category": ChallengeCategory.IMPOSSIBLE,
        "timeout": 0,
        "action": "manual_intervention",
    },
    "WRONG_PASSWORD_CHECK_EMAIL": {
        "patterns": ["Check your email"],
        "category": ChallengeCategory.IMPOSSIBLE,
        "timeout": 0,
        "action": "wrong_password",
    },
    # "WRONG_PASSWORD_TRY_ANOTHER": {
    #     "patterns": ["Try another way"],
    #     "category": ChallengeCategory.IMPOSSIBLE,
    #     "timeout": 0,
    #     "action": "wrong_password",
    # },
    "ACCOUNT_SUSPENDED": {
        "patterns": ["account suspended", "temporarily suspended", "suspended for violating"],
        "category": ChallengeCategory.IMPOSSIBLE,
        "timeout": 0,
        "action": "manual_intervention",
    },
    "ACCOUNT_DISABLED": {
        "patterns": ["account disabled", "permanently disabled", "your account has been disabled"],
        "category": ChallengeCategory.IMPOSSIBLE,
        "timeout": 0,
        "action": "manual_intervention",
    },
    "ACCOUNT_HACKED": {
        "patterns": ["secure your account", "hacked account", "we detected unusual"],
        "category": ChallengeCategory.IMPOSSIBLE,
        "timeout": 0,
        "action": "manual_intervention",
    },

    # ==================== Current Working Auto-Handles ====================
    "SUSPECT_SCREEN": {
        "patterns": ["suspect automated behavior"],
        "category": ChallengeCategory.AUTO_HANDLE,
        "action": "click_dismiss",
        "timeout": 0,
    },
    "SAVE_PROFILE": {
        "patterns": ["Save"],
        "category": ChallengeCategory.AUTO_HANDLE,
        "action": "click_save",
        "timeout": 0,
    },
    "DISMISS_BUTTON": {
        "patterns": ["Dismiss"],
        "category": ChallengeCategory.AUTO_HANDLE,
        "action": "click",
        "timeout": 0,
    },
}

# 2FA flow specific patterns (used by legacy detector in session.py)
# NOTE: This is kept for backward compatibility with the legacy challenge detector.
# The new ChallengeDetector class uses SCREEN_PATTERNS instead.
TWO_FACTOR_PATTERNS = {
    "confirm_its_you": "Confirm it's you",
    "continue_button": "Continue",
    "enter_confirmation_code": "Enter confirmation code",
    "wait_a_moment": "Wait a moment",
}


# ============================================================================
# SELFIE CHALLENGE DETECTION (Used by both detectors)
# ============================================================================

def detect_selfie_challenge(device) -> bool:
    """Detect if selfie challenge is shown on screen.

    CRITICAL: Uses className='android.view.View' for Bloks-based screens.
    Uses Timeout.TINY for fast detection to avoid delays.
    """
    selfie_indicators = [
        "Take a selfie",
        "take a selfie to verify",
        "We need to verify it's you",
        "Verify your identity",
        "Face verification",
        "Face scan",
        "selfie verification",
        "We need to confirm it's you",
        "Take a photo of your face",
    ]
    for indicator in selfie_indicators:
        if device.find(textMatches=case_insensitive_re(indicator), className='android.view.View').exists(Timeout.TINY):
            return True
    return False


# ============================================================================
# CHALLENGE DETECTOR CLASS (Challenge Loop Architecture)
# ============================================================================

class ChallengeDetector:
    """
    State-machine-based challenge detector.

    Implements the challenge loop architecture from LOGIN_FUNCTION_ENHANCEMENT_PLAN.md
    Section 11. This approach continuously detects and handles challenges in a loop
    until login succeeds or an impossible challenge is encountered.

    NOTE: Priority order is critical for correct detection:
    - IMPOSSIBLE challenges are checked first for fail-fast behavior
    - SUSPECT_SCREEN must come before DISMISS_BUTTON (both use "Dismiss" text)
    - AUTO_HANDLE challenges are checked before USER_WAIT to auto-resolve when possible
    """

    # Priority order - check most specific/automatable first
    # IMPORTANT: SUSPECT_SCREEN must come before DISMISS_BUTTON because both
    # look for "Dismiss" text, but SUSPECT_SCREEN has the more specific trigger pattern
    CHALLENGE_PRIORITY = [
        # Category C: IMPOSSIBLE (check first to fail fast)
        "SELFIE",
        "ID_UPLOAD",
        "AGE_VERIFICATION",
        "PASSWORD_CHANGE",
        "WRONG_PASSWORD_CHECK_EMAIL",
        # "WRONG_PASSWORD_TRY_ANOTHER",  # Patterns commented out - not implemented
        "ACCOUNT_SUSPENDED",
        "ACCOUNT_DISABLED",
        "ACCOUNT_HACKED",

        # Category A: AUTO_HANDLE
        "CONSENT",
        "TRUSTED_DEVICE",
        "SUSPECT_SCREEN",  # Must be before DISMISS_BUTTON - uses "suspect automated behavior" pattern
        "SAVE_PROFILE",
        "DISMISS_BUTTON",  # Generic dismiss - checked after specific SUSPECT_SCREEN

        # Category B: USER_WAIT
        "TWO_FACTOR_TOTP",
        "TWO_FACTOR_SMS",
        "TWO_FACTOR_WHATSAPP",
        "CAPTCHA",
        "NEW_DEVICE_REVIEW",
        "SUSPICIOUS_ACTIVITY",
        "ACCOUNT_REACTIVATION",
        "OTHER_DEVICE_APPROVAL",
    ]

    def __init__(self, device, ig_username: str, interval: float = 0.5):
        self.device = device
        self.ig_username = ig_username
        self.interval = interval
        self.last_challenge = None
        self.challenge_start_time = None

    def detect(self) -> Optional[ChallengeInfo]:
        """
        Detect current challenge on screen.

        Returns:
            ChallengeInfo if challenge detected, None otherwise
        """
        # Check for selfie challenge first (highest priority impossible)
        if detect_selfie_challenge(self.device):
            logger.debug("Selfie challenge detected")
            return ChallengeInfo(
                challenge_type=ChallengeType.SELFIE,
                category=ChallengeCategory.IMPOSSIBLE,
                patterns_matched=["selfie indicators"],
                timeout_seconds=0,
                action="manual_intervention"
            )

        # Check all patterns in priority order
        for challenge_name in self.CHALLENGE_PRIORITY:
            config = SCREEN_PATTERNS.get(challenge_name)
            if not config:
                continue

            patterns = config.get("patterns", [])
            for pattern in patterns:
                # CRITICAL: Use className='android.view.View' for Bloks screens
                # Use Timeout.TINY for fast detection (avoids 20-40 second delays)
                if self.device.find(textMatches=case_insensitive_re(pattern), className='android.view.View').exists(Timeout.TINY):
                    print(f"Challenge detected: {challenge_name} (pattern: '{pattern}')", flush=True)
                    return ChallengeInfo(
                        challenge_type=ChallengeType[challenge_name],
                        category=config["category"],
                        patterns_matched=[pattern],
                        timeout_seconds=config["timeout"],
                        action=config.get("action", "")
                    )

        return None

    def is_logged_in(self) -> bool:
        """Check if login was successful (tab bar present)."""
        return self.device.find(
            resourceId="com.instagram.android:id/tab_bar"
        ).exists(Timeout.TINY)

    def handle_auto_challenge(self, challenge: ChallengeInfo) -> None:
        """Auto-handle consent, trusted device, suspect, save profile challenges."""

        if challenge.challenge_type == ChallengeType.CONSENT:
            # Click accept/agree buttons
            for btn_text in ["Accept", "Agree", "I Agree", "Continue", "OK"]:
                btn = self.device.find(className='android.view.View', textMatches=case_insensitive_re(btn_text))
                if btn.exists(Timeout.TINY):
                    btn.click()
                    send_webhook({
                        'event': 'login_challenge',
                        'payload': {
                            **challenge.to_dict(),
                            'button_clicked': btn_text,
                        }
                    })
                    print(f"Auto-handled consent: clicked {btn_text}", flush=True)
                    return

        elif challenge.challenge_type == ChallengeType.TRUSTED_DEVICE:
            # Click trust/remember device
            for pattern in ["Trust", "Remember", "Don't ask", "Save"]:
                elem = self.device.find(textContains=case_insensitive_re(pattern), className='android.view.View')
                if elem.exists(Timeout.TINY):
                    elem.click()
                    send_webhook({
                        'event': 'login_challenge',
                        'payload': {
                            **challenge.to_dict(),
                            'button_clicked': pattern,
                        }
                    })
                    print(f"Auto-handled trusted device: clicked {pattern}", flush=True)
                    return

        elif challenge.challenge_type == ChallengeType.SUSPECT_SCREEN:
            # Dismiss suspect automated behavior
            dismiss_btn = self.device.find(className='android.view.View', textMatches=case_insensitive_re("Dismiss"))
            if dismiss_btn.exists(Timeout.TINY):
                dismiss_btn.click()
                send_webhook({
                    'event': 'login_challenge',
                    'payload': challenge.to_dict()
                })
                print("Auto-handled suspect screen: clicked Dismiss", flush=True)
                return

        elif challenge.challenge_type == ChallengeType.SAVE_PROFILE:
            # Click Save profile button
            save_btn = self.device.find(className='android.view.View', textMatches=case_insensitive_re("Save"))
            if save_btn.exists(Timeout.TINY):
                save_btn.click_retry(sleep=5, maxretry=3)
                send_webhook({
                    'event': 'login_challenge',
                    'payload': challenge.to_dict()
                })
                print("Auto-handled save profile: clicked Save", flush=True)
                return

        elif challenge.challenge_type == ChallengeType.DISMISS_BUTTON:
            dismiss_btn = self.device.find(className='android.view.View', textMatches=case_insensitive_re("Dismiss"))
            if dismiss_btn.exists(Timeout.TINY):
                dismiss_btn.click()
                send_webhook({
                    'event': 'login_challenge',
                    'payload': challenge.to_dict()
                })
                print("Auto-handled: clicked Dismiss", flush=True)
                return

    def handle_user_wait_challenge(self, challenge: ChallengeInfo) -> str:
        """Handle user-wait challenges with webhook notification and timeout.

        This method sends a webhook notification and waits for the user to complete
        the challenge (e.g., enter 2FA code, solve captcha). It polls for login success.

        Args:
            challenge: The ChallengeInfo for the user-wait challenge

        Returns:
            'loggedin' if login successful, 'timeout' if timed out
        """
        print(f"User-wait challenge detected: {challenge.challenge_type.value}", flush=True)

        # Send webhook notification
        send_webhook({
            'event': 'login_challenge',
            'payload': challenge.to_dict()
        })

        # Wait for user action with timeout
        start_time = time.time()
        while time.time() - start_time < challenge.timeout_seconds:
            # Check if login successful
            if self.is_logged_in():
                print(f"User completed challenge: {challenge.challenge_type.value}", flush=True)
                return 'loggedin'

            # Check if challenge still present
            current_challenge = self.detect()
            if current_challenge and current_challenge.challenge_type != challenge.challenge_type:
                # Different challenge detected - let caller handle it
                print(f"Challenge changed from {challenge.challenge_type.value} to {current_challenge.challenge_type.value}", flush=True)
                return 'challenge_changed'

            time.sleep(self.interval)

        # Timeout exceeded
        logger.warning(f"User-wait challenge timed out after {challenge.timeout_seconds}s")
        return 'timeout'

    def handle_impossible_challenge(self, challenge: ChallengeInfo) -> str:
        """Handle impossible challenges with screenshot, Sentry report, and webhook notification.

        Returns:
            Error string indicating the type of failure
        """
        logger.error(f"Impossible challenge detected: {challenge.challenge_type.value}")

        # Capture screenshot and report to Sentry
        report_challenge_with_screenshot(
            device=self.device,
            challenge_type=challenge.challenge_type.value,
            ig_username=self.ig_username,
            additional_context={
                "patterns_matched": challenge.patterns_matched,
                "category": "impossible",
            },
            stage="challenge_loop"
        )

        # Send webhook
        send_webhook({
            'event': 'login_challenge',
            'payload': challenge.to_dict()
        })

        # Return appropriate error value using the enum method
        return challenge.challenge_type.to_error_string()
