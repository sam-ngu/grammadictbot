import sys
import json
import os
import subprocess
import yaml
from pathlib import Path
from extra.igsession import session as igsession
import GramAddict

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

def prepare_android_machine(profile_id: str, social_username: str):
  pipelines = (
    # 'adb start-server',
    # 'adb connect emulator-5554',
    # 'adb -s emulator-5554 wait-for-device',
    "adb wait-for-device shell 'while [[ -z $(getprop sys.boot_completed) ]]; do sleep 1; done; input keyevent 82'", # this will wait till emulator is ready
    # 'adb kill-server',
    # 'adb connect emulator-5554',
    # 'adb -s emulator-5554 wait-for-device',
    'adb install /home/androidusr/instagram.apk',
    '/home/androidusr/miniconda3/bin/python -m uiautomator2 init'
  )

  for cmd in pipelines:
    print('running ', cmd, flush=True)
    # process = subprocess.run(cmd, capture_output=True, text=True, shell=True, encoding="utf8")
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
    process.wait()
    stdout, stderr = process.communicate()
    print(stdout, stderr, flush=True)

  igsession.init_ig_session(profile_id, social_username)
  

def main():
  fisherman_payload = json.loads(os.environ['SCHED_FISHERMAN_PAYLOAD'])

  configyml = yaml.safe_load(fisherman_payload['config.yml'])
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

  prepare_android_machine(profile_id, ig_username)

  # exec python run.py
  cwd = Path(__file__).parent
  print('running grammadict', flush=True)
  # TODO: explore how to run gramaddict from the run function without starting a new process
  # GramAddict.run(config=cwd.joinpath('accounts/' + ig_username + '/config.yml'))
  cmd = "/home/androidusr/miniconda3/bin/python " + cwd.joinpath('run.py').__str__() + " --config " + cwd.joinpath('accounts/' + ig_username + '/config.yml').__str__()
  print('running ', cmd, flush=True)
  process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
  process.wait()
  stdout, stderr = process.communicate()
  print(stdout, stderr, flush=True)

if __name__ == "__main__":
  main()
