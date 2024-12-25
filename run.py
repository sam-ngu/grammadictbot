import GramAddict
from GramAddict.core.device_facade import create_device, get_device_info, Mode, Timeout
from GramAddict.core.config import Config
from GramAddict.core.utils import (check_adb_connection, open_instagram)
from GramAddict.core.utils import load_config as load_utils

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
    return
  
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

if __name__ == "__main__":
  login();
  GramAddict.run()
