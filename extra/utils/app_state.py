from GramAddict.core.session_state import SessionState
from GramAddict.core.device_facade import DeviceFacade
class AppState:

  configyml = None
  session_state: SessionState = None
  device: DeviceFacade = None

  def __init__(self):
    pass

  def __new__(cls, configyml: dict):
    cls.configyml = configyml
    pass

