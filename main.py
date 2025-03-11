import sys
import json
import os
import subprocess
import yaml
from pathlib import Path
from extra.igsession import session as igsession
import GramAddict
import traceback
from GramAddict.plugins.telegram import telegram_bot_send_file, telegram_bot_send_text 
from GramAddict.core.utils import shutdown

def setup_grammadict_config(social_username: str, config_files: dict):
   # create new folder with account name
  # with the following files in the accounts folder from the json payload:
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

def prepare_android_machine(social_username: str):
  pipelines = (
    # 'adb start-server',
    # 'adb connect emulator-5554',
    # 'adb -s emulator-5554 wait-for-device',
    "adb wait-for-device shell 'while [[ -z $(getprop sys.boot_completed) ]]; do sleep 1; done; input keyevent 82'", # this will wait till emulator is ready
    # 'adb kill-server',
    # 'adb connect emulator-5554',
    # 'adb -s emulator-5554 wait-for-device',
    'adb install /home/androidusr/instagram.apk',
    'python3 -m uiautomator2 init'
  )

  for cmd in pipelines:
    print('running ', cmd, flush=True)
    # process = subprocess.run(cmd, capture_output=True, text=True, shell=True, encoding="utf8")
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
    process.wait()
    stdout, stderr = process.communicate()
    print(stdout, stderr, flush=True)

  igsession.init_ig_session(social_username)


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


def main():
  fisherman_payload = json.loads(os.environ['SCHED_FISHERMAN_PAYLOAD'])

  configyml = yaml.safe_load(fisherman_payload['config.yml'])
  telegramyml = yaml.safe_load(fisherman_payload.get('telegram.yml') or '')
  ig_username = configyml['username']
  profile_id = fisherman_payload.get('profileId', '')
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

  prepare_android_machine(ig_username)

  # exec python run.py
  cwd = Path(__file__).parent
  print('running grammadict', flush=True)
  os.chdir(cwd.__str__())

  if not "--config" in sys.argv:
    sys.argv.append("--config")
    sys.argv.append(cwd.joinpath('accounts/' + ig_username + '/config.yml').__str__())

  try:
    if telegramyml is not None or telegramyml != '':
      telegram_bot_send_text(telegramyml['telegram-api-token'], telegramyml['telegram-chat-id'], 'Running gramaddict for: ' + ig_username)
    GramAddict.run()
  except Exception as e:
    print(e, flush=True)
    send_logs(telegramyml['telegram-api-token'], telegramyml['telegram-chat-id'], err_message=f"Exception: {traceback.format_exc()}")
    # TODO: uncomment this
    shutdown()
    return

  # save session before shutting down
  igsession.save_session_files(ig_username)
  print('session finished.', flush=True)
  # send logs to telegram or email
  if telegramyml is not None or telegramyml != '':
    send_logs(telegramyml['telegram-api-token'], telegramyml['telegram-chat-id'])

  # TODO: uncomment this
  shutdown()

  # cmd = "/home/androidusr/miniconda3/bin/python " + cwd.joinpath('run.py').__str__() + " --config " + cwd.joinpath('accounts/' + ig_username + '/config.yml').__str__()
  # print('running ', cmd, flush=True)
  # process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
  # process.wait()
  # stdout, stderr = process.communicate()
  # print(stdout, stderr, flush=True)


def playground():
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
  
  GramAddict.run()

  
  # import boto3
  # client = boto3.client(service_name='s3', 
  #                     aws_access_key_id='jxm3vkf2tr5dmya3r2473hhjbiyq', 
  #                     aws_secret_access_key='j2z6r5fvomfwrjs6ush6t6tsev6l5bjxcxefhl2hhafsv5je5axv6',
  #                     endpoint_url='https://gateway.storjshare.io')

  # bucket_name = "grammadict-ig-sessions"
  # file_key = "sessionfiles_sunnyrachel21.zip"
  # # file_key = "sessionfiles_kellysfishh.zip"

  # result = client.head_object(Bucket=bucket_name, Key=file_key)
  # print(result)
  pass

if __name__ == "__main__":
  
  # playground()

  main()
  pass
