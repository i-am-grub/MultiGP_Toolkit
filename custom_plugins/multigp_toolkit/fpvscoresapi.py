"""
FPVScores Connections
"""

import json
import logging
import sys
from collections.abc import Callable, Generator
from functools import wraps
from typing import TypeVar, Union

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

if sys.version_info >= (3, 10):
    from typing import Concatenate, ParamSpec
else:
    from typing_extensions import Concatenate, ParamSpec

import gevent
import requests
from data_export import DataExporter
from Database import (
    Heat,
    HeatNode,
    Pilot,
    Profiles,
    RaceClass,
    SavedRaceMeta,
)
from eventmanager import Evt
from gevent.lock import BoundedSemaphore
from RHAPI import RHAPI
from sqlalchemy import inspect
from sqlalchemy.ext.declarative import DeclarativeMeta
from typing_extensions import override

from .abstracts import _APIManager
from .enums import RequestAction

logger = logging.getLogger(__name__)
"""Module logger"""

BASE_API_URL = "https://api.fpvscores.com"
"""FPVScores API base URL"""
FPVS_API_VERSION = "0.1.0"
"""FPVScores Sync API version"""
LEGACY_HEADERS = {
    "Authorization": "rhconnect",
    "Accept": "application/json",
    "Content-Type": "application/json",
}
"""Headers for FPVScores MultiGP requests"""

P = ParamSpec("P")
"""Generic for typing"""
R = TypeVar("R")
"""Generic for typing"""


def standard_plugin_not_installed() -> bool:
    """
    Check if the full FPVScores plugin is not installed

    :return: status of the install
    """
    return "plugins.fpvscores" not in sys.modules


class FPVScoresAPI(_APIManager):
    """
    The primary class used to interact with the FPVScores API

    .. seealso::

        https://github.com/FPVScores/FPVScores-Sync/tree/main
    """

    _linked_org: Union[bool, None] = None
    """Whether the current MultiGP chapter is linked to FPVScores or not"""
    sync_ran: bool = False
    """Status if a full sync was ran or not"""

    def __init__(self, rhapi: RHAPI):
        """
        Class initalization

        :param rhapi: An instance of RHAPI
        """
        super().__init__(rhapi)

        self._rhapi = rhapi
        """A stored instance of RHAPI"""
        self.sync_guard = BoundedSemaphore()

        if standard_plugin_not_installed():
            self._register_listeners()

    def _register_listeners(self) -> None:
        """
        Registers the FPVScores event listeners
        """
        self._rhapi.events.on(
            Evt.CLASS_ADD,
            self.add_raceclass_listener,
            priority=20,
            name="class_listener",
        )
        self._rhapi.events.on(
            Evt.CLASS_ALTER,
            self.alter_raceclass_listener,
            priority=50,
            name="class_listener",
        )
        self._rhapi.events.on(
            Evt.CLASS_DELETE, self.class_delete, name="class_listener"
        )

        self._rhapi.events.on(
            Evt.HEAT_GENERATE, self.heat_listener, priority=99, name="heat_listener"
        )
        self._rhapi.events.on(Evt.HEAT_ALTER, self.heat_listener, name="heat_listener")
        self._rhapi.events.on(Evt.HEAT_DELETE, self.heat_delete, name="heat_listener")

        self._rhapi.events.on(
            Evt.PILOT_ADD, self.pilot_listener, priority=99, name="pilot_listener"
        )
        self._rhapi.events.on(
            Evt.PILOT_ALTER, self.pilot_listener, name="pilot_listener"
        )

        self._rhapi.events.on(
            Evt.LAPS_SAVE, self.results_listener, name="results_listener"
        )
        self._rhapi.events.on(
            Evt.LAPS_RESAVE, self.results_listener, name="results_listener"
        )

    def connection_check(self) -> bool:
        """
        Checks for a connection to FPVScores

        :return: The connection status
        """

        if self._connected is None:
            try:
                self._request(RequestAction.GET, BASE_API_URL, None)
            except requests.ConnectionError:
                self._connected = False
            else:
                self._connected = True

        if self._connected is False:
            self._rhapi.db.option_set("push_fpvs", "0")
            self._rhapi.db.option_set("fpvscores_autoupload_mgp", "0")

        return self._connected

    def generate_fpvsconditions(self) -> Generator[bool, None, None]:
        """
        Lazy loads and runs checks for fpvscores api actions

        :yield: Check statuses
        """
        self.sync_ran = False

        with self.sync_guard:
            yield self.connection_check()

            if self._rhapi.db.option("event_uuid_toolkit"):
                yield True
            elif self._linked_org is None:
                self._linked_org = self.check_linked_org()

                if self._linked_org:
                    self.run_full_sync()
                    self.sync_ran = True

                yield bool(self._rhapi.db.option("event_uuid_toolkit"))
            else:
                yield False

    def _generate_listener_conditions(self) -> Generator[bool, None, None]:
        """
        Lazy loads and runs checks for event listeners

        :yield: Check statuses
        """
        yield self._rhapi.db.option("fpvscores_autoupload_mgp") == "1"
        yield from self.generate_fpvsconditions()

    def _check_listener_conditions(  # type: ignore
        func: Callable[Concatenate[Self, P], R],
    ) -> Callable[Concatenate[Self, P], R]:
        """
        Decorator to run a series of checks before running event callback
        """
        # pylint: disable=E1102,E0213,W0212

        @wraps(func)
        def inner(self, *args: P.args, **kwargs: P.kwargs):
            if all(self._generate_listener_conditions()):
                func(self, *args, **kwargs)

        return inner

    def _parse_server_response(self, data: str) -> None:
        """
        Attempts to parse the incoming data from the FPVScores server.

        :param data: The returned FPVScores data
        """

        try:
            parsed_data = json.loads(data)
        except json.JSONDecodeError:
            message = "FPVScores: Failed to parse server response."
            logger.error("%s Response: %s", message, data)
            self._rhapi.ui.message_notify(message)
            return

        if isinstance(parsed_data, list):
            parsed_data = parsed_data[0]

        if "status" in parsed_data and "message" in parsed_data:
            message = f"FPVScores: {parsed_data['message']}"

            if parsed_data["status"] == "error":
                logger.error(message)
                self._rhapi.ui.message_notify(message)
            else:
                self._rhapi.ui.message_notify(message)

        else:
            message = "FPVScores: Unexpected response format."
            self._rhapi.ui.message_notify(message)

        if "event_uuid" in parsed_data:
            self._rhapi.db.option_set("event_uuid_toolkit", parsed_data["event_uuid"])

    def _process_response(self, greenlet: gevent.Greenlet) -> None:
        """
        Wait for the response greenlet to finish. Attempt to
        parse the incoming data when completed.

        :param greenlet: The greenlet to wait for
        """

        gevent.wait((greenlet,))
        response: requests.Response = greenlet.value
        self._parse_server_response(response.text)

    def _class_listener_request(self, payload: dict) -> None:
        """
        Submits a request to the class update enpoint asynchronously
        using gevent

        :param payload: The payload to send
        """

        url = f"{BASE_API_URL}/rh/{FPVS_API_VERSION}/?action=class_update"
        greenlet = gevent.spawn(self._request, RequestAction.POST, url, payload)
        self._process_response(greenlet)

    @_check_listener_conditions
    def add_raceclass_listener(self, args: Union[dict, None]) -> None:
        """
        Sync the individual race class creation data to FPVScores

        :param args: Default callback arguments
        """
        class_id = args["class_id"]

        payload = {
            "event_uuid": self._rhapi.db.option("event_uuid_toolkit"),
            "class_id": class_id,
            "class_name": f"Class {class_id}",
            "class_descr": "No description",
            "class_bracket_type": "none",
            "event_name": args["_eventName"],
        }
        self._class_listener_request(payload)

    @_check_listener_conditions
    def alter_raceclass_listener(self, args: Union[dict, None]) -> None:
        """
        Sync the individual race class modification data to FPVScores

        :param args: Default callback arguments
        """
        class_id = args["class_id"]
        raceclass: RaceClass = self._rhapi.db.raceclass_by_id(class_id)

        payload = {
            "event_uuid": self._rhapi.db.option("event_uuid_toolkit"),
            "class_id": class_id,
            "class_name": raceclass.display_name,
            "class_descr": raceclass.description,
            "class_bracket_type": "check",
            "event_name": args["_eventName"],
        }
        self._class_listener_request(payload)

    def get_race_channels(self) -> list[str]:
        """
        Gets the channel list in the FPVScores format

        :return: The list of channels
        """
        profile: Profiles = self._rhapi.race.frequencyset
        freq = json.loads(profile.frequencies)

        racechannels = []
        for band, channel in zip(freq["b"], freq["c"]):
            if str(band) == "None":
                racechannels.append("0")
            else:
                racechannels.append(f"{band}{channel}")

        return racechannels

    @_check_listener_conditions
    def class_delete(self, args: Union[dict, None]) -> None:
        """
        Deletes a single race class from FPVScores.

        :param args: Default callback arguments
        """

        payload = {
            "event_uuid": self._rhapi.db.option("event_uuid_toolkit"),
            "class_id": args["class_id"],
        }

        url = f"{BASE_API_URL}/rh/{FPVS_API_VERSION}/?action=class_delete"
        greenlet = gevent.spawn(self._request, RequestAction.POST, url, payload)
        self._process_response(greenlet)

    @_check_listener_conditions
    def heat_listener(self, args: Union[dict, None]) -> None:
        """
        Sync the individual heat data to FPVScores

        :param args: Default callback arguments
        """

        heat: Heat = self._rhapi.db.heat_by_id(args["heat_id"])
        heat_data: dict[str, Union[str, list]] = {
            "class_id": f"{heat.class_id}",
            "class_name": "unsupported",
            "class_descr": "unsupported",
            "class_bracket_type": "",
            "heat_name": heat.display_name,
            "heat_id": f"{heat.id}",
            "slots": [],
        }

        race_channels = self.get_race_channels()

        slots: list[HeatNode] = self._rhapi.db.slots_by_heat(heat.id)
        for slot in slots:
            if slot.node_index is None:
                continue

            pilotcallsign = "-"
            if slot.pilot_id != 0:
                pilot: Pilot = self._rhapi.db.pilot_by_id(slot.pilot_id)
                pilotcallsign = pilot.display_callsign

            slot_ = {
                "pilotid": slot.pilot_id,
                "nodeindex": slot.node_index,
                "channel": race_channels[slot.node_index],
                "callsign": pilotcallsign,
            }

            if slot_["channel"] != "0" and slot_["channel"] != "00":
                heat_data["slots"].append(slot_)

        payload = {
            "event_uuid": self._rhapi.db.option("event_uuid_toolkit"),
            "heats": [heat_data],
        }

        url = f"{BASE_API_URL}/rh/{FPVS_API_VERSION}/?action=heat_update"
        greenlet = gevent.spawn(self._request, RequestAction.POST, url, payload)
        self._process_response(greenlet)

    @_check_listener_conditions
    def heat_delete(self, args: Union[dict, None]):
        """
        Deletes a single heat from FPVScores.

        :param args: Default callback arguments
        """

        payload = {
            "event_uuid": self._rhapi.db.option("event_uuid_toolkit"),
            "heat_id": args["heat_id"],
        }

        url = f"{BASE_API_URL}/rh/{FPVS_API_VERSION}/?action=heat_delete"
        greenlet = gevent.spawn(self._request, RequestAction.POST, url, payload)
        self._process_response(greenlet)

    @_check_listener_conditions
    def pilot_listener(self, args: Union[dict, None]) -> None:
        """
        Sync the individual pilot data to FPVScores

        :param args: Default callback arguments
        """

        pilot: Pilot = self._rhapi.db.pilot_by_id(args["pilot_id"])
        payload = {
            "event_uuid": self._rhapi.db.option("event_uuid_toolkit"),
            "pilot_id": pilot.id,
            "callsign": pilot.display_callsign,
            "name": pilot.display_name,
            "team": pilot.team,
            "country": "",
            "fpvs_uuid": "",
            "phonetic": pilot.phonetic,
            "color": pilot.color,
            "event_name": args["_eventName"],
            "mgp_id": self._rhapi.db.pilot_attribute_value(
                pilot.id, "mgp_pilot_id", ""
            ),
        }

        url = f"{BASE_API_URL}/rh/{FPVS_API_VERSION}/?action=pilot_update"
        greenlet = gevent.spawn(self._request, RequestAction.POST, url, payload)
        self._process_response(greenlet)

    def generate_rank_payload(self, raceclass: RaceClass) -> list[dict]:
        """
        Generate the rankings payload for FPVScores

        :param raceclass: The raceclass to generate the payload from
        :return: A generated list of pilot data
        """

        payload = []

        if not (rankings := self._rhapi.db.raceclass_ranking(raceclass.id)):
            return payload

        meta = rankings["meta"]

        rank: dict
        for rank in rankings["ranking"]:
            rank_values = rank.copy()
            if "total_time_laps" in rank_values:
                del rank_values["total_time_laps"]

            pilot_data = {
                "classid": raceclass.id,
                "classname": raceclass.display_name,
                "pilot_id": rank_values.pop("pilot_id", None),
                "callsign": rank_values.pop("callsign", None),
                "position": rank_values.pop("position", None),
                "team_name": rank_values.pop("team_name", None),
                "node": rank_values.pop("node", None),
                "method_label": meta["method_label"],
                "rank_fields": meta["rank_fields"],
                "rank_values": rank_values,
            }
            payload.append(pilot_data)

        return payload

    def generate_results_payload(self, raceclass: RaceClass) -> list[dict]:
        """
        Generate the results payload for FPVScores

        :param raceclass: The raceclass to generate the payload from
        :return: A generated list of pilot data
        """

        payload = []

        if (fullresults := self._rhapi.db.raceclass_results(raceclass.id)) is None:
            return payload

        for leaderboard in ("by_consecutives", "by_race_time", "by_fastest_lap"):
            if leaderboard in fullresults:
                result: dict[str, Union[str, int, float, dict]]
                for result in fullresults[leaderboard]:
                    pilot_data = {
                        "classid": raceclass.id,
                        "classname": raceclass.display_name,
                        "pilot_id": result["pilot_id"],
                        "callsign": result["callsign"],
                        "team": result["team_name"],
                        "node": result["node"],
                        "points": "",
                        "position": result["position"],
                        "consecutives": result["consecutives"],
                        "consecutives_base": result["consecutives_base"],
                        "laps": result["laps"],
                        "starts": result["starts"],
                        "total_time": result["total_time"],
                        "total_time_laps": result["total_time_laps"],
                        "last_lap": result["last_lap"],
                        "last_lap_raw": result["last_lap_raw"],
                        "average_lap": result["average_lap"],
                        "fastest_lap": result["fastest_lap"],
                        "total_time_raw": result["total_time_raw"],
                        "total_time_laps_raw": result["total_time_laps_raw"],
                        "average_lap_raw": result["average_lap_raw"],
                        "consecutives_lap_start": result.get(
                            "consecutive_lap_start", ""
                        ),
                        "method_label": leaderboard,
                    }

                    if (
                        fast_source := result.get("fastest_lap_source", {})
                    ) is not None:
                        pilot_data["fastest_lap_source_round"] = fast_source.get(
                            "round", ""
                        )
                        pilot_data["fastest_lap_source_heat"] = fast_source.get(
                            "heat", ""
                        )
                        pilot_data["fastest_lap_source_displayname"] = fast_source.get(
                            "displayname", ""
                        )
                    else:
                        pilot_data["fastest_lap_source_round"] = ""
                        pilot_data["fastest_lap_source_heat"] = ""
                        pilot_data["fastest_lap_source_displayname"] = ""

                    if (
                        con_source := result.get("consecutives_source", {})
                    ) is not None:
                        pilot_data["consecutives_source_round"] = con_source.get(
                            "round", ""
                        )
                        pilot_data["consecutives_source_heat"] = con_source.get(
                            "heat", ""
                        )
                        pilot_data["consecutives_source_displayname"] = con_source.get(
                            "displayname", ""
                        )
                    else:
                        pilot_data["consecutives_source_round"] = ""
                        pilot_data["consecutives_source_heat"] = ""
                        pilot_data["consecutives_source_displayname"] = ""

                    payload.append(pilot_data)

        return payload

    @_check_listener_conditions
    def results_listener(self, args: Union[dict, None]) -> None:
        """
        Sync the individual class results to FPVScores

        :param args: Default callback arguments
        """

        race_meta: SavedRaceMeta = self._rhapi.db.race_by_id(args["race_id"])
        race_class: RaceClass = self._rhapi.db.raceclass_by_id(race_meta.class_id)

        payload = {
            "event_uuid": self._rhapi.db.option("event_uuid_toolkit"),
            "ranking": self.generate_rank_payload(race_class),
            "results": self.generate_results_payload(race_class),
            "classid": race_meta.class_id,
        }

        url = f"{BASE_API_URL}/rh/{FPVS_API_VERSION}/?action=leaderboard_update"
        greenlet = gevent.spawn(self._request, RequestAction.POST, url, payload)
        self._process_response(greenlet)

    def run_full_sync(self, _args: Union[dict, None] = None) -> None:
        """
        Syncs the FPVScores event to the current RotorHazard state

        :param _args: Default callback arguments
        """

        if not self.connection_check():
            message = "Unable to connect to FPVScores"
            self._rhapi.ui.message_notify(message)
            return

        message = "Running a full push to FPVScores. This may take a minute or two..."
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))

        export = self._rhapi.io.run_export("JSON_FPVScores_MGP_Upload")
        payload = json.loads(export["data"])
        url = f"{BASE_API_URL}/rh/{FPVS_API_VERSION}/?action=full_manual_import"

        greenlet = gevent.spawn(
            self._request, RequestAction.POST, url, payload, LEGACY_HEADERS, 600
        )
        self._process_response(greenlet)

    def get_event_url(self) -> Union[str, None]:
        """
        Get the FPVScores event url for the active race

        :return: The event url
        """

        if not self._connected or not (
            uuid := self._rhapi.db.option("event_uuid_toolkit")
        ):
            return None

        payload = {"event_uuid": uuid}
        url = f"{BASE_API_URL}/rh/{FPVS_API_VERSION}/?action=fpvs_get_event_url"

        greenlet = gevent.spawn(
            self._request, RequestAction.POST, url, payload, LEGACY_HEADERS
        )
        gevent.wait((greenlet,))

        response: requests.Response = greenlet.value

        if response.status_code == 200 and response.text != "no event found":
            logger.info("FPVScores event URL: %s", response.text)
            return response.text

        return None

    def check_linked_org(self) -> bool:
        """
        Checks if the MultiGP API timer key in the system is linked to
        an FPVScores organization

        :return: Whether the key is linked or not
        """

        if not self._connected:
            return False

        payload = {"mgp_api_key": self._rhapi.db.option("mgp_api_key")}
        url = f"{BASE_API_URL}/rh/{FPVS_API_VERSION}/?action=mgp_api_check"

        greenlet = gevent.spawn(
            self._request, RequestAction.POST, url, payload, LEGACY_HEADERS
        )
        gevent.wait((greenlet,))

        response: requests.Response = greenlet.value

        if response.status_code == 200:
            data = json.loads(response.text.split("\n")[-1])
            return data["exist"] == "true"

        return False


def _assemble_pilots_complete(rhapi: RHAPI) -> list[Pilot]:
    """
    Gets the database pilots and adds their MultiGP id
    to the upload data.

    :return: The list of pilots
    """
    payload = rhapi.db.pilots

    pilot: Pilot
    for pilot in payload:
        pilot.mgpid = rhapi.db.pilot_attribute_value(pilot.id, "mgp_pilot_id")

    return payload


def _assemble_heatnodes_complete(rhapi: RHAPI) -> dict:
    """
    Assembles heatnode data for FPVScores push

    :param rhapi: An instance of RHAPI
    :return: The formated payload
    """
    payload: list[HeatNode] = rhapi.db.slots
    profile: Profiles = rhapi.race.frequencyset
    freqs = json.loads(profile.frequencies)

    for slot in payload:
        if slot.node_index is not None and isinstance(slot.node_index, int):
            slot.node_frequency_band = (
                freqs["b"][slot.node_index]
                if len(freqs["b"]) > slot.node_index
                else " "
            )
            slot.node_frequency_c = (
                freqs["c"][slot.node_index]
                if len(freqs["c"]) > slot.node_index
                else " "
            )
            slot.node_frequency_f = (
                freqs["f"][slot.node_index]
                if len(freqs["f"]) > slot.node_index
                else " "
            )
        else:
            slot.node_frequency_band = " "
            slot.node_frequency_c = " "
            slot.node_frequency_f = " "

    return payload


def register_handlers(args: Union[dict, None]) -> None:
    """
    Register export handlers

    :param args: Default callback arguments
    """

    def write_to_json(data):
        payload = json.dumps(data, indent="\t", cls=AlchemyEncoder)
        return {"data": payload, "encoding": "application/json", "ext": "json"}

    def assemble_fpvscores_upload(rhapi: RHAPI):
        payload = {}
        payload["import_settings"] = "upload_FPVScores"
        payload["Pilot"] = _assemble_pilots_complete(rhapi)
        payload["Heat"] = rhapi.db.heats
        payload["HeatNode"] = _assemble_heatnodes_complete(rhapi)
        payload["RaceClass"] = rhapi.db.raceclasses
        payload["GlobalSettings"] = rhapi.db.options
        payload["FPVScores_results"] = rhapi.eventresults.results

        return payload

    if "register_fn" in args:
        args["register_fn"](
            DataExporter(
                "JSON FPVScores MGP Upload",
                write_to_json,
                assemble_fpvscores_upload,
            )
        )


class AlchemyEncoder(json.JSONEncoder):
    """
    JSON encoder for SQLAlchemy objects
    """

    @override
    def default(self, o: object):
        custom_vars = (
            "node_frequency_band",
            "node_frequency_c",
            "node_frequency_f",
            "mgpid",
            "display_name",
        )

        if isinstance(o.__class__, DeclarativeMeta):
            mapped_instance = inspect(o)
            fields = {}

            for field in dir(o):
                if field in [*mapped_instance.attrs.keys(), *custom_vars]:
                    data = o.__getattribute__(field)

                    if field != "query" and field != "query_class":
                        try:
                            json.dumps(data)
                            if field == "frequencies":
                                fields[field] = json.loads(data)
                            elif field == "enter_ats" or field == "exit_ats":
                                fields[field] = json.loads(data)
                            else:
                                fields[field] = data
                        except TypeError:
                            fields[field] = None

            return fields

        return super().default(o)
