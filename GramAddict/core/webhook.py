import requests
import os


def send_webhook(payload):
  try:
    res = requests.post(os.environ['FG_WEBHOOK_URL'], 
                  headers={
                    'Content-Type': 'application/json',
                    'fg-signature': os.environ['FG_NONCE'],
                  }, 
                  json=payload)
  except Exception as e:
    print(e, flush=True)
    pass