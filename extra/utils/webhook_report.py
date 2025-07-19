import json
import logging
from datetime import datetime
from typing import Optional

import requests
import yaml
from colorama import Fore, Style

from GramAddict.core.plugin_loader import Plugin
from GramAddict.core.webhook import send_webhook
from extra.utils.app_state import AppState

logger = logging.getLogger(__name__)

# TODO: use sqlite instead of json to handle session
def load_sessions(username) -> Optional[dict]:
    try:
        with open(f"accounts/{username}/sessions.json") as json_data:
            return json.load(json_data)
    except FileNotFoundError:
        print("No session data found. Skipping report generation.", flush=True)
        return None


def _calculate_session_duration(session):
    try:
        start_datetime = datetime.strptime(
            session["start_time"], "%Y-%m-%d %H:%M:%S.%f"
        )
        finish_datetime = datetime.strptime(
            session["finish_time"], "%Y-%m-%d %H:%M:%S.%f"
        )
        return int((finish_datetime - start_datetime).total_seconds() / 60)
    except ValueError as e:
        print(e, flush=True)
        print(f"{session['id']} has no finish_time. Skipping duration calculation.", flush=True)
        return 0

def generate_report(
    last_session,
    followers_now,
    following_now,
):
    return {
        "followers_now": followers_now,
        "followers_gained": (followers_now - last_session.get("profile", {}).get("followers", 0)) if followers_now else None,
        "following_now": following_now,
        "following_gained": (following_now - last_session.get("profile", {}).get("following", 0)) if followers_now else None,

        "duration": last_session["duration"],
        "total_likes": last_session["total_likes"],
        "total_followed": last_session["total_followed"],
        "total_unfollowed": last_session["total_unfollowed"],
        "total_watched": last_session["total_watched"],
        "total_comments": last_session["total_comments"],
        "total_pm": last_session["total_pm"],        
    }



class WebhookReports:
    """Generate reports at the end of the session and send them using webhook"""

    @staticmethod
    def run():
        print('WebhookReports running....', flush=True)
        username = AppState.configyml.get("username")
        session_state = AppState.session_state
        if not session_state:
            print("No session state found. Skipping report generation.", flush=True)
            return
        followers_now = session_state.my_followers_count
        following_now = session_state.my_following_count

        if username is None:
            print("You have to specify a username for getting reports!")
            return

        sessions = load_sessions(username)
        if not sessions:
            print(
                f"No session data found for {username}. Skipping report generation."
            )
            return

        last_session = sessions[-1]
        print('last_session', last_session, flush=True)
        last_session["duration"] = _calculate_session_duration(last_session)

        report = generate_report(
            last_session,
            followers_now,
            following_now,
        )

        response = send_webhook({
            "event": "report",
            "report": report
        })
        if response and response.status_code == 200:
            print(
                "Webhook message sent successfully.",
                flush=True,
            )
        else:
            print(f"Failed to send Webhook message", flush=True)
