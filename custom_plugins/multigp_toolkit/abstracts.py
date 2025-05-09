"""
Data manager abstraction
"""

import logging
import time
from typing import TypeVar, Union

import requests
from RHAPI import RHAPI

from .enums import RequestAction

logger = logging.getLogger(__name__)
"""Module logger"""

U = TypeVar("U", bound=Union[bool, str, int, dict])
"""Generic used for typing"""


class _APIManager:
    """
    Base manager for API access
    """

    # pylint: disable=R0903

    _connected: Union[bool, None] = None
    """Whether the system is able to connect to the API"""

    _session: requests.Session
    """Session for API requests"""

    def __init__(self, rhapi: RHAPI, headers: Union[dict[str, str], None] = None):
        """
        Class initalization

        :param headers: Header to use for API request
        """

        self._rhapi = rhapi
        """Instace of RHAPI"""

        self._session = requests.Session()
        """Session to use for API requests"""
        self._session.headers = headers

    def _request(
        self,
        request_type: RequestAction,
        url: str,
        json_request: Union[dict, None],
        headers: Union[dict, None] = None,
        timeout: int = 5,
    ) -> requests.Response:
        """
        Make a request to the class's API

        :param url: URL endpoint for the request
        :param json_request: JSON payload as a string
        :return: Data recieved from the request
        """

        try:
            req_send = time.time()
            response = self._session.request(
                request_type,
                url,
                headers=headers,
                json=json_request,
                timeout=timeout,
            )
            logger.debug(
                "%s response time: %s seconds",
                self.__class__.__name__,
                time.time() - req_send,
            )
        except requests.exceptions.ConnectionError:
            message = f"Connection with {type(self).__name__} failed"
            self._rhapi.ui.message_alert(message)
            logger.warning(message)
            self._connected = False
            raise

        self._connected = True

        return response
