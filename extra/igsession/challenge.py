"""
Instagram Login Challenge Handler

Provides two challenge detection approaches:
1. legacy_challenge_detector() - The current working linear flow
2. new_challenge_detector() - Challenge loop architecture from the plan

Both use className='android.view.View' for Bloks-based screens (CRITICAL).
"""

import time

from GramAddict.core.device_facade import Timeout
from GramAddict.core.webhook import send_webhook
from extra.utils.sentry_reporter import report_challenge_with_screenshot
from extra.igsession.challenge_detector import (
    ChallengeCategory,
    ChallengeType,
    ChallengeInfo,
    ChallengeDetector,
    SCREEN_PATTERNS,
    TWO_FACTOR_PATTERNS,
    detect_selfie_challenge,
)


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
        send_webhook({'event': 'login_unknown_state'})
        print('login unknown state', flush=True)
        report_challenge_with_screenshot(
            device=device,
            challenge_type="unknown_login_state",
            ig_username=ig_username,
            stage="after_password"
        )
        raise Exception('unknown_login_state')

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

    # Track unknown scenario (no challenge detected for extended period)
    unknown_scenario_start = None
    UNKNOWN_SCENARIO_THRESHOLD = 30  # seconds

    while (time.time() - start_time) < MAX_TOTAL_TIME:

        # 1. Check for login success (tab bar present)
        if detector.is_logged_in():
            return 'loggedin'

        # 2. Detect current challenge
        challenge = detector.detect()

        if challenge is None:
            # No challenge detected - track duration for unknown scenario detection
            if unknown_scenario_start is None:
                unknown_scenario_start = time.time()
            elif time.time() - unknown_scenario_start > UNKNOWN_SCENARIO_THRESHOLD:
                # Unknown scenario: no challenge detected for 30+ seconds
                print(f'unknown scenario detected - no challenge for {UNKNOWN_SCENARIO_THRESHOLD}s', flush=True)
                report_challenge_with_screenshot(
                    device=device,
                    challenge_type="unknown_login_state",
                    ig_username=ig_username,
                    stage="no_challenge_detected"
                )
                send_webhook({
                    'event': 'login_unknown_state',
                    'payload': {
                        'message': f'No challenge detected for {UNKNOWN_SCENARIO_THRESHOLD} seconds'
                    }
                })
                # Reset timer to avoid repeated reports, report once every 30 seconds
                unknown_scenario_start = time.time()
                # should not return here, continue to next iteration, let user decide what to do
                # return 'login_unknown_state'

            time.sleep(interval)
            continue

        # Reset unknown scenario timer when a challenge is detected
        unknown_scenario_start = None

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
            result = detector.handle_user_wait_challenge(challenge)
            if result == 'timeout':
                return 'timeout'
            elif result == 'loggedin':
                return 'loggedin'
            # result == 'challenge_changed': reset and continue loop to detect new challenge
            detector.last_challenge = None
            detector.challenge_start_time = None
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
