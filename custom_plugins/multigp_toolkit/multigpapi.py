"""
MultiGP RaceSync API Access
"""

import logging
from typing import TypeVar, Union

import requests

from .abstracts import _APIManager
from .enums import RequestAction

logger = logging.getLogger(__name__)
"""Module logger"""

T = TypeVar("T", bound=Union[bool, str, int])
"""Generic for typing"""
U = TypeVar("U", bound=Union[bool, str, int, dict])
"""Generic for typing"""

BASE_API_URL = "https://www.multigp.com/mgp/multigpwebservice"
"""MultiGP API base URL"""


class MultiGPAPI(_APIManager):
    """
    The primary class used to interact with the MultiGP RaceSync API

    .. seealso::

        https://www.multigp.com/apidocumentation/
    """

    _api_key: Union[str, None] = None
    """Chapter API key"""
    _chapter_id: Union[int, None] = None
    """MultiGP id for the chapter"""

    def __init__(self, rhapi):
        """
        Class initalization

        :param rhapi: An instance of RHAPI
        """
        headers = {"Content-type": "application/json"}
        super().__init__(rhapi, headers)

    def _request_and_parse(
        self, request_type: RequestAction, url: str, json_request: dict
    ) -> Union[dict[str, bool], dict[str, U]]:
        """
        Request data from the MultiGP API and parse it's output

        :param request_type: The request type
        :param url: The url to send the request
        :param json_request: The payload
        :return: The parsed data
        """

        if self._connected is False:
            return {"status": False}

        try:
            response = self._request(request_type, url, json_request)
        except requests.exceptions.ConnectionError:
            return {"status": False}

        try:
            return response.json()
        except (AttributeError, requests.JSONDecodeError):
            logger.error("Error parsing data from MultiGP")
            return {"status": False}

    def set_api_key(self, api_key: str) -> None:
        """
        Sets the MultiGP api key for

        :param apiKey: The MultiGP api key for the chapter
        """
        self._api_key = api_key

    def pull_chapter(self) -> Union[str, None]:
        """
        Find the chapter for the set RaceSync API key.

        :return: The name of the Chapter, returns None if chapter not found
        """
        url = f"{BASE_API_URL}/chapter/findChapterFromApiKey"
        payload = {"apiKey": self._api_key}

        returned_json = self._request_and_parse(RequestAction.POST, url, payload)

        if returned_json["status"]:
            self._chapter_id = returned_json["chapterId"]
            chapter_name = str(returned_json["chapterName"])
            return chapter_name

        return None

    def pull_races(self) -> Union[dict[int, str], None]:
        """
        Pull the avaliable races for the chapter.

        :return: Keypair of the race id and the race name. Returns
        None if race not found.
        """

        url = f"{BASE_API_URL}/race/listForChapter?chapterId={self._chapter_id}"
        payload = {"apiKey": self._api_key}

        returned_json = self._request_and_parse(RequestAction.POST, url, payload)

        if returned_json["status"]:
            races = {}

            for race in returned_json["data"]:
                races[race["id"]] = race["name"]

            return races

        return None

    def pull_race_data(self, race_id: str) -> Union[dict[str, U], None]:
        """
        retrieve the race data for a specific race.

        :param race_id: The MultiGP id for the race.
        :return: _description_
        """

        url = f"{BASE_API_URL}/race/view?id={race_id}"
        payload = {"apiKey": self._api_key}

        returned_json = self._request_and_parse(RequestAction.POST, url, payload)

        if returned_json["status"]:
            logger.info("Pulled data for %s", {returned_json["data"]["chapterName"]})
            return returned_json["data"]

        return None

    def pull_additional_rounds(
        self, race_id: str, round_num: int
    ) -> Union[dict[str, U], None]:
        """
        Downloads round informtions. Typcially used for ZippyQ.

        :param race_id: ID of the t
        :param round_num: Round number to pull
        :return: The race data for the round
        """
        url = f"{BASE_API_URL}/race/getAdditionalRounds?id={race_id}&startFromRound={round_num}"
        payload = {"apiKey": self._api_key}

        returned_json = self._request_and_parse(RequestAction.POST, url, payload)

        if returned_json["status"]:
            return returned_json["data"]

        return None

    def push_slot_and_score(self, captured_data: tuple[str, int, int, int, dict]):
        """
        Push individual results to the RaceSync API

        :param captured_data: Data to send to RaceSync. Elements of the tuple include
        (race_id, round_number, heat_number, slot_number, race_data).
        :return: The status of the results push
        """

        race_id, race_round, heat, slot, race_data = captured_data

        url = (
            f"{BASE_API_URL}/race/assignslot/id/"
            f"{race_id}/cycle/{race_round}/heat/{heat}/slot/{slot}"
        )
        payload = {"data": race_data, "apiKey": self._api_key}

        returned_json = self._request_and_parse(RequestAction.PUT, url, payload)

        return returned_json["status"]

    def push_overall_race_results(
        self, race_id: str, bracket_results: list[dict[str, int]]
    ):
        """
        Push the overall results to the RaceSync API

        :param race_id: The race id
        :param bracket_results: A list of pilot rankings
        :return: The status of the reuslts push
        """

        url = f"{BASE_API_URL}/race/captureOverallRaceResult?id={race_id}"
        payload = {
            "data": {"raceId": race_id, "bracketResults": bracket_results},
            "apiKey": self._api_key,
        }

        returned_json = self._request_and_parse(RequestAction.PUT, url, payload)

        return returned_json["status"]
