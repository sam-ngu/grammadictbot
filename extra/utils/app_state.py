from GramAddict.core.session_state import SessionState
class AppState:

  configyml = None
  session_state: SessionState = None

  def __init__(self):
    pass

  def __new__(cls, configyml: dict):
    cls.configyml = configyml
    pass

