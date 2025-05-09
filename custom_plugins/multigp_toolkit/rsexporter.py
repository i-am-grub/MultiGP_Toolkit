"""
Import Data from RaceSync
"""

import json
import logging
import sys
from collections.abc import Generator, Iterable
from typing import Any, TypeVar, Union

import gevent
import gevent.lock
import gevent.pool
from Database import Heat, Pilot, RaceClass, SavedRaceMeta
from RHAPI import RHAPI

from .enums import MGPMode
from .fpvscoresapi import FPVScoresAPI
from .multigpapi import MultiGPAPI

try:
    if sys.version_info.minor == 13:
        from .verification.py313 import SystemVerification
    elif sys.version_info.minor == 12:
        from .verification.py312 import SystemVerification
    elif sys.version_info.minor == 11:
        from .verification.py311 import SystemVerification
    elif sys.version_info.minor == 10:
        from .verification.py310 import SystemVerification
    elif sys.version_info.minor == 9:
        from .verification.py39 import SystemVerification
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

T = TypeVar("T")

logger = logging.getLogger(__name__)


class RaceSyncExporter:
    """Actions for exporting data to RaceSync"""

    def __init__(
        self,
        rhapi: RHAPI,
        multigp: MultiGPAPI,
        verification: SystemVerification,
    ):
        """
        Class initalization

        :param rhapi: An instance of RHAPI
        :param multigp: An instance of the MultiGPAPI
        :param verification: An instace of the SystemVerification module
        """
        self._rhapi = rhapi
        """A stored instace of the RHAPI module"""
        self._multigp = multigp
        """A stored instace of the MultiGPAPI module"""
        self._verification = verification
        """A stored instace of the SystemVerification module"""
        self._fpvscores = FPVScoresAPI(rhapi)
        """An instance of FPVScoresAPI"""
        self.active_sync = gevent.lock.BoundedSemaphore()
        """Variable for checking if a results sync is active"""

    def get_mgp_pilot_id(self, pilot_id: int) -> Union[str, None]:
        """
        Gets the MultiGP id for a pilot

        :param pilot_id: The database id for the pilot
        :return: The
        """
        entry: str = self._rhapi.db.pilot_attribute_value(pilot_id, "mgp_pilot_id")
        if entry:
            return entry.strip()

        return None

    def generate_formated_race_data(
        self,
        race_info: SavedRaceMeta,
        selected_race: int,
        round_num: int,
        heat_num: int,
        event_url: Union[str, None],
    ):
        """
        Generates a slot and score package for each pilot for the provided race

        :param race_info: Data for the completed race
        :param event_url: The FPVScores event url
        :yield: Formated race data
        """
        # pylint: disable=R0913

        race_pilots = json.loads(
            self._rhapi.db.race_attribute_value(race_info.id, "race_pilots")
        )
        results = self._rhapi.db.race_results(race_info.id)["by_race_time"]

        for pilot_id in race_pilots:

            for result in results:
                if result["pilot_id"] == int(pilot_id):
                    break
            else:
                result = None

            slot_num = race_pilots[pilot_id] + 1

            race_data: dict[str, Any] = {}

            mgp_pilot_id = self.get_mgp_pilot_id(pilot_id)
            if mgp_pilot_id:
                race_data["pilotId"] = mgp_pilot_id
            else:
                pilot_info: Pilot = self._rhapi.db.pilot_by_id(pilot_id)
                message = (
                    f"{pilot_info.callsign} does not have a "
                    "MultiGP Pilot ID. Pilot's results will not be pushed..."
                )
                logger.warning(message)
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                continue

            if result is not None:

                if "points" in result:
                    race_data["score"] = result["points"]

                race_data["totalLaps"] = result["laps"]
                race_data["totalTime"] = round(result["total_time_raw"] * 0.001, 3)
                race_data["fastestLapTime"] = round(
                    result["fastest_lap_raw"] * 0.001, 3
                )

                if result["consecutives_base"] == 3:
                    race_data["fastest3ConsecutiveLapsTime"] = round(
                        result["consecutives_raw"] * 0.001, 3
                    )
                elif result["consecutives_base"] == 2:
                    race_data["fastest2ConsecutiveLapsTime"] = round(
                        result["consecutives_raw"] * 0.001, 3
                    )
            else:
                race_data["totalLaps"] = 0

            if event_url is not None:
                race_data["liveTimeEventUrl"] = event_url

            yield (selected_race, round_num, heat_num, slot_num, race_data)

    def slot_score(self, collection: Iterable[Generator]) -> bool:
        """
        Push generated data to MultiGP. Uses a gevent connection pool for parallel
        connections.

        :param data_generators: Generators for formating data.
        :return: Status of the push
        """

        def combined_generators(iterable):
            for generator in iterable:
                yield from generator

        statuses = gevent.pool.Pool(10).map(
            self._multigp.push_slot_and_score, combined_generators(collection)
        )

        if not all(statuses):
            message = "Results push to MultiGP FAILED."
            self._rhapi.ui.message_alert(self._rhapi.language.__(message))
            return False

        return True

    def _generate_fpvscores_conditions(self) -> Generator[bool, None, None]:
        """
        Lazily generate the conditions for pushing to FPVScores

        :yield: Check statuses
        """
        yield self._rhapi.db.option("push_fpvs") == "1"
        yield from self._fpvscores.generate_fpvsconditions()

    def _bundle_by_group(
        self, races: list[SavedRaceMeta]
    ) -> dict[int, list[SavedRaceMeta]]:
        """
        Group saved race meta by heat groups and then sorts
        each heat groups based on heat id.

        :param races: The saved race meta to organize
        :return: The sorted heat groups
        """

        def heat_id_from_race(race_info: SavedRaceMeta):
            return race_info.heat_id

        heat_groups: dict[int, list] = {}
        for race in races:
            heat: Heat = self._rhapi.db.heat_by_id(race.heat_id)
            if heat.group_id not in heat_groups:
                heat_groups[heat.group_id] = [race]
            else:
                heat_groups[heat.group_id].append(race)

        for group in heat_groups.values():
            group.sort(key=heat_id_from_race)

        return heat_groups

    def _bundle_by_heat(
        self, races: list[SavedRaceMeta]
    ) -> dict[int, list[SavedRaceMeta]]:
        """
        Group saved race meta by heat id.

        :param races: A list of the saved race data
        :return: An organized group of race data
        """
        groups: dict[int, list] = {}
        for race in races:
            heat: Heat = self._rhapi.db.heat_by_id(race.heat_id)
            if heat.id not in groups:
                groups[heat.id] = [race]
            else:
                groups[heat.id].append(race)

        return groups

    def _parse_heat_group_data(
        self,
        selected_mgp_race: int,
        event_url: Union[str, None],
        races: list[SavedRaceMeta],
    ) -> Generator[Generator[tuple, None, None], None, None]:
        """
        Parses class data in the `Generate Heat Groups` format
        to be compatible with MultiGP predefined heats.

        Round number is set to the internal group id + 1 and the heat number
        is set set to the index of the heat within the heat group

        **Race data may be lost if a pilot participates in more than one heat per round.
        This is due to a limitation with MultiGP limiting pilots to one heat per round.**

        :param selected_mgp_race: The selected MultiGP race
        :param event_url: The FPVScores event url
        :param races: The race data
        :yield: The formated data
        """

        data = self._bundle_by_group(races)
        for group_id, races_ in data.items():
            heat_index = 1
            for race_info in races_:
                yield self.generate_formated_race_data(
                    race_info,
                    selected_mgp_race,
                    group_id + 1,
                    heat_index,
                    event_url,
                )
                heat_index += 1

    def _parse_heat_data(
        self,
        selected_mgp_race: int,
        event_url: Union[str, None],
        races: list[SavedRaceMeta],
    ) -> Generator[Generator[tuple, None, None], None, None]:
        """
        Parses class data in the `Count Races per Heat` format
        to be compatible with MultiGP predefined heats.

        Uses the internal round number and the index of the heat
        within the raceclass.

        **Race data may be lost if a pilot participates in more than one heat per round.
        This is due to a limitation with MultiGP limiting pilots to one heat per round.**

        :param selected_mgp_race: The selected MultiGP race
        :param event_url: The FPVScores event url
        :param races: The race data
        :yield: The formated data
        """

        data = self._bundle_by_heat(races)
        heat_index = 1
        for heat in data.values():
            for race_info in heat:
                yield self.generate_formated_race_data(
                    race_info,
                    selected_mgp_race,
                    race_info.round_id,
                    heat_index,
                    event_url,
                )

            heat_index += 1

    def _parse_zippyq_data(
        self,
        selected_mgp_race: int,
        event_url: Union[str, None],
        races: list[SavedRaceMeta],
    ) -> Generator[Generator[tuple, None, None], None, None]:
        """
        Parses class data to be compatible with ZippyQ.

        The zippyq round number is read from the heat metadata

        :param selected_mgp_race: The selected MultiGP race
        :param event_url: The FPVScores event url
        :param races: The race data
        :yield: The formated data
        """

        for race_info in races:
            round_num = int(
                self._rhapi.db.heat_attribute_value(
                    race_info.heat_id, "zippyq_round_num"
                )
            )

            if round_num:
                yield self.generate_formated_race_data(
                    race_info,
                    selected_mgp_race,
                    round_num,
                    1,
                    event_url,
                )

    def _parse_incremental_round_data(
        self,
        selected_mgp_race: int,
        event_url: Union[str, None],
        races: list[SavedRaceMeta],
    ) -> Generator[Generator[tuple, None, None], None, None]:
        """
        Parses class data to be compatible with brackets or ladders.

        Each race increments the round number and
        the heat number is always set to 1.

        :param selected_mgp_race: The selected MultiGP race
        :param event_url: The FPVScores event url
        :param races: The race data
        :yield: The formated data
        """

        def id_from_race(race_info: SavedRaceMeta):
            return race_info.id

        races.sort(key=id_from_race)
        for index, race_info in enumerate(races, start=1):
            yield self.generate_formated_race_data(
                race_info,
                selected_mgp_race,
                index,
                1,
                event_url,
            )

    def raceclass_slot_score(
        self,
        selected_mgp_race: int,
        selected_rh_class: int,
        event_url: Union[str, None],
    ):
        """
        Pushes race results for a selected RotorHazard class to a specific
        MultiGP race. Typically trigger by a manual button press in the
        user interface.

        :param selected_mgp_race: The MultiGP race to push to.
        :param selected_rh_class: The selected RotorHazard class id
        :param event_url: The FPVScores
        """

        def generate_score_data(races: list[SavedRaceMeta]):

            raceclass: RaceClass = self._rhapi.db.raceclass_by_id(selected_rh_class)

            if (
                self._rhapi.db.raceclass_attribute_value(selected_rh_class, "mgp_mode")
                == MGPMode.ZIPPYQ
            ):
                yield from self._parse_zippyq_data(selected_mgp_race, event_url, races)

            elif (
                self._rhapi.db.raceclass_attribute_value(selected_rh_class, "mgp_mode")
                == MGPMode.BRACKET
            ):
                yield from self._parse_incremental_round_data(
                    selected_mgp_race, event_url, races
                )

            elif raceclass.round_type == 1:
                yield from self._parse_heat_group_data(
                    selected_mgp_race, event_url, races
                )

            else:
                yield from self._parse_heat_data(selected_mgp_race, event_url, races)

        races: list[SavedRaceMeta] = self._rhapi.db.races_by_raceclass(
            selected_rh_class
        )

        if not self.slot_score(generate_score_data(races)):
            return False

        message = "Results successfully pushed to MultiGP."
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))
        return True

    def _rankings_from_leaderboard_data(self, data: dict) -> list[dict]:
        """
        Generates formated pilot rankings from leaderboard data

        :param data: The input leaderboard data
        :return: Formated ranking data
        """
        rankings = []

        for pilot in data:
            pilot_id = int(pilot["pilot_id"])

            if multigp_id := int(
                self._rhapi.db.pilot_attribute_value(pilot_id, "mgp_pilot_id")
            ):
                class_position = pilot["position"]
                result_dict = {"orderNumber": class_position, "pilotId": multigp_id}
                rankings.append(result_dict)

            else:
                logger.warning(
                    "Pilot %s does not have a MultiGP Pilot ID. Skipping...",
                    {pilot["pilot_id"]},
                )

        return rankings

    def push_bracketed_rankings(
        self, selected_mgp_race: str, selected_rh_class: int
    ) -> bool:
        """
        Pushes the overall rankings of the selected RotorHazard race class
        to the MultiGP race.

        :param selected_mgp_race: The set MultiGP race
        :param selected_rh_class: The selected RotorHazard race class
        :return: Status
        """

        if selected_rh_class == "" or selected_rh_class is None:
            return False

        if rankings := self._rhapi.db.raceclass_ranking(selected_rh_class):
            win_condition = None
            data = rankings["ranking"]

        elif results_list := self._rhapi.db.raceclass_results(selected_rh_class):
            primary_leaderboard = results_list["meta"]["primary_leaderboard"]
            win_condition = results_list["meta"]["win_condition"]
            data = results_list[primary_leaderboard]

        else:
            return False

        if rankings or (results_list and win_condition):

            rankings_ = self._rankings_from_leaderboard_data(data)

            if self._multigp.push_overall_race_results(selected_mgp_race, rankings_):
                message = "Rankings pushed to MultiGP"
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                return True

            message = "Failed to push rankings to MultiGP"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))

        return False

    def raceclass_rankings_push(self) -> bool:
        """
        Trigger a rankings push to all imported MultiGP races

        :return: Push status
        """
        gq_active = self._rhapi.db.option("global_qualifer_event") == "1"

        for index, race in enumerate(
            json.loads(self._rhapi.db.option("mgp_event_races"))
        ):
            if gq_active:
                if self._verification.capture_race_results(race["mgpid"]):
                    message = "Successfully processed Global Qualifer race results"
                    self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                else:
                    message = "Failed to process Global Qualifer race results"
                    self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                    return False
            else:
                self.push_bracketed_rankings(
                    race["mgpid"], self._rhapi.db.option(f"ranks_select_{index}")
                )

        return True

    def raceclass_results_push(self, event_url: Union[str, None] = None) -> bool:
        """
        Trigger a results push to all imported MultiGP races
        """
        gq_active = self._rhapi.db.option("global_qualifer_event") == "1"

        for index, race in enumerate(
            json.loads(self._rhapi.db.option("mgp_event_races"))
        ):
            if gq_active:
                rh_class: RaceClass
                for rh_class in self._rhapi.db.raceclasses:
                    mgp_id = self._rhapi.db.raceclass_attribute_value(
                        rh_class.id, "mgp_raceclass_id"
                    )
                    if mgp_id == race["mgpid"]:
                        break
                else:
                    message = "Imported Global Qualifier class not found... aborting results push"
                    self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                    return False

                if self.raceclass_slot_score(race["mgpid"], rh_class.id, event_url):
                    return True
            else:
                if self.raceclass_slot_score(
                    race["mgpid"],
                    self._rhapi.db.option(f"results_select_{index}"),
                    event_url,
                ):
                    return True

        return False

    def _gq_push_checks(self) -> bool:
        """
        System checks before pushing global qualifier data

        :return: The status of the checks
        """

        self._rhapi.db.option_set("consecutivesCount", 3)
        verification_status = self._verification.get_system_status()
        for key, value in verification_status.items():
            if not value:
                message = f"Stopping Results push - {key}"
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                logger.warning(message)
                return False

        return True

    def _run_fpvscores_sync(self, gq_active: bool) -> tuple[bool, Union[str, None]]:
        """
        Manage the data push to FPVScores

        :param gq_active: Configure the push for a global qualifier
        :return: The status and event url
        """
        if gq_active or all(self._generate_fpvscores_conditions()):

            if gq_active:
                self._rhapi.db.option_set("push_fpvs", "1")

            with self._fpvscores.sync_guard:
                if not self._fpvscores.sync_ran:
                    self._fpvscores.run_full_sync()

            if not self._rhapi.db.option("event_uuid_toolkit"):
                return False, None

            event_url = self._fpvscores.get_event_url()
            self._rhapi.ui.broadcast_ui("format")

        else:
            event_url = None

        return True, event_url

    def zippyq_slot_score(self, args: dict[str, int]) -> None:
        """
        Push results of a saved ZippyQ race to MultiGP

        :param args: Callback args
        """

        race_info: SavedRaceMeta = self._rhapi.db.race_by_id(args["race_id"])
        class_id = race_info.class_id

        round_num = round_num = int(
            self._rhapi.db.heat_attribute_value(race_info.heat_id, "zippyq_round_num")
        )

        if (
            self._rhapi.db.raceclass_attribute_value(class_id, "mgp_mode")
            != MGPMode.ZIPPYQ
            or not round_num
        ):
            return

        gq_active = self._rhapi.db.option("global_qualifer_event") == "1"
        if gq_active and not self._gq_push_checks():
            return

        message = "Automatically uploading ZippyQ data to MultiGP..."
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))

        selected_race = self._rhapi.db.raceclass_attribute_value(
            class_id, "mgp_raceclass_id"
        )

        heat_ids: list[Heat] = []
        heat: Heat
        for heat in self._rhapi.db.heats_by_class(class_id):
            heat_ids.append(heat.id)

        event_url = self._fpvscores.get_event_url()

        if self.slot_score(
            [
                self.generate_formated_race_data(
                    race_info, selected_race, round_num, 1, event_url
                )
            ]
        ):
            message = "ZippyQ data successfully pushed to MultiGP."
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))

    def manual_push_results(self, args: Union[dict, None] = None) -> None:
        """
        Wrapper for _manual_push_results. Prevents multiple pushes from being active
        at once

        :param _args: Callback args, defaults to None
        """

        if self.active_sync.locked():
            message = "Already working on pushing results. Please wait..."
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return

        with self.active_sync:
            self._manual_push_results(args)

    def _manual_push_results(self, _args: Union[dict, None] = None) -> None:
        """
        Pushes the results of a RotorHazard class to MultiGP

        :param _args: Callback args, defaults to None
        """

        gq_active = self._rhapi.db.option("global_qualifer_event") == "1"

        if gq_active:
            if not self._gq_push_checks():
                return
        else:
            for index, race in enumerate(
                json.loads(self._rhapi.db.option("mgp_event_races"))
            ):
                selected_results = self._rhapi.db.option(f"results_select_{index}")
                if selected_results == "":
                    message = f"Choose a class to upload results for {race['name']}"
                    self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                    return

        status, event_url = self._run_fpvscores_sync(gq_active)
        if status is False:
            return

        message = "Starting to push results to MultiGP..."
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))

        if self.raceclass_results_push(event_url):
            self.raceclass_rankings_push()
