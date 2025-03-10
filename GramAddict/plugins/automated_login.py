from GramAddict.core.plugin_loader import Plugin


class AutomatedLogin(Plugin):
    """Short explanation that shows up on start"""

    def __init__(self):
        super().__init__()
        self.description = (
            "login"
        )
        self.arguments = [
            #
            # argparse arguments
            #
            # Example of operation (a plugin that does something - like interact with followers)
            {
                "arg": "--password",
                "nargs": None,  # see argparse docs for usage - if not needed use None
                "help": "instagram account password",
                "metavar": None,  # see argparse docs for usage - if not needed use None
                "default": None,  # see argparse docs for usage - if not needed use None
                "operation": False,  # If the argument is an operation, set to true. Otherwise do not include
            },
            # # Example of argparse "action" (something that requires no arguments)
            # {
            #     "arg": "--screen-sleep",
            #     "help": "save your screen by turning it off during the inactive time, disabled by default",
            #     "action": "store_true",  # see argparse docs for usage
            # },
        ]

    def run(self, device, configs, storage, sessions, profile_filter, plugin):
        # Your code here. All variables above must be in function definition, but
        # do not have to be used. If not needed, just ignore it. If you need anything
        # else from the main script - please include it in __init__.py and update
        # the run definition on all other plugins.
        pass
