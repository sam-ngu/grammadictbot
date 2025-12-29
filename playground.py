import sys
from pathlib import Path
import GramAddict
from GramAddict.core.device_facade import create_device, Mode, Timeout
from GramAddict.core.utils import load_config
from GramAddict.core.resources import ResourceID as resources
# from GramAddict.core.resources import ClassName
from GramAddict.core.config import Config
import subprocess
from extra.igsession.session import storage_client
import os

def run_command(cmd: str):
  print('running ', cmd, flush=True)
  process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
  process.wait()

  stdout, stderr = process.communicate()

  if(stderr):
    raise Exception(stderr)
  return stdout

def remove_input_method():
  output = run_command('adb shell ime list -s')
  input_methods = output.split('\n')

  run_command('adb shell ime disable com.github.uiautomator/.FastInputIME')

  for input_method in input_methods:
    if not input_method:
      continue
    run_command(f'adb shell ime disable {input_method}')

def main():

  # "sessionfiles_" + social_username + "_" + os.environ['FG_SOCIAL_ACCOUNT_ID'] + ".zip"
  # if not "--config" in sys.argv:
  #   sys.argv.append("--config")
  #   cwd = Path(__file__).parent
  #   sys.argv.append(cwd.joinpath('accounts/' + 'kellysfishh' + '/config.yml').__str__())
  
  # configs = Config(first_run=True)
  # configs.parse_args()
  # print(configs.app_id, flush=True)

  # load_config(configs)

  # remove_input_method()
  app_id = "com.instagram.android"
  device = create_device(None, app_id)
  ResourceID = resources(app_id)

  resend_code = device.find(text="Wait a moment")

  print('resend_code', resend_code.exists(Timeout.SHORT), flush=True)

  # check_email = device.find(className='android.view.View', text="Check your email")
  # try_another_way = device.find(className='android.view.View', text="Try another way")
  # is_in_wrong_password_screen = check_email.exists(Timeout.SHORT) or try_another_way.exists(Timeout.SHORT)
  # print('checking if user entered wrong password', is_in_wrong_password_screen, flush=True)
  


  # def scrolled_to_top():
  #   row_search = device.find(
  #       resourceId=ResourceID.ROW_SEARCH_EDIT_TEXT,
  #       className=ClassName.EDIT_TEXT,
  #   )
  #   return row_search.exists()

  # top = scrolled_to_top()
  # print('top is',  top)

  # # if top
  # # then scroll to the bottom 
  # list_view = device.find(
  #     resourceId=ResourceID.LIST, className=ClassName.LIST_VIEW
  # )

  # print('dir', Direction.DOWN)
  
  # # scroll up offset to fully reveal the search bar if exist
  # device.swipe(direction=Direction.DOWN, scale=0.5)
  # # check if at top, if yes scroll all the way to bottom, else continue
  # if scrolled_to_top():
  #   list_view.viewV2.fling.toEnd()
  # else:
  #   # resume offset
  #   device.swipe(direction=Direction.UP, scale=0.5)

  # # device.
  # list_view.viewV2.fling.toEnd()
  # # list_view.scroll(direction=Direction.DOWN)
  # # device.View.scroll(direction=Direction.DOWN)
  pass


if __name__ == "__main__":
  # remove_input_method()
  main()