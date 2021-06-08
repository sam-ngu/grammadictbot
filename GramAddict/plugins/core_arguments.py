from GramAddict.core.plugin_loader import Plugin

# Note: this is mainly here to house old arguments until we figure out args better


class CoreArguments(Plugin):
    """Simply adds core arguments"""

    def __init__(self):
        super().__init__()
        self.description = "Simply adds core arguments"
        self.arguments = [
            {
                "arg": "--device",
                "nargs": None,
                "help": "device identifier. Should be used only when multiple devices are connected at once",
                "metavar": "2443de990e017ece",
                "default": None,
            },
            {
                "arg": "--username",
                "nargs": None,
                "help": "username of the instagram account being used",
                "metavar": "justinbieber",
                "default": None,
            },
            {
                "arg": "--likes-count",
                "nargs": None,
                "help": "number of likes for each interacted user, 1-2 by default. It can be a number (e.g. 2) or a range (e.g. 2-4)",
                "metavar": "2-4",
                "default": "1-2",
            },
            {
                "arg": "--total-likes-limit",
                "nargs": None,
                "help": "limit on total amount of likes per session, 300 by default",
                "metavar": "300",
                "default": "300",
            },
            {
                "arg": "--total-follows-limit",
                "nargs": None,
                "help": "limit on total follows per session, 50 by default",
                "metavar": "50",
                "default": "50",
            },
            {
                "arg": "--total-unfollows-limit",
                "nargs": None,
                "help": "limit on total unfollows per session, 50 by default",
                "metavar": "50",
                "default": "50",
            },
            {
                "arg": "--total-watches-limit",
                "nargs": None,
                "help": "limit on total watched stories per session, 50 by default",
                "metavar": "50",
                "default": "50",
            },
            {
                "arg": "--total-successful-interactions-limit",
                "nargs": None,
                "help": "limit on total successful interactions per session, 100 by default",
                "metavar": "100",
                "default": "100",
            },
            {
                "arg": "--total-interactions-limit",
                "nargs": None,
                "help": "limit on total interactions per session, 1000 by default",
                "metavar": "1000",
                "default": "1000",
            },
            {
                "arg": "--stories-count",
                "nargs": None,
                "help": "number of stories to watch for each user, 0 by default. It can be a number (e.g. 2) or a range (e.g. 2-4)",
                "metavar": "2-4",
                "default": "0",
            },
            {
                "arg": "--stories-percentage",
                "nargs": None,
                "help": "chance of watching stories on a particular profile, 30-40 by default. It can be a number (e.g. 20) or a range (e.g. 20-40)",
                "metavar": "50-70",
                "default": "30-40",
            },
            {
                "arg": "--carousel-count",
                "nargs": None,
                "help": "number of photos in carousel to watch, 1 by default. It can be a number (e.g. 2) or a range (e.g. 2-4)",
                "metavar": "2-4",
                "default": "1",
            },
            {
                "arg": "--carousel-percentage",
                "nargs": None,
                "help": "chance of watching photos in carousel, 60-70 by default. It can be a number (e.g. 75) or a range (e.g. 60-70)",
                "metavar": "10-90",
                "default": "60-70",
            },
            {
                "arg": "--watch-video-time",
                "nargs": None,
                "help": "amount of time (seconds) you want to watch a video before interact with it, set to 0 to disable this feature. It can be a number (e.g. 20) or a range (e.g. 20-40)",
                "metavar": "15-55",
                "default": "20-40",
            },
            {
                "arg": "--interactions-count",
                "nargs": None,
                "help": "number of interactions per each blogger, 30-50 by default. It can be a number (e.g. 70) or a range (e.g. 60-80). Only successful interactions count",
                "metavar": "60-80",
                "default": "30-50",
            },
            {
                "arg": "--interact-percentage",
                "nargs": None,
                "help": "chance to interact with user/hashtag or place when applicable (currently in hashtag or place-posts-recent/top)",
                "metavar": "50",
                "default": "50",
            },
            {
                "arg": "--repeat",
                "nargs": None,
                "help": "repeat the same session again after N minutes after completion, disabled by default. It can be a number of minutes (e.g. 180) or a range (e.g. 120-180)",
                "metavar": "220-300",
                "default": None,
            },
            {
                "arg": "--follow-percentage",
                "nargs": None,
                "help": "follow given percentage of interacted users, 0 by default",
                "metavar": "50",
                "default": "0",
            },
            {
                "arg": "--follow-limit",
                "nargs": None,
                "help": "limit on amount of follows per source in each action, disabled by default",
                "metavar": "0",
                "default": None,
            },
            {
                "arg": "--skipped-list-limit",
                "nargs": None,
                "help": "limit how many scrolls tried, with already interacted users, until we move to next source. Does not apply for unfollows",
                "metavar": "10-15",
                "default": "10-15",
            },
            {
                "arg": "--fling-when-skipped",
                "nargs": None,
                "help": 'fling after "X" many scrolls tried, with already interacted users. (not recommended - disabled by default)',
                "metavar": "10-12",
                "default": "0",
            },
            {
                "arg": "--speed-multiplier",
                "nargs": None,
                "help": "modifier for random sleep values - slows down (<1) or speeds up (>1) depending on multiplier passed",
                "metavar": 1,
                "default": 1,
            },
            {
                "arg": "--screen-sleep",
                "help": "save your screen by turning it off during the inactive time, disabled by default",
                "action": "store_true",
            },
            {
                "arg": "--debug",
                "help": "enable debug logging",
                "action": "store_true",
            },
            {
                "arg": "--screen-record",
                "help": "enable screen recording: it will be saved as debug.mp4",
                "action": "store_true",
            },
            {
                "arg": "--close-apps",
                "help": "close all apps except IG, for avoid interference",
                "action": "store_true",
            },
            {
                "arg": "--interact",
                "nargs": "+",
                "help": "list of @usernames or #hashtags with whose followers you want to interact",
                "metavar": ("@username1", "@username2"),
                "default": None,
            },
            {
                "arg": "--hashtag-likers",
                "nargs": "+",
                "help": "list of hashtags with whose likers you want to interact",
                "metavar": ("hashtag1", "hashtag2"),
                "default": None,
            },
            {
                "arg": "--delete-interacted-users",
                "help": "delete the user from the file after processing it",
                "action": "store_true",
            },
            {
                "arg": "--scrape-to-file",
                "nargs": None,
                "help": "generate a file in main directory with given name with target users",
                "metavar": ("filename"),
                "default": None,
            },
            {
                "arg": "--total-scraped-limit",
                "nargs": None,
                "help": "limit on total scrape per session, 50 by default",
                "metavar": "5-10",
                "default": "50",
            },
            {
                "arg": "--comment-percentage",
                "nargs": None,
                "help": "comment given percentage of interacted users, 0 by default",
                "metavar": "40-60",
                "default": "0",
            },
            {
                "arg": "--total-comments-limit",
                "nargs": None,
                "help": "limit on total comments per session, disabled by default",
                "metavar": "5-10",
                "default": "0",
            },
            {
                "arg": "--pm-percentage",
                "nargs": None,
                "help": "private message given percentage of interacted users, 0 by default",
                "metavar": "40-60",
                "default": "0",
            },
            {
                "arg": "--total-pm-limit",
                "nargs": None,
                "help": "limit on total private message per session, disabled by default",
                "metavar": "5-10",
                "default": "0",
            },
            {
                "arg": "--max-comments-pro-user",
                "nargs": None,
                "help": "limit on max possibile comments for each interacted user",
                "metavar": "1-2",
                "default": "1",
            },
            {
                "arg": "--truncate-sources",
                "nargs": None,
                "help": "truncate the source list to a finite number of items",
                "metavar": "2-4",
                "default": "0",
            },
            {
                "arg": "--shuffle-jobs",
                "help": "shuffle jobs order",
                "action": "store_true",
            },
            {
                "arg": "--working-hours",
                "nargs": "+",
                "help": "specify working hours",
                "metavar": "10-22",
                "default": ["00.00-23.59"],
            },
            {
                "arg": "--time-delta",
                "nargs": None,
                "help": "delta time to add or subtract from working hours",
                "metavar": "10-15",
                "default": "0",
            },
            {
                "arg": "--disable-filters",
                "help": "disable the using of filters without have to remove/rename the json file",
                "action": "store_true",
            },
            {
                "arg": "--total-crashes-limit",
                "nargs": None,
                "help": "limit on total allowed crashes for session, 5 by default",
                "metavar": "5-10",
                "default": "5",
            },
            {
                "arg": "--uia-version",
                "nargs": None,
                "help": "uiautomator version, deprecated.",
                "metavar": 2,
                "default": 2,
            },
        ]