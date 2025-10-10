import sys
import json
import os
import subprocess
import yaml
import requests
from pathlib import Path
from extra.igsession import session as igsession
import traceback
import GramAddict
from GramAddict.plugins.telegram import telegram_bot_send_file, telegram_bot_send_text 
from GramAddict.core.utils import shutdown
from GramAddict.core.webhook import send_webhook
from extra.utils.app_state import AppState
from extra.utils.webhook_report import WebhookReports, generate_report
import signal
import logging
from adbutils.errors import AdbError
from datetime import datetime
from dotenv import load_dotenv
import playground
load_dotenv(override=True)

import sentry_sdk
sentry_sdk.init(
  dsn=os.environ['SENTRY_DSN'],
  traces_sample_rate=1.0
)
sentry_sdk.integrations.logging.ignore_logger(__name__)

current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)
logger.info("----------- session " + current_time + " -----------")
logger.error("----------- session " + current_time + " -----------")


def setup_grammadict_config(social_username: str, config_files: dict):
   # config.yml
  # telegram.yml
  # filters.yml
  # whitelist.txt
  # blacklist.txt
  # comments_list.txt
  # pm_list.txt
  account_path = Path(__file__).parent.joinpath('accounts', social_username)
  default_config_path = Path(__file__).parent.joinpath('config-examples')
  os.makedirs(account_path, exist_ok=True)
  for file_name, content in config_files.items():
    with open(account_path.joinpath(file_name), 'w') as f:
      if(content is None or content == ''):
        content = default_config_path.joinpath(file_name).read_text()
      f.write(content)

def prepare_android_machine():
  pipelines = [
    # this will wait till emulator is ready
    "adb wait-for-device shell 'while [[ -z $(getprop sys.boot_completed) ]]; do sleep 1; done; input keyevent 82'", 
  ]
  # these 2 should already be included in Digital Ocean snapshot
  #  add these 2 to local only
  if os.environ.get('APP_ENV') is not None and os.environ['APP_ENV'] != 'production':
    pipelines.append('adb install /home/androidusr/instagram.apk')
    pipelines.append('python3 -m uiautomator2 init')

  for cmd in pipelines:
    print('running ', cmd, flush=True)
    # process = subprocess.run(cmd, capture_output=True, text=True, shell=True, encoding="utf8")
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
    process.wait()
    stdout, stderr = process.communicate()
    print(stdout, stderr, flush=True)



def send_logs(api_token, chat_id, err_message = None):
  logs_path = Path("/home/androidusr/logs")
  # use telegram to send log file
  log_files = (
    open(logs_path.joinpath('log_gramaddict.stderr.log').__str__(), 'rb'),
    open(logs_path.joinpath('log_gramaddict.stdout.log').__str__(), 'rb'),
  )

  for log_file in log_files:
    response = telegram_bot_send_file(api_token, chat_id, log_file)

  if err_message:
    response = telegram_bot_send_text(api_token, chat_id, err_message)

def graceful_shutdown(signum, frame):
  print('attempting to send analytics to webhook', flush=True)
  # send_webhook({
  #   "event": "testwebhook",
  # })
  
  WebhookReports().run()
  shutdown()

# TODO: remove the unneccessary apps
# com.google.android.calendar, 
# com.android.emulator.multidisplay, 
# com.android.se, 
# com.google.android.apps.wellbeing, 
# com.google.android.videos, 
# com.google.android.ext.services, 
# com.google.android.gms, 
# com.instagram.android, 
# com.android.dialer, 
# com.android.providers.calendar, 
# com.google.android.ims, 
# com.android.phone, 
# com.android.bluetooth, 
# com.android.systemui, 
# com.google.android.permissioncontroller, 
# com.google.android.youtube, 
# com.google.android.inputmethod.latin, 
# com.google.android.apps.nexuslauncher, 
# com.google.android.providers.media.module, 
# com.github.uiautomator, 
# com.google.android.apps.wallpaper, 
# com.google.android.apps.messaging,
def main():

  # send webhook on session analytics

  fisherman = os.environ['SCHED_FISHERMAN_PAYLOAD']

  if not fisherman:
    print('fisherman payload not found', flush=True)
    return

  fisherman_payload = json.loads(fisherman)

  configyml = yaml.safe_load(fisherman_payload['config.yml'])
  AppState(configyml)
  telegramyml = yaml.safe_load(fisherman_payload.get('telegram.yml') or '')
  ig_username = configyml['username']
  print('igusername', ig_username, flush=True)

  # payload is an object that contains the text content of the file eg:
  # {
  # s3Credentials: 'text', 
  # config.yml: 'text', telegram.yml: 'text', filters.yml: 'text', whitelist.txt: 'text', blacklist.txt: 'text', comments_list.txt: 'text', pm_list.txt: 'text' }
  # print(payload, flush=True)
  setup_grammadict_config(ig_username, {
    'config.yml': fisherman_payload['config.yml'],
    'telegram.yml': fisherman_payload.get('telegram.yml', ''),
    'filters.yml': fisherman_payload.get('filters.yml', ''),
    'whitelist.txt': fisherman_payload.get('whitelist.txt', ''),
    'blacklist.txt': fisherman_payload.get('blacklist.txt', ''),
    'comments_list.txt': fisherman_payload.get('comments_list.txt', ''),
    'pm_list.txt': fisherman_payload.get('pm_list.txt', ''),
  })

  prepare_android_machine()

  login_only = os.environ['GRAMADDICT_MODE'] == 'login'

  try:
    result = igsession.init_ig_session(ig_username)

    if login_only:
      res = send_webhook({
        'event': 'loggedin' if result == 'loggedin' else 'failed',
        'payload': {'message': result}
      })
      shutdown()
      return
  except Exception as e:
    # send crash event , should retry machine
    print('exception: ', e, flush=True)

    res = send_webhook({
      'event': 'crashed',
      'payload': e.__str__()
    })
    return

  # exec python run.py
  cwd = Path(__file__).parent
  print('running grammadict', flush=True)
  os.chdir(cwd.__str__())

  if not "--config" in sys.argv:
    sys.argv.append("--config")
    sys.argv.append(cwd.joinpath('accounts/' + ig_username + '/config.yml').__str__())

  try:
    # if telegramyml is not None or telegramyml != '':
    #   telegram_bot_send_text(telegramyml['telegram-api-token'], telegramyml['telegram-chat-id'], 'Running gramaddict for: ' + ig_username)
    GramAddict.run()
  except Exception as e:
    print('exception: ', e, flush=True)
    res = send_webhook({
      'event': 'failed',
      'payload': {
        'message': e.__str__()
      }
    })
    shutdown()
    return
  print('Sending done webhook...', flush=True)
  res = send_webhook({
    'event': 'done',
    'payload': {
      'message': 'Done',
      'report': generate_report()
    }
  })

  # save session before shutting down
  igsession.save_session_files(ig_username)
  print('session finished.', flush=True)
  # send logs to telegram or email
  # TODO: send finish event to webhook

  # if telegramyml is not None or telegramyml != '':
  #   send_logs(telegramyml['telegram-api-token'], telegramyml['telegram-chat-id'])

  # TODO: uncomment this
  shutdown()


def playground_dev():
  # To run dev mode, run this in terminal: DEV_MODE=True python3 main.py 

  # fisherman_payload = json.loads(os.environ['SCHED_FISHERMAN_PAYLOAD'])

  # configyml = yaml.safe_load(fisherman_payload['config.yml'])
  # ig_username = configyml['username']

  # # print(configyml, flush=True)
  # cwd = Path(__file__).parent

  if not "--config" in sys.argv:
    sys.argv.append("--config")
    cwd = Path(__file__).parent
    sys.argv.append(cwd.joinpath('accounts/' + 'kellysfishh' + '/config.yml').__str__())
  
  # start_bot()
  playground.main()

  pass

if __name__ == "__main__":
  signal.signal(signal.SIGTERM, graceful_shutdown)
  signal.signal(signal.SIGINT, graceful_shutdown)
  # signal cant handle SIGKILL, SIGKILL is not meant for gracefull shutdown
  # signal.signal(signal.SIGKILL, graceful_shutdown)

  if os.environ.get('DEV_MODE') == 'True':
    playground_dev()
    sys.exit(0)

  main()
