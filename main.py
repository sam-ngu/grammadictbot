import sys
import json
import os
import subprocess
import yaml
from pathlib import Path
from extra.igsession import session as igsession

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

def prepare_android_machine(profile_id: str):
  pipelines = (
    'adb start-server',
    'adb connect 127.0.0.1:5555',
    'adb -s 127.0.0.1:5555 wait-for-device',
    'adb -s 127.0.0.1:5555 install /home/androidusr/instagram.apk',
    '/home/androidusr/miniconda3/bin/python -m uiautomator2 init'
  )

  for cmd in pipelines:
    # process = subprocess.run(cmd, capture_output=True, text=True, shell=True, encoding="utf8")
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
    process.wait()
    stdout, stderr = process.communicate()
    print(stdout, stderr)

  igsession.init_ig_session(profile_id)
  

def main():
  fisherman_payload = json.loads(os.environ['SCHED_FISHERMAN_PAYLOAD'])

  configyml = yaml.safe_load(fisherman_payload['config.yml'])
  ig_username = configyml['username']
  print('igusername', ig_username)

  # payload is an object that contains the text content of the file eg:
  # {
  # s3Credentials: 'text', 
  # config.yml: 'text', telegram.yml: 'text', filters.yml: 'text', whitelist.txt: 'text', blacklist.txt: 'text', comments_list.txt: 'text', pm_list.txt: 'text' }
  # print(payload)
  setup_grammadict_config(ig_username, {
    'config.yml': fisherman_payload['config.yml'],
    'telegram.yml': fisherman_payload.get('telegram.yml', ''),
    'filters.yml': fisherman_payload.get('filters.yml', ''),
    'whitelist.txt': fisherman_payload.get('whitelist.txt', ''),
    'blacklist.txt': fisherman_payload.get('blacklist.txt', ''),
    'comments_list.txt': fisherman_payload.get('comments_list.txt', ''),
    'pm_list.txt': fisherman_payload.get('pm_list.txt', ''),
  })

  prepare_android_machine(fisherman_payload.get('profileId', ''))

  # exec python run.py
  cwd = Path(__file__).parent
  process = subprocess.Popen("/home/androidusr/miniconda3/bin/python " + cwd.joinpath('run.py').__str__() + " --config " + cwd.joinpath('accounts', ig_username, 'config.yml').__str__(), 
                             cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
  process.wait()
  stdout, stderr = process.communicate()
  print(stdout, stderr)

if __name__ == "__main__":
  main()
