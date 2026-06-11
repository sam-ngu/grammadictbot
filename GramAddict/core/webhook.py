import requests
import os
from extra.utils.app_state import AppState


WEBHOOK_BATCH_SIZE = 20  # flush after this many payloads


class ProfileVisitBatch:
    """Accumulates profile_visit payloads and flushes them as a batch webhook."""
    _queue: list = []

    @classmethod
    def enqueue(cls, payload: dict):
        """Add a profile_visit payload to the batch. Auto-flushes when batch is full."""
        cls._queue.append(payload)
        if len(cls._queue) >= WEBHOOK_BATCH_SIZE:
            cls.flush()

    @classmethod
    def flush(cls):
        """Send all queued profile_visit payloads as a single batch webhook."""
        if not cls._queue:
            return
        batch = cls._queue[:]
        cls._queue = []
        send_webhook({
            "event": "profile_visit_batch",
            "count": len(batch),
            "payloads": batch,
        })

def _get_last_n_lines(filepath, n=20):
    """
    Retrieves the last n lines of a file.

    Args:
        filepath (str): The path to the file.
        n (int): The number of last lines to retrieve.

    Returns:
        list: A list containing the last n lines of the file.
              Returns an empty list if the file is not found or empty.
    """
    try:
      with open(filepath, 'rb') as f:
        f.seek(0)
        content_bype = f.read()
        lines = content_bype.decode('utf-8').splitlines()
        return lines[-n:]
    except FileNotFoundError:
      return ['LOG FILE NOT FOUND ERROR']
    except Exception as e:
      return ['Unable to get logs: ' + str(e)]

def send_webhook(payload: dict):
  try:
    logs = {
      'fisher_stdout': ''.join(_get_last_n_lines('/home/androidusr/logs/log_gramaddict.stdout.log')),
      'fisher_stderr': ''.join(_get_last_n_lines('/home/androidusr/logs/log_gramaddict.stderr.log', 100)),
    }
    ig_username = AppState.configyml['username']
    payload.update({
      'logs': logs,
      'social_platform': 'instagram',
      'social_username': ig_username,
      'social_account_id': os.environ['FG_SOCIAL_ACCOUNT_ID'],
    })

    return requests.post(os.environ['FG_WEBHOOK_URL'], 
                  headers={
                    'Content-Type': 'application/json',
                    'fg-signature': os.environ['FG_NONCE'],
                  }, 
                  json=payload)
  except Exception as e:
    print(e, flush=True)
    pass


def queue_profile_visit_webhook(username, context, profile_data=None, is_private=None, posts_count=None):
    """
    Queue a profile visit webhook for batch sending.

    Args:
        username: The visited account's username
        context: "source" (from navigation) or "target" (from filter)
        profile_data: Profile object (for target visits with full data)
        is_private: bool (for source visits with minimal data)
        posts_count: int (for source visits with minimal data)
    """
    payload = {
        "event": "profile_visit",
        "context": context,
    }

    if profile_data is not None:
        payload["payload"] = {
            "username": username,
            "full_name": profile_data.fullname,
            "biography": profile_data.biography,
            "is_private": profile_data.is_private,
            "is_verified": profile_data.is_verified,
            "has_business_category": profile_data.has_business_category,
            "follower_count": profile_data.followers,
            "following_count": profile_data.followings,
            "post_count": profile_data.posts_count,
            "link_in_bio": profile_data.link_in_bio,
        }
    else:
        # Minimal data for skipped source accounts
        payload["payload"] = {
            "username": username,
            "full_name": None,
            "biography": None,
            "is_private": is_private,
            "is_verified": None,
            "has_business_category": None,
            "follower_count": None,
            "following_count": None,
            "post_count": posts_count,
            "link_in_bio": None,
        }

    ProfileVisitBatch.enqueue(payload)