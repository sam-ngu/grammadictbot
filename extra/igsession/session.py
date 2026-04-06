import subprocess
import os
import sys
import boto3
from dotenv import load_dotenv
from pathlib import Path
from GramAddict.core.device_facade import create_device, get_device_info, Mode, Timeout
from GramAddict.core.config import Config
from GramAddict.core.utils import (check_adb_connection, open_instagram)
from GramAddict.core.utils import load_config as load_utils
from botocore.exceptions import ClientError
import shutil
import yaml
from GramAddict.plugins.telegram import telegram_bot_send_text, load_telegram_config
from GramAddict.core.webhook import send_webhook
import uiautomator2 as u2
import time

load_dotenv(override=True)

# Import challenge handler from challenge.py
from extra.igsession.challenge import handle_challenge, detect_selfie_challenge

def run_command(cmd: str):
  print('running ', cmd, flush=True)
  process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
  process.wait()

  stdout, stderr = process.communicate()

  if(stderr):
    raise Exception(stderr)
  return stdout

def list_input_methods():
  output = run_command('adb shell ime list -s')
  return output.split('\n')

def remove_input_methods():
  # reverse to disable fastinputime first
  input_methods = list_input_methods()

  for input_method in input_methods:
    if not input_method:
      continue
    stdout = run_command(f'adb shell ime disable {input_method}')
    print(stdout, flush=True)

def storage_client():
    return boto3.client(service_name='s3', 
                      aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'], 
                      aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
                      endpoint_url=os.environ['AWS_S3_ENDPOINT_URL'])


def save_session_files(social_username: str):
  cwd = Path("~/.gramaddict").expanduser()
  if not cwd.exists():
    cwd.mkdir()
  
  # assume installed ig and logged in 
  if cwd.joinpath("tmp").exists():
    # shutil.rmtree(cwd.joinpath("tmp").__str__())
    subprocess.run("rm -rf " + cwd.joinpath("tmp").__str__(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, encoding="utf8")

  cwd.joinpath("tmp").mkdir()
  cwd.joinpath("tmp/keystore").mkdir()
  cwd.joinpath("tmp/com.instagram.android").mkdir()
  cwd.joinpath("tmp/gramaddict_data").mkdir()
  tmp_path = cwd.joinpath("tmp")

  gramaddict_user_path = Path("/home/androidusr/gramaddict/accounts/" + social_username)
  gramaddict_data_exist = gramaddict_user_path.joinpath("sessions.json").exists()

  pipelines = [
     "adb root",
     "adb pull /data/misc/keystore/user_0 " + tmp_path.__str__() + "/keystore",
     "adb pull /data/data/com.instagram.android/databases " + tmp_path.__str__() + "/com.instagram.android",
     "adb pull /data/data/com.instagram.android/shared_prefs " + tmp_path.__str__() + "/com.instagram.android",
     "adb pull /data/data/com.instagram.android/files " + tmp_path.__str__() + "/com.instagram.android",
  ]
  
  if gramaddict_data_exist:
    print('found gramaddict session, packaging...', flush=True)
    #  get user sessions.json, history_filters_users.json, interacted_users.json from gramaddict user folder 
    pipelines = pipelines + [
      "cp " + gramaddict_user_path.joinpath("sessions.json").__str__() + " " + tmp_path.__str__() + "/gramaddict_data",
      "cp " + gramaddict_user_path.joinpath("history_filters_users.json").__str__() + " " + tmp_path.__str__() + "/gramaddict_data",
      "cp " + gramaddict_user_path.joinpath("interacted_users.json").__str__() + " " + tmp_path.__str__() + "/gramaddict_data"
    ]

  for cmd in pipelines:
    print('running ', cmd, flush=True)
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, encoding="utf8")

  # zip tmp folder 
  zip_file_name = _zip_file_name(social_username)
  zip_file_path = cwd.joinpath(zip_file_name)
  subprocess.run("zip -r " + zip_file_path.__str__() + " tmp/", cwd=cwd.__str__(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, encoding="utf8")

  # check zip file size, if too small dont save eg less than 1 MB
  zip_file_size = os.path.getsize(zip_file_path.__str__())
  if zip_file_size < (1024 * 1024):
    print("session zip file size too small, not saving", flush=True)
    raise Exception("session zip file size too small, not saving, only " + str(zip_file_size / (1024 * 1024)) + " MB")

  # upload to storage
  client = storage_client()

  client.delete_object(Bucket="grammadict-ig-sessions", Key=zip_file_name)
  client.upload_file(zip_file_path, "grammadict-ig-sessions", zip_file_name)
  print("saved session to cloud storage", flush=True)

def file_exist_in_storage(bucket_name: str, file_key: str):
  client = storage_client()
  print("checking file exist in cloud, bucket: " + bucket_name + ' file_key: ' + file_key, flush=True)
  try:
    file_exist_in_storage = client.head_object(Bucket=bucket_name, Key=file_key)
    return True
  except ClientError as e:
     if e.response['Error']['Code'] == "404":
       return False
     else:
        # Something else went wrong
       raise e

def _zip_file_name(social_username: str):
  return "sessionfiles_" + social_username + "_" + os.environ['FG_SOCIAL_ACCOUNT_ID'] + ".zip"

def unpack_session_files_to_machine(social_username: str):
  cwd = Path("~/.gramaddict").expanduser()
  if not cwd.exists():
    cwd.mkdir()

  # download from storage 
  client = storage_client()
  filename = _zip_file_name(social_username)
  tmp_path = cwd.joinpath("tmp")
  if not tmp_path.exists():
    tmp_path.mkdir()

  local_filepath = tmp_path.joinpath(filename)

  bucket_name = "grammadict-ig-sessions"

  # if not found then dont do anything
  if not file_exist_in_storage(bucket_name, filename):
    print('session zip does not exist', flush=True)
    return False

  print('Found existing session in cloud. Downloading session', flush=True)
  client.download_file(bucket_name, filename, local_filepath.__str__())

  # unzip - this will create tmp folder in local
  if tmp_path.joinpath("com.instagram.android").exists():
    # shutil.rmtree(tmp_path.joinpath("com.instagram.android").__str__())
    subprocess.run("rm -rf " + tmp_path.joinpath("com.instagram.android").__str__())
  if tmp_path.joinpath("keystore").exists():
    # shutil.rmtree(tmp_path.joinpath("keystore").__str__())
    subprocess.run("rm -rf " + tmp_path.joinpath("keystore").__str__())
  subprocess.run("unzip " + local_filepath.__str__(), cwd=cwd.__str__(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, encoding="utf8")

  # push all the files that starts with 10167 in user_0 folder 
  # we want only the 10167 prefix as they are the only ones related to instagram
  files = tmp_path.joinpath("keystore/user_0").glob("*10167*")
  adb_push_keystore = ["adb push " + file.__str__() + " /data/misc/keystore/user_0" for file in files] + ["adb shell chown -R keystore:keystore /data/misc/keystore"]

  # push gramadict data file to gramaddict user folder
  if tmp_path.joinpath("gramaddict_data").exists():
    gramaddict_user_path = Path("~/gramaddict/accounts/" + social_username).expanduser()
    gramaddict_data = ("sessions.json", "history_filters_users.json", "interacted_users.json")
    gramaddict_copy_data = [
      "cp " + tmp_path.joinpath("gramaddict_data").joinpath(file).__str__() + " " + gramaddict_user_path.joinpath(file).__str__() for file in gramaddict_data
    ]
  else:
    gramaddict_copy_data = []
  
  # copy to machine
  pipelines = [
     "adb root",
     "adb push " + tmp_path.__str__() + "/com.instagram.android/databases /data/data/com.instagram.android/databases",
     "adb push " + tmp_path.__str__() + "/com.instagram.android/shared_prefs /data/data/com.instagram.android/shared_prefs",
     "adb push " + tmp_path.__str__() + "/com.instagram.android/files /data/data/com.instagram.android/files",
     "adb shell chown -R u0_a167:u0_a167 /data/data/com.instagram.android/databases",
     "adb shell chown -R u0_a167:u0_a167 /data/data/com.instagram.android/shared_prefs",
     "adb shell chown -R u0_a167:u0_a167 /data/data/com.instagram.android/files",
  ] + adb_push_keystore + gramaddict_copy_data
  for cmd in pipelines:
    print('running ', cmd, flush=True)
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, encoding="utf8")

  return True

def load_config(ig_username: str, yaml_name: str = "config.yml"):
  config_path = get_config_path(ig_username, yaml_name)
  with open(config_path, "r", encoding="utf-8") as stream:
    return yaml.safe_load(stream)

def get_config_path(ig_username: str, yaml_name: str = "config.yml"):
  return Path(__file__).parent.parent.parent.joinpath("accounts/" + ig_username + "/" + yaml_name)

def login(ig_username: str):
  login_only = os.environ['GRAMADDICT_MODE'] == 'login'

  # config_path = Path(__file__).parent.parent.parent.joinpath("accounts/" + ig_username + "/config.yml")
  config_path = get_config_path(ig_username, 'config.yml')
  configs = Config(first_run=True, config=config_path.__str__())
  configs.load_plugins()
  configs.parse_args()
  load_utils(configs)

  connected = check_adb_connection()

  print('app id is ', configs.config.get('app-id'))
  app_id = configs.config.get('app-id') if configs.config.get('app-id') else 'com.instagram.android'
  device = create_device(configs.device_id, app_id)

  open_instagram(device)

  device.deviceV2.sleep(3)

  current_app_info = device.deviceV2.app_current()
  print('current app info is ', current_app_info, flush=True)
  print('package is ', current_app_info['package'], flush=True)
  if current_app_info['package'] != app_id:
    print('instagram is not opened', flush=True)
    # usually because corrupted session in the cloud
    return 'ig_launch_error'

  # cancel button will show when ig is still in loading state
  cancel_button = device.find(className='android.view.View', text="Cancel")

  # if cancel button exist, then it means ig is still loading
  while cancel_button.exists(Timeout.SHORT):
    print('cancel button exists before homescreen check means it is loading... sleeping 1s', flush=True)
    device.deviceV2.sleep(1)

  # Page is not available
  page_not_available = device.find(className='android.view.View', text="technical error")
  if page_not_available.exists(Timeout.SHORT):
    print('page not available, clicking refresh', flush=True)
    refresh_button = device.find(className='android.view.View', text="Refresh")
    refresh_button.click()

  homescreen_checks = ["I already have an account", "I already have a profile", "Join Instagram", "Get started"]
  proceed_home_screen_buttons = [
    device.find(className='android.view.View', text="I already have an account"),
    device.find(className='android.view.View', text="I already have a profile"),
  ]

  for homescreen_check in homescreen_checks:
    check_element = device.find(className='android.view.View', text=homescreen_check)
    if check_element.exists(Timeout.SHORT):
      print('sees homescreen check', flush=True)
      if not login_only:
        return 'sees_home_screen'

      for btn in proceed_home_screen_buttons:
        if btn.exists(Timeout.ZERO):
          btn.click()
          if login_only:
            send_webhook({
              'event': 'login_ig_has_home_screen',
            })
            
          break
      
  while cancel_button.exists(Timeout.TINY):
    print('cancel button exists before login means it is loading... sleeping 1s', flush=True)
    device.deviceV2.sleep(1)

  if page_not_available.exists(Timeout.SHORT):
    print('page not available, clicking refresh', flush=True)
    refresh_button = device.find(className='android.view.View', text="Refresh")
    refresh_button.click()

  # find login button, if does not exist then user has already logged in 
  login_button = device.find(className='android.view.View', text="Log in")

  if not login_button.exists(Timeout.SHORT):
    print('user has already logged in', flush=True)
    return 'already_logged_in'

  # here login button exist
  # if this is not supposed to be a login machine, need to stop and send webhook outside to inform user
  if not login_only:
    return 'invalid_machine_mode'

  editable_text_field = device.find(className='android.widget.EditText', enabled=True)
  username_field = device.find(className='android.widget.EditText', enabled=True, instance=0)
  username_field.set_text(ig_username, mode=Mode.TYPE)

  # focusing on password field
  password_field = device.find(className='android.widget.EditText', enabled=True, instance=1)
  password_field.set_text('', mode=Mode.TYPE)

  # hide keyboard so we know exactly what px to hide in IG UI
  device.deviceV2.sleep(1)
  remove_input_methods()
  device.deviceV2.sleep(1)

  res = send_webhook({
    'event': 'login_ready',
  })

  if os.environ.get('DEV_MODE') == "True":
    import playground
    time.sleep(60*60* 5)
    # playground.main()
    # sys.exit(0)
    return

  # should wait for 10 min for user to login. Timeout and shutdown if fail to login
  timeout = 60 * 10  # 10 min
  print('checking if login button exists', flush=True)
  interval = 1
  wrong_password_modal = device.find(text="Incorrect password")
  unable_to_login_modal = device.find(text="Unable to log in")
  wrong_password_notice = device.find(text="The password you entered is incorrect")
  while login_button.exists(Timeout.TINY) or wrong_password_modal.exists(Timeout.ZERO) or wrong_password_notice.exists(Timeout.ZERO):
    device.deviceV2.sleep(interval)
    timeout -= interval
    if timeout <= 0:
      print('timed out waiting for user to login', flush=True)
      return 'timeout'
    # force user to not modify username
    try:
      if username_field.exists(Timeout.TINY) and editable_text_field.count_items() == 2:
        entered_username = username_field.get_text()
        remove_input_methods()
        if entered_username != ig_username:
          print('user entered wrong username', flush=True)
          username_field.set_text(ig_username, mode=Mode.TYPE)
          remove_input_methods()
          send_webhook({
            'event': 'login_username_modified',
          })
    except Exception as e:
      # this may happen once moved passed login screen, ignore
      print('except in login block: ',e, flush=True)
      pass
  
  if unable_to_login_modal.exists(Timeout.SHORT):
    print('unable to login', flush=True)
    # when this happens, its most likely ig has blocked the login attempt, due to suspicious location. Australian ip tends to do this
    return 'unable_to_login_due_to_unknown_error'

  send_webhook({
    'event': 'login_entered_password',
  })
  print('user entered password', flush=True)
  device.deviceV2.sleep(1)

  # ====================================================================
  # CHALLENGE HANDLING
  # All challenge detection and handling logic moved to challenge.py
  # ====================================================================

  # Use legacy detector by default (proven, tested implementation)
  # Set use_legacy=False to use new challenge loop architecture
  challenge_result = handle_challenge(device, ig_username, interval=0.5, use_legacy=False)

  # If challenge handler returned an error status, return it
  if challenge_result != 'loggedin':
    return challenge_result

  # ====================================================================
  # POST-CHALLENGE SUCCESS
  # ====================================================================

  return 'loggedin'

  username = configs.config.get('username')
  password = configs.config.get('password')
  if not username or not password:
    raise Exception("Username or password not found in config file")
  
  username_field = device.find(className='android.widget.EditText', enabled=True, instance=0)
  username_field.set_text(username, mode=Mode.TYPE)

  password_field = device.find(className='android.widget.EditText', enabled=True, instance=1)
  password_field.set_text(password, mode=Mode.TYPE)

  # click on log in button 
  login_button.click()

  # save your login info screen
  # find the save button
  device.deviceV2.sleep(5)
  print('woke up continue')

  return True

def init_ig_session(social_username: str):
  
  # if session file is already corrupted and currently in login mode, user will never get to see the login screen
  is_login_mode = os.environ['GRAMADDICT_MODE'] == 'login'
  if not is_login_mode:
    has_unpacked = unpack_session_files_to_machine(social_username)
    # standard mode but no session files in cloud
    if not has_unpacked:
      print('no session files found in cloud storage', flush=True)
      return 'no_session_files'

  # standard mode and has session file [handled in login()] 
  # login mode and no session file - handled in login() - initiate login 
  # login mode and has session file - handled in login() - return already logged in 

  # need to login an upload session file
  result = login(social_username)
  if result == 'already_logged_in' or result == 'loggedin':
    print('Saving session files after logged in', flush=True)
    if is_login_mode:
      save_session_files(social_username)
  return result  

  # if not has_unpacked:
  # else:
  #   print('unpacked session files to machine', flush=True)

if __name__ == "__main__":
  # print(os.environ['AWS_ACCESS_KEY_ID'])
  # save_session_files("12345678")
  # unpack_session_files_to_machine("12345678")
  # init_ig_session("kellysfishh")
  pass