"""
Data manager abstraction
"""

import sys
from enum import IntEnum

from RHAPI import RHAPI

from .multigpapi import MultiGPAPI

try:
    if sys.version_info.minor == 13:
        from .verification import SystemVerification
    elif sys.version_info.minor == 12:
        from .verification import SystemVerification
    elif sys.version_info.minor == 11:
        from .verification import SystemVerification
    elif sys.version_info.minor == 10:
        from .verification import SystemVerification
    elif sys.version_info.minor == 9:
        from .verification import SystemVerification
    else:
        raise ImportError("Unsupported Python version")
except ImportError as exc:
    raise ImportError(
        (
            "System Verification module not found. "
            "Follow the installation instructions here: "
            "https://multigp-toolkit.readthedocs.io"
            "/stable/usage/install/index.html"
        )
    ) from exc


class MultiGPMode(IntEnum):
    """
    MultiGP Schedule types
    """

    PREDEFINED_HEATS = 0
    """Standard type. Formerly known as CONTROLLED mode"""
    ZIPPYQ = 1
    """MultiGP's customing queuing mode"""


class _RaceSyncDataManager:
    """
    Base class for race sync data managers
    """

    def __init__(
        self,
        rhapi: RHAPI,
        multigp: MultiGPAPI,
        verification: SystemVerification,
        pilot_urls: bool = False,
    ):
        self._rhapi = rhapi
        self._multigp = multigp
        self._verification = verification
        self._pilot_urls = pilot_urls

    def get_mgp_pilot_id(self, pilot_id: int):
        """
        Gets the MultiGP id for a pilot

        :param pilot_id: The database id for the pilot
        :return: The
        """
        entry: str = self._rhapi.db.pilot_attribute_value(pilot_id, "mgp_pilot_id")
        if entry:
            return entry.strip()

        return None

    def clear_uuid(self, _args=None):
        """
        Clears the FPVScores uuid.

        :param _args: Args passed to the callback function, defaults to None
        """
        self._rhapi.db.option_set("event_uuid_toolkit", "")
