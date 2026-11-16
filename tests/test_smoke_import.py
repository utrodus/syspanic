import syspanic
from syspanic import constants


def test_version_is_0_1_0():
    assert syspanic.__version__ == "0.1.0"


def test_app_identity_constants():
    assert constants.APP_NAME == "SysPanic"
    assert constants.TAGLINE == "Don't panic. Diagnose."
