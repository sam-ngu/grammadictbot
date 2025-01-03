import subprocess
import os
import boto3
from dotenv import load_dotenv
from pathlib import Path
from GramAddict.core.device_facade import create_device, get_device_info, Mode, Timeout
from GramAddict.core.config import Config
from GramAddict.core.utils import (check_adb_connection, open_instagram)
from GramAddict.core.utils import load_config as load_utils

load_dotenv()

def storage_client():
    # TODO: pass aws keys
    return boto3.client(service_name='s3', 
                      aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'], 
                      aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
                      endpoint_url=os.environ['AWS_S3_ENDPOINT_URL'])


def save_session_files(profile_id: str):
  cwd = Path(__file__).parent
  
  # assume installed ig and logged in 
  if cwd.joinpath("tmp").exists():
    subprocess.run(["rm", "-rf", cwd.joinpath("tmp")])

  cwd.joinpath("tmp").mkdir()
  cwd.joinpath("tmp/keystore").mkdir()
  cwd.joinpath("tmp/com.instagram.android").mkdir()
  tmp_path = cwd.joinpath("tmp")
  pipelines = (
     "adb root",
     "adb pull /data/misc/keystore/user_0 " + tmp_path.__str__() + "/keystore",
     "adb pull /data/data/com.instagram.android/databases " + tmp_path.__str__() + "/com.instagram.android",
     "adb pull /data/data/com.instagram.android/shared_prefs " + tmp_path.__str__() + "/com.instagram.android",
     "adb pull /data/data/com.instagram.android/files " + tmp_path.__str__() + "/com.instagram.android",
  )
  for cmd in pipelines:
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, encoding="utf8")

  # zip tmp folder 
  zip_file_name = "sessionfiles_" + profile_id + ".zip"
  subprocess.run("zip -r " + cwd.joinpath(zip_file_name).__str__() + " tmp/", stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, encoding="utf8")

  # upload to storage
  client = storage_client()

  client.delete_object(Bucket="grammadict-ig-sessions", Key=zip_file_name)
  client.upload_file(zip_file_name, "grammadict-ig-sessions", zip_file_name)


def unpack_session_files_to_machine(profile_id: str):
  cwd = Path(__file__).parent

  # download from storage 
  client = storage_client()
  filename = "sessionfiles_" + profile_id + ".zip"
  tmp_path = cwd.joinpath("tmp")
  local_filepath = tmp_path.joinpath(filename)
  client.download_file("grammadict-ig-sessions", filename, local_filepath.__str__())

  # if not found then dont do anything
  if not local_filepath.exists():
    print('session zip does not exist')
    return False

  # unzip - this will create tmp folder in local
  if tmp_path.joinpath("com.instagram.android").exists():
    subprocess.run(["rm", "-rf", tmp_path.joinpath("com.instagram.android")])
  if tmp_path.joinpath("keystore").exists():
    subprocess.run(["rm", "-rf", tmp_path.joinpath("keystore")])
  subprocess.run("unzip " + local_filepath.__str__(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, encoding="utf8")

  # push all the files that starts with 10167 in user_0 folder 
  # we want only the 10167 prefix as they are the only ones related to instagram
  files = tmp_path.joinpath("keystore/user_0").glob("*10167*")
  adb_push_keystore = ["adb push " + file.__str__() + " /data/misc/keystore/user_0" for file in files] + ["adb shell chown -R keystore:keystore /data/misc/keystore"]

  # copy to machine
  pipelines = [
     "adb root",
     "adb push " + tmp_path.__str__() + "/com.instagram.android/databases /data/data/com.instagram.android/databases",
     "adb push " + tmp_path.__str__() + "/com.instagram.android/shared_prefs /data/data/com.instagram.android/shared_prefs",
     "adb push " + tmp_path.__str__() + "/com.instagram.android/files /data/data/com.instagram.android/files",
     "adb shell chown -R u0_a167:u0_a167 /data/data/com.instagram.android/databases",
     "adb shell chown -R u0_a167:u0_a167 /data/data/com.instagram.android/shared_prefs",
     "adb shell chown -R u0_a167:u0_a167 /data/data/com.instagram.android/files",
  ] + adb_push_keystore
  for cmd in pipelines:
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, encoding="utf8")

  return True

def login():
  configs = Config(first_run=True)
  configs.load_plugins()
  configs.parse_args()
  load_utils(configs)

  connected = check_adb_connection();

  device = create_device(configs.device_id, configs.app_id)

  open_instagram(device);

  # find login button, if does not exist then user has already logged in 
  login_button = device.find(className='android.view.View', text="Log in")

  if not login_button.exists(Timeout.SHORT):
    return True
  
  username_field = device.find(className='android.widget.EditText', enabled=True, instance=0)
  username_field.set_text(configs.username, mode=Mode.TYPE)

  password_field = device.find(className='android.widget.EditText', enabled=True, instance=1)
  password_field.set_text(configs.args.password, mode=Mode.TYPE)

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

def init_ig_session(profile_id: str):
  
  has_unpacked = unpack_session_files_to_machine(profile_id)
  if not has_unpacked:
    # need to login an upload session file
    if login():
      save_session_files(profile_id)


if __name__ == "__main__":
  # print(os.environ['AWS_ACCESS_KEY_ID'])
  # save_session_files("12345678")
  unpack_session_files_to_machine("12345678")