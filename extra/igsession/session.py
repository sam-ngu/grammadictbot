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

load_dotenv()

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
  zip_file_name = "sessionfiles_" + social_username + ".zip"
  zip_file_path = cwd.joinpath(zip_file_name)
  subprocess.run("zip -r " + zip_file_path.__str__() + " tmp/", cwd=cwd.__str__(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, encoding="utf8")

  # upload to storage
  client = storage_client()

  client.delete_object(Bucket="grammadict-ig-sessions", Key=zip_file_name)
  client.upload_file(zip_file_path, "grammadict-ig-sessions", zip_file_name)
  print("saved session to cloud storage", flush=True)

def file_exist_in_storage(bucket_name: str, file_key: str):
  client = storage_client()
  try:
    file_exist_in_storage = client.head_object(Bucket=bucket_name, Key=file_key)
    return True
  except ClientError as e:
     if e.response['Error']['Code'] == "404":
       return False
     else:
        # Something else went wrong
       raise e

def unpack_session_files_to_machine(social_username: str):
  cwd = Path("~/.gramaddict").expanduser()
  if not cwd.exists():
    cwd.mkdir()

  # download from storage 
  client = storage_client()
  filename = "sessionfiles_" + social_username + ".zip"
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

def login(ig_username: str):
  config_path = Path(__file__).parent.parent.parent.joinpath("accounts/" + ig_username + "/config.yml")
  configs = Config(first_run=True, config=config_path.__str__())
  configs.load_plugins()
  configs.parse_args()
  load_utils(configs)

  connected = check_adb_connection()

  print('app id is ', configs.config.get('app-id'))
  device = create_device(configs.device_id, configs.config.get('app-id'))

  open_instagram(device);

  # find login button, if does not exist then user has already logged in 
  login_button = device.find(className='android.view.View', text="Log in")

  if not login_button.exists(Timeout.SHORT):
    print('user has already logged in')
    return True
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
  save_profile_button = device.find(className='android.view.View', text="Save")
  if save_profile_button.exists(Timeout.MEDIUM):
    save_profile_button.click_retry(sleep=5, maxretry=3)

  return True

def init_ig_session(social_username: str):
  
  has_unpacked = unpack_session_files_to_machine(social_username)
  if not has_unpacked:
    # need to login an upload session file
    if login(social_username):
      save_session_files(social_username)


if __name__ == "__main__":
  # print(os.environ['AWS_ACCESS_KEY_ID'])
  # save_session_files("12345678")
  # unpack_session_files_to_machine("12345678")
  # init_ig_session("kellysfishh")
  pass