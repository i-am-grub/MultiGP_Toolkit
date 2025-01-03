"""
Data manager abstraction
"""

import logging
from typing import TypeVar

import requests

from RHAPI import RHAPI

from .enums import RequestAction

U = TypeVar("U", bound=bool | str | int | dict)

logger = logging.getLogger(__name__)


class _APIManager:
    """
    Base manager for API access
    """

    # pylint: disable=R0903

    _connected: bool | None = None
    """Whether the system is able to connect to the API"""

    _session: requests.Session
    """Session for API requests"""

    def __init__(self, headers: dict[str, str]):
        """
        Class initalization

        :param headers: Header to use for API request
        """
        self._session = requests.Session()
        self._session.headers = headers

    def _request(
        self, request_type: RequestAction, url: str, json_request: str | None
    ) -> requests.Response:
        """
        Make a request to the MultiGP API

        :param url: URL endpoint for the request
        :param json_request: JSON payload as a string
        :return: Data recieved from the request
        """
        try:
            response = self._session.request(
                request_type,
                url,
                data=json_request,
                timeout=10,
            )
        except requests.exceptions.ConnectionError:
            logger.warning("Unable to connect to MultiGP API")
            self._connected = False
            raise

        self._connected = True

        return response


class _RaceSyncDataManager:
    """
    Base class for race sync data managers
    """

    def __init__(
        self,
        rhapi: RHAPI,
    ):
        """
        Class initalization

        :param rhapi: An instance of RHAPI
        """
        self._rhapi = rhapi
        """A stored instace of the RHAPI module"""

    def get_mgp_pilot_id(self, pilot_id: int) -> None:
        """
        Gets the MultiGP id for a pilot

        :param pilot_id: The database id for the pilot
        :return: The
        """
        entry: str = self._rhapi.db.pilot_attribute_value(pilot_id, "mgp_pilot_id")
        if entry:
            return entry.strip()

        return None

    def clear_uuid(self, _args=None) -> None:
        """
        Clears the FPVScores uuid.

        :param _args: Args passed to the callback function, defaults to None
        """
        self._rhapi.db.option_set("event_uuid_toolkit", "")
