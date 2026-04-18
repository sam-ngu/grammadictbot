"""Human-like Instagram bot powered by UIAutomator2"""

__version__ = "3.2.12"
__tested_ig_version__ = "300.0.0.29.110"


def run(**kwargs):
    from GramAddict.core.bot_flow import start_bot

    start_bot(**kwargs)
