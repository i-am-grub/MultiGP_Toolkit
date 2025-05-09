"""
Custom Enums
"""

from dataclasses import dataclass
from enum import Enum

from RHRace import StartBehavior, WinCondition


class RequestAction(str, Enum):
    """
    Common request methods
    """

    GET = "GET"
    """Represents a GET action"""
    POST = "POST"
    """Represents a POST action"""
    PUT = "PUT"
    """Represents a PUT action"""
    PATCH = "PATCH"
    """Represents a PATCH action"""
    DELETE = "DELETE"
    """Represents a DELETE action"""


class MGPMode(str, Enum):
    """
    MultiGP Schedule types
    """

    PREDEFINED_HEATS = "0"
    """Standard type. Formerly known as CONTROLLED mode"""
    ZIPPYQ = "1"
    """MultiGP's custom queueing mode"""
    BRACKET = "2"
    """Setting for custom bracket results. Expects 1 round per heat"""


@dataclass(frozen=True)
class MGPFormat:
    """
    Define the standard variables for an imported race format
    """

    format_name: str
    """Name of the format"""
    win_condition: WinCondition
    """Win condition of the format"""
    mgp_gq: bool = False
    """Flag marking the format to be used for Global Qualifiers"""
    race_time_sec: int = 120
    """The default time in seconds for the format"""
    unlimited_time: bool = False
    """Allow unlimited time for the format"""
    start_behavior: StartBehavior = StartBehavior.HOLESHOT
    """Start behavior for the format"""
    team_racing_mode: bool = False
    """Team racing enabled for the format"""


class DefaultMGPFormats(MGPFormat, Enum):
    """
    Default formats for MultiGP
    """

    AGGREGATE = "MultiGP: Aggregate Laps", WinCondition.MOST_PROGRESS
    """Most laps in race"""
    FASTEST = "MultiGP: Fastest Lap", WinCondition.FASTEST_LAP
    """Fastest lap in race"""
    CONSECUTIVE = "MultiGP: Fastest Consecutive Laps", WinCondition.FASTEST_CONSECUTIVE
    """Fastest Consecutive laps in race"""
    GLOBAL = "MultiGP: Global Qualifier", WinCondition.FASTEST_CONSECUTIVE, True
    """`CONSECUTIVE` with Global Qualifer features enabled.

    This format needs to be hardcoded until there is a way to lock format changes
    in the user interface.
    """
