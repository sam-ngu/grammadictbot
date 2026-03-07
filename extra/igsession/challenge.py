"""
Instagram Login Challenge Handler

Provides two challenge detection approaches:
1. legacy_challenge_detector() - The current working linear flow
2. new_challenge_detector() - Challenge loop architecture from the plan

Both use className='android.view.View' for Bloks-based screens (CRITICAL).
"""

import time
from enum import Enum
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

from GramAddict.core.device_facade import Timeout
from GramAddict.core.webhook import send_webhook
from extra.utils.sentry_reporter import report_challenge_with_screenshot


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

    # Category C: IMPOSSIBLE
    SELFIE = "selfie"
    ID_UPLOAD = "id_upload"
    AGE_VERIFICATION = "age_verification"
    PASSWORD_CHANGE = "password_change"
    WRONG_PASSWORD_CHECK_EMAIL = "wrong_password_check_email"
    WRONG_PASSWORD_TRY_ANOTHER = "wrong_password_try_another"
    ACCOUNT_SUSPENDED = "account_suspended"
    ACCOUNT_DISABLED = "account_disabled"
    ACCOUNT_HACKED = "account_hacked"
    UNKNOWN = "unknown"


@dataclass
class ChallengeInfo:
    """Information about a detected challenge"""
    challenge_type: ChallengeType
    category: ChallengeCategory
    patterns_matched: list
    timeout_seconds: int
    action: str = ""


# ============================================================================
# DETECTION PATTERNS (from CHALLENGE_SCREENS_ANALYSIS.md)
# ============================================================================

SCREEN_PATTERNS = {
    # ==================== Category A: AUTO-HANDLE ====================
    "CONSENT": {
        "patterns": ["terms of service", "privacy policy", "accept", "agree", "i agree"],
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
        "patterns": ["authentication app", "authenticator app", "totp", "google authenticator", "6-digit code", "verification app"],
        "category": ChallengeCategory.USER_WAIT,
        "timeout": 600,  # 10 min
        "action": "wait_for_code",
    },
    "TWO_FACTOR_SMS": {
        "patterns": ["sms", "text message", "we sent a code", "verification code", "resend sms", "sent to your phone"],
        "category": ChallengeCategory.USER_WAIT,
        "timeout": 600,
        "action": "wait_for_code",
    },
    "TWO_FACTOR_WHATSAPP": {
        "patterns": ["whatsapp", "wa_key", "whatsapp verification"],
        "category": ChallengeCategory.USER_WAIT,
        "timeout": 600,
        "action": "wait_for_code",
    },
    "CAPTCHA": {
        "patterns": ["captcha", "not a robot", "select all images", "verify you're human", "i'm not a robot"],
        "category": ChallengeCategory.USER_WAIT,
        "timeout": 300,  # 5 min
        "action": "wait_for_captcha",
    },
    "NEW_DEVICE_REVIEW": {
        "patterns": ["new device", "unrecognized device", "verify it's you", "was this you", "confirm your identity"],
        "category": ChallengeCategory.USER_WAIT,
        "timeout": 600,
        "action": "wait_for_confirmation",
    },
    "SUSPICIOUS_ACTIVITY": {
        "patterns": ["unusual activity", "suspicious login", "we noticed something unusual"],
        "category": ChallengeCategory.USER_WAIT,
        "timeout": 600,
        "action": "wait_for_confirmation",
    },
    "ACCOUNT_REACTIVATION": {
        "patterns": ["reactivate", "account deactivated", "log in to reactivate"],
        "category": ChallengeCategory.USER_WAIT,
        "timeout": 300,
        "action": "wait_for_reactivation",
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
    "WRONG_PASSWORD_TRY_ANOTHER": {
        "patterns": ["Try another way"],
        "category": ChallengeCategory.IMPOSSIBLE,
        "timeout": 0,
        "action": "wrong_password",
    },
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

# 2FA flow specific patterns (used by legacy detector)
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
        if device.find(text=indicator, className='android.view.View').exists(Timeout.SHORT):
            return True
    return False


# ============================================================================
# LEGACY CHALLENGE DETECTOR (Current Working Implementation)
# ============================================================================

def legacy_challenge_detector(device, ig_username: str, interval: float = 0.5) -> str:
    """
    Legacy challenge detector - the current working linear flow.

    This is the proven, tested implementation moved from session.py.
    It handles challenges in a sequential manner:
    1. Selfie challenge check
    2. Wrong password detection
    3. 2FA flow (two-phase)
    4. Selfie challenge after 2FA
    5. Suspect screen auto-dismiss
    6. Save profile auto-click
    7. Final selfie challenge check

    Args:
        device: The device facade object
        ig_username: Instagram username for webhooks
        interval: Sleep interval for wait loops

    Returns:
        str: Result status ('loggedin', 'timeout', 'unable_to_login_due_to_*')
    """
    print('starting legacy challenge detection', flush=True)

    # ==================== 1. Selfie Challenge (after password) ====================
    if detect_selfie_challenge(device):
        print('selfie challenge detected after password', flush=True)
        # Capture screenshot and report to Sentry
        report_challenge_with_screenshot(
            device=device,
            challenge_type="selfie",
            ig_username=ig_username,
            stage="after_password"
        )
        send_webhook({'event': 'login_selfie_challenge', 'payload': {'message': 'selfie challenge detected after password'}})
        return 'unable_to_login_due_to_selfie_challenge'

    # TODO: May get prompt to 'check your notification on another device' for login approval
    

    # ==================== 2. Wrong Password Detection ====================
    # user may enter wrong password - verify if following is correct
    # check if wrong password screen, if so send webhook 
    check_email = device.find(className='android.view.View', text="Check your email")
    try_another_way = device.find(className='android.view.View', text="Try another way")

    # dont click on back button, the ig behaviour is not consistent, better to restart a new machine 
    print('checking if user entered wrong password', flush=True)
    is_in_wrong_password_screen = check_email.exists(Timeout.SHORT) or try_another_way.exists(Timeout.SHORT)
    if is_in_wrong_password_screen:
        send_webhook({'event': 'login_wrong_password'})
        print('user entered wrong password', flush=True)
        raise Exception('user entered wrong password')

    device.deviceV2.sleep(1)

    # ==================== 3. Two-Phase 2FA Flow ====================
    # Phase 1: "Confirm it's you" screen
    # may see code verify screen
    #  check if got the send code verify email screen
    verify_code = device.find(className='android.view.View', text=TWO_FACTOR_PATTERNS["confirm_its_you"])
    verify_confirm_button = device.find(className='android.view.View', text=TWO_FACTOR_PATTERNS["continue_button"])

    timeout = 60 * 10  # 10 min
    print('checking if user need to enter 2FA code', flush=True)
    needs_2fa = verify_code.exists(Timeout.MEDIUM)
    if needs_2fa:
        send_webhook({'event': 'login_needs_2fa'})

    # Wait for user to click on continue button
    while (verify_code.exists(Timeout.TINY) and verify_confirm_button.exists(Timeout.TINY)):
        device.deviceV2.sleep(interval)
        timeout -= interval
        if timeout <= 0:
            print('timed out waiting for user to proceed with 2fa')
            return 'timeout'

    print('user proceed with 2fa to get code', flush=True)
    send_webhook({'event': 'login_proceed_2fa_get_code'})

    # Phase 2: Code entry screen
    enter_code = device.find(text=TWO_FACTOR_PATTERNS["enter_confirmation_code"])
    # check if user clicked on resend code and the Wait a moment modal pops up
    resend_code_wait_a_moment = device.find(text=TWO_FACTOR_PATTERNS["wait_a_moment"])

    while enter_code.exists(Timeout.TINY) or resend_code_wait_a_moment.exists(Timeout.TINY):
        device.deviceV2.sleep(interval)
        timeout -= interval
        if timeout <= 0:
            print('timed out waiting for user to enter verification code')
            return 'timeout'

    send_webhook({'event': 'login_passed_2fa'})
    print('passed verification code', flush=True)

    # ==================== 4. Selfie Challenge (after 2FA) ====================
    if detect_selfie_challenge(device):
        print('selfie challenge detected after 2fa', flush=True)
        # Capture screenshot and report to Sentry
        report_challenge_with_screenshot(
            device=device,
            challenge_type="selfie",
            ig_username=ig_username,
            stage="after_2fa"
        )
        send_webhook({'event': 'login_selfie_challenge', 'payload': {'message': 'selfie challenge detected after 2fa'}})
        return 'unable_to_login_due_to_selfie_challenge'

    # ==================== 5. Suspect Screen Auto-Dismiss ====================
    device.deviceV2.sleep(1)
    is_suspect = device.find(className='android.view.View', text="suspect automated behavior")
    timeout = 60 * 2  # 2 min
    print('checking for user to dismiss suspect screen', flush=True)
    if is_suspect.exists(Timeout.MEDIUM):
        send_webhook({'event': 'login_suspect_screen'})
        dismiss_btn = device.find(className='android.view.View', text="Dismiss")
        dismiss_btn.click()

    device.deviceV2.sleep(1)

    # ==================== 6. Save Profile Auto-Click ====================
    save_profile_button = device.find(className='android.view.View', text="Save")
    if save_profile_button.exists(Timeout.MEDIUM):
        save_profile_button.click_retry(sleep=5, maxretry=3)
        send_webhook({'event': 'login_saved_profile'})
    device.deviceV2.sleep(1)

    # ==================== 7. Final Selfie Challenge Check ====================
    if detect_selfie_challenge(device):
        print('selfie challenge detected before login success', flush=True)
        # Capture screenshot and report to Sentry
        report_challenge_with_screenshot(
            device=device,
            challenge_type="selfie",
            ig_username=ig_username,
            stage="final_check"
        )
        send_webhook({'event': 'login_selfie_challenge', 'payload': {'message': 'selfie challenge detected final stage'}})
        return 'unable_to_login_due_to_selfie_challenge'

    # ==================== 8. Login Success Verification ====================
    # Verify we are on a known success screen before returning 'loggedin'
    device.deviceV2.sleep(1)

    # Check for known success indicators
    tab_bar = device.find(resourceId="com.instagram.android:id/tab_bar")
    setup_new_device = device.find(className='android.view.View', text="Set up on new device")
    save_profile_button = device.find(className='android.view.View', text="Save")
    allow_button = device.find(className='android.view.View', text="Allow")

    is_logged_in_screen = tab_bar.exists(Timeout.MEDIUM)
    is_setup_new_device = setup_new_device.exists(Timeout.MEDIUM)
    is_save_profile = save_profile_button.exists(Timeout.MEDIUM)
    is_allow_button = allow_button.exists(Timeout.MEDIUM)

    # If we see setup new device or allow button, click it
    if is_setup_new_device or is_allow_button:
        allow_button.click_retry(sleep=5, maxretry=3)
        device.deviceV2.sleep(1)

    # Final verification: check if any success indicator is present
    if is_logged_in_screen or is_setup_new_device or is_save_profile or is_allow_button:
        print('login success verified', flush=True)
        return 'loggedin'

    # Unknown scenario - none of the expected success indicators found
    print('unknown login state - no success indicators found', flush=True)
    report_challenge_with_screenshot(
        device=device,
        challenge_type="unknown_login_state",
        ig_username=ig_username,
        stage="final_verification"
    )
    send_webhook({
        'event': 'login_unknown_state',
        'payload': {
            'message': 'No known success indicators found after challenge handling'
        }
    })

    return 'unable_to_login_due_to_unknown_state'


# ============================================================================
# NEW CHALLENGE DETECTOR (Challenge Loop Architecture)
# ============================================================================

class ChallengeDetector:
    """
    State-machine-based challenge detector.

    Implements the challenge loop architecture from LOGIN_FUNCTION_ENHANCEMENT_PLAN.md
    Section 11. This approach continuously detects and handles challenges in a loop
    until login succeeds or an impossible challenge is encountered.
    """

    # Priority order - check most specific/automatable first
    CHALLENGE_PRIORITY = [
        # Category C: IMPOSSIBLE (check first to fail fast)
        "SELFIE",
        "ID_UPLOAD",
        "AGE_VERIFICATION",
        "PASSWORD_CHANGE",
        "WRONG_PASSWORD_CHECK_EMAIL",
        "WRONG_PASSWORD_TRY_ANOTHER",
        "ACCOUNT_SUSPENDED",
        "ACCOUNT_DISABLED",
        "ACCOUNT_HACKED",

        # Category A: AUTO_HANDLE
        "CONSENT",
        "TRUSTED_DEVICE",
        "SUSPECT_SCREEN",
        "SAVE_PROFILE",
        "DISMISS_BUTTON",

        # Category B: USER_WAIT
        "TWO_FACTOR_TOTP",
        "TWO_FACTOR_SMS",
        "TWO_FACTOR_WHATSAPP",
        "CAPTCHA",
        "NEW_DEVICE_REVIEW",
        "SUSPICIOUS_ACTIVITY",
        "ACCOUNT_REACTIVATION",
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
                if self.device.find(text=pattern, className='android.view.View').exists(Timeout.SHORT):
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
        ).exists(Timeout.SHORT)

    def handle_auto_challenge(self, challenge: ChallengeInfo) -> None:
        """Auto-handle consent, trusted device, suspect, save profile challenges."""

        if challenge.challenge_type == ChallengeType.CONSENT:
            # Click accept/agree buttons
            for btn_text in ["Accept", "Agree", "I Agree", "Continue", "OK"]:
                btn = self.device.find(className='android.view.View', text=btn_text)
                if btn.exists(Timeout.SHORT):
                    btn.click()
                    send_webhook({'event': 'login_consent_handled'})
                    print(f"Auto-handled consent: clicked {btn_text}", flush=True)
                    return

        elif challenge.challenge_type == ChallengeType.TRUSTED_DEVICE:
            # Click trust/remember device
            for pattern in ["Trust", "Remember", "Don't ask", "Save"]:
                elem = self.device.find(textContains=pattern, className='android.view.View')
                if elem.exists(Timeout.SHORT):
                    elem.click()
                    send_webhook({'event': 'login_trusted_device_handled'})
                    print(f"Auto-handled trusted device: clicked {pattern}", flush=True)
                    return

        elif challenge.challenge_type == ChallengeType.SUSPECT_SCREEN:
            # Dismiss suspect automated behavior
            dismiss_btn = self.device.find(className='android.view.View', text="Dismiss")
            if dismiss_btn.exists(Timeout.SHORT):
                send_webhook({'event': 'login_suspect_screen'})
                dismiss_btn.click()
                print("Auto-handled suspect screen: clicked Dismiss", flush=True)
                return

        elif challenge.challenge_type == ChallengeType.SAVE_PROFILE:
            # Click Save profile button
            save_btn = self.device.find(className='android.view.View', text="Save")
            if save_btn.exists(Timeout.SHORT):
                save_btn.click_retry(sleep=5, maxretry=3)
                send_webhook({'event': 'login_saved_profile'})
                print("Auto-handled save profile: clicked Save", flush=True)
                return

        elif challenge.challenge_type == ChallengeType.DISMISS_BUTTON:
            dismiss_btn = self.device.find(className='android.view.View', text="Dismiss")
            if dismiss_btn.exists(Timeout.SHORT):
                dismiss_btn.click()
                print("Auto-handled: clicked Dismiss", flush=True)
                return

    def handle_impossible_challenge(self, challenge: ChallengeInfo) -> str:
        """Handle impossible challenges with screenshot, Sentry report, and webhook notification."""

        print(f"Impossible challenge detected: {challenge.challenge_type.value}", flush=True)

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
            'event': f'login_impossible_challenge_{challenge.challenge_type.value}',
            'payload': {
                'challenge_type': challenge.challenge_type.value,
                'patterns_matched': challenge.patterns_matched,
            }
        })

        # Return appropriate error value
        error_mapping = {
            ChallengeType.SELFIE: 'unable_to_login_due_to_selfie_challenge',
            ChallengeType.ID_UPLOAD: 'unable_to_login_due_to_id_verification',
            ChallengeType.AGE_VERIFICATION: 'unable_to_login_due_to_age_verification',
            ChallengeType.PASSWORD_CHANGE: 'unable_to_login_due_to_password_change',
            ChallengeType.WRONG_PASSWORD_CHECK_EMAIL: 'unable_to_login_due_to_wrong_password',
            ChallengeType.WRONG_PASSWORD_TRY_ANOTHER: 'unable_to_login_due_to_wrong_password',
            ChallengeType.ACCOUNT_SUSPENDED: 'unable_to_login_due_to_account_suspended',
            ChallengeType.ACCOUNT_DISABLED: 'unable_to_login_due_to_account_disabled',
            ChallengeType.ACCOUNT_HACKED: 'unable_to_login_due_to_account_hacked',
            ChallengeType.UNKNOWN: 'unable_to_login_due_to_unknown_challenge',
        }

        return error_mapping.get(challenge.challenge_type, 'unable_to_login_due_to_unknown_challenge')


def new_challenge_detector(device, ig_username: str, interval: float = 0.5) -> str:
    """
    New challenge detector using challenge loop architecture.

    Implements a state-machine-based approach that continuously detects
    and handles challenges in a loop until:
    - Login succeeds (returns 'loggedin')
    - Timeout exceeded (returns 'timeout')
    - Impossible challenge detected (returns 'unable_to_login_due_to_*')

    This is the recommended approach from LOGIN_FUNCTION_ENHANCEMENT_PLAN.md Section 11.

    Args:
        device: The device facade object
        ig_username: Instagram username for webhooks
        interval: Sleep interval for wait loops

    Returns:
        str: Result status ('loggedin', 'timeout', 'unable_to_login_due_to_*')
    """
    print('starting new challenge loop detection', flush=True)

    detector = ChallengeDetector(device, ig_username, interval)

    # Total timeout: 20 minutes
    MAX_TOTAL_TIME = 60 * 20
    start_time = time.time()

    while time.time() - start_time < MAX_TOTAL_TIME:

        # 1. Check for login success (tab bar present)
        if detector.is_logged_in():
            return 'loggedin'

        # 2. Detect current challenge
        challenge = detector.detect()

        if challenge is None:
            # No challenge detected, wait briefly and continue
            time.sleep(interval)
            continue

        # 3. Skip if same challenge (still waiting for user)
        if challenge.challenge_type == detector.last_challenge:
            # Check for challenge timeout
            if detector.challenge_start_time and challenge.timeout_seconds > 0:
                if time.time() - detector.challenge_start_time > challenge.timeout_seconds:
                    print(f"Challenge timeout: {challenge.challenge_type.value}", flush=True)
                    return 'timeout'
            time.sleep(interval)
            continue

        # New challenge detected
        detector.last_challenge = challenge.challenge_type
        detector.challenge_start_time = time.time()
        print(f"Detected challenge: {challenge.challenge_type.value}", flush=True)

        # 4. Handle based on category
        if challenge.category == ChallengeCategory.IMPOSSIBLE:
            # Category C: Return error
            return detector.handle_impossible_challenge(challenge)

        elif challenge.category == ChallengeCategory.AUTO_HANDLE:
            # Category A: Auto-handle and reset for next challenge
            detector.handle_auto_challenge(challenge)
            detector.last_challenge = None
            detector.challenge_start_time = None
            time.sleep(1)  # Brief pause after auto-handling
            continue

        elif challenge.category == ChallengeCategory.USER_WAIT:
            # Category B: Send webhook and wait
            send_webhook({'event': f'login_{challenge.challenge_type.value}'})
            # Loop will wait and check for completion
            continue

    # Total timeout exceeded
    print('total timeout exceeded', flush=True)
    return 'timeout'


# ============================================================================
# MAIN HANDLER (Entry Point)
# ============================================================================

def handle_challenge(device, ig_username: str, interval: float = 0.5, use_legacy: bool = True) -> str:
    """
    Main entry point for challenge handling.

    By default uses legacy_challenge_detector which is the proven, tested implementation.
    Set use_legacy=False to use the new challenge loop architecture.

    Args:
        device: The device facade object
        ig_username: Instagram username for webhooks
        interval: Sleep interval for wait loops
        use_legacy: If True, use legacy detector (default). If False, use new detector.

    Returns:
        str: Result status ('loggedin', 'timeout', 'unable_to_login_due_to_*')
    """
    if use_legacy:
        return legacy_challenge_detector(device, ig_username, interval)
    else:
        return new_challenge_detector(device, ig_username, interval)


if __name__ == "__main__":
    # Test/demo code
    print("Challenge handler module loaded")
    print(f"Available challenge types: {len(SCREEN_PATTERNS)} patterns defined")
