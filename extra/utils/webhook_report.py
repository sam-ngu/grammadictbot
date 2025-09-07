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
from GramAddict.core.session_state import SessionState

logger = logging.getLogger(__name__)

# TODO: use sqlite instead of json to handle session
def load_sessions(username) -> Optional[dict]:
    try:
        with open(f"accounts/{username}/sessions.json") as json_data:
            return json.load(json_data)
    except FileNotFoundError:
        print("No session data found. Skipping report generation.", flush=True)
        return None


def _calculate_session_duration(session: SessionState):
    try:
        start_datetime = session.startTime if isinstance(session.startTime, datetime) else datetime.strptime(
            session.startTime, "%Y-%m-%d %H:%M:%S.%f"
        )
        finish_datetime = session.finishTime if isinstance(session.finishTime, datetime) else datetime.strptime(
            session.finishTime, "%Y-%m-%d %H:%M:%S.%f"
        )
        return int((finish_datetime - start_datetime).total_seconds() / 60)
    except ValueError as e:
        print(e, flush=True)
        print(f"{session['id']} has no finish_time. Skipping duration calculation.", flush=True)
        return 0

def generate_report():
    session = AppState.session_state
    duration = _calculate_session_duration(session)

    return {
        "followers_now": session.my_followers_count,
        # "followers_gained": (followers_now - session.get("profile", {}).get("followers", 0)) if followers_now else None,
        "following_now": session.my_following_count,
        # "following_gained": (following_now - session.get("profile", {}).get("following", 0)) if followers_now else None,

        "duration": duration,
        "total_likes": session.totalLikes,
        "total_followed": session.totalFollowed,
        "total_unfollowed": session.totalUnfollowed,
        "total_watched": session.totalWatched,
        "total_comments": session.totalComments,
        "total_pm": session.totalPm,        
    }



class WebhookReports:
    """Generate reports at the end of the session and send them using webhook"""

    @staticmethod
    def run():
        print('WebhookReports running....', flush=True)
        username = AppState.configyml.get("username")
        if not AppState.session_state:
            print("No session state found. Skipping report generation.", flush=True)
            return

        if username is None:
            print("You have to specify a username for getting reports!")
            return

        # last_session = None
        # with load_sessions(username) as sessions:
        #     if not sessions:
        #         print(
        #             f"No session data found for {username}. Skipping report generation."
        #         )
        #         return
        #     last_session = sessions[-1]
        #     print('last_session', last_session, flush=True)
        

        report = generate_report()

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
