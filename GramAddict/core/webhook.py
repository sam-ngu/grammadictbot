import requests
import os
from extra.utils.app_state import AppState

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
      with open(filepath, 'r') as f:
          lines = f.readlines()
          return lines[-n:]
    except FileNotFoundError:
      return []
    except Exception:
      return []

def send_webhook(payload: dict):
  try:
    logs = {
      'fisher_stdout': ''.join(_get_last_n_lines('/home/androidusr/logs/log_gramaddict.stdout.log')),
      'fisher_stderr': ''.join(_get_last_n_lines('/home/androidusr/logs/log_gramaddict.stderr.log')),
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