"""
Import Data from RaceSync
"""

import json
import logging
from typing import TypeVar
from collections.abc import Generator

import gevent
import gevent.pool

from Database import Pilot, Heat, RaceClass, SavedRaceMeta

from .datamanager import _RaceSyncDataManager, MultiGPMode

T = TypeVar("T")

logger = logging.getLogger(__name__)


class RaceSyncExporter(_RaceSyncDataManager):
    """Actions for exporting data to RaceSync"""

    _connection_pool = gevent.pool.Pool(10)

    def generate_score_data_for_pilots(
        self,
        race_info: SavedRaceMeta,
        event_url: str | None,
    ):
        """
        Generates a score package for each pilot for the provided race

        :param race_info: Data for the completed race
        :param event_url: The FPVScores event url
        :yield: Formated race data
        """
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

            race_data = {}

            mgp_pilot_id = self.get_mgp_pilot_id(pilot_id)
            if mgp_pilot_id:
                race_data["pilotId"] = mgp_pilot_id
            else:
                pilot_info: Pilot = self._rhapi.db.pilot_by_id(pilot_id)
                message = (
                    f"{pilot_info.callsign} does not have a "
                    "MultiGP Pilot ID. Not pushing pilot's results..."
                )
                logger.warning(message)
                self._rhapi.ui.message_alert(self._rhapi.language.__(message))
                continue

            if result is not None:
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
                race_data["liveTimeevent_url"] = event_url

            yield (slot_num, race_data)

    def generate_score_data_for_race(
        self,
        race_info: SavedRaceMeta,
        selected_race: int,
        round_num: int,
        heat_num: int,
        event_url: str | None,
    ):
        for pilot_data in self.generate_score_data_for_pilots(race_info, event_url):
            yield (selected_race, round_num, heat_num, *pilot_data)

    def slot_score(self, data_generators: Generator[Generator, None, None]) -> bool:
        """
        Push generated data to MultiGP. Uses a gevent connection pool for parallel
        connections.

        :param data_generators: Generators for formating data.
        :return: Status of the push
        """

        def combined_generators(list_of_generators):
            for generator in list_of_generators:
                yield from generator

        statuses = self._connection_pool.map(
            self._multigp.push_slot_and_score, combined_generators(data_generators)
        )

        if not all(statuses):
            message = "Results push to MultiGP FAILED."
            self._rhapi.ui.message_alert(self._rhapi.language.__(message))
            return False

        return True

    def _generate_fpvscores_conditions(self) -> Generator[bool, None, None]:
        """
        Lazily generate the conditions

        :yield:
        """
        yield self._rhapi.db.option("push_fpvs") == "1"
        yield linkedMGPOrg(self._rhapi) or self._rhapi.db.option("event_uuid_toolkit")

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

        :param races: _description_
        :return: _description_
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
        self, selected_mgp_race: int, event_url: str | None, races: list[SavedRaceMeta]
    ):
        """
        Parses class data in the `Generate Heat Groups` format
        to be compatible with MultiGP predefined heats

        :param selected_mgp_race: The selected MultiGP race
        :param event_url: The FPVScores event url
        :param races: The race data
        :yield: The formated data
        """

        data = self._bundle_by_group(races)
        for group_id, races_ in data.items():
            heat_index = 1
            for race_info in races_:
                yield self.generate_score_data_for_race(
                    race_info,
                    selected_mgp_race,
                    group_id + 1,
                    heat_index,
                    event_url,
                )
                heat_index += 1

    def _parse_heat_data(
        self, selected_mgp_race: int, event_url: str | None, races: list[SavedRaceMeta]
    ):
        """
        Parses class data in the `Count Races per Heat` format
        to be compatible with MultiGP predefined heats

        :param selected_mgp_race: The selected MultiGP race
        :param event_url: The FPVScores event url
        :param races: The race data
        :yield: The formated data
        """

        data = self._bundle_by_heat(races)
        heat_index = 1
        for races_ in data.values():
            for race_info in races_:
                yield self.generate_score_data_for_race(
                    race_info,
                    selected_mgp_race,
                    race_info.round_id,
                    heat_index,
                    event_url,
                )

            heat_index += 1

    def _parse_zippyq_data(
        self, selected_mgp_race: int, event_url: str | None, races: list[SavedRaceMeta]
    ):
        """
        Parses class data to be compatible with ZippyQ

        :param selected_mgp_race: The selected MultiGP race
        :param event_url: The FPVScores event url
        :param races: The race data
        :yield: The formated data
        """

        def id_from_race(race_info: SavedRaceMeta):
            return race_info.id

        races.sort(key=id_from_race)
        for index, race_info in enumerate(races):
            yield self.generate_score_data_for_race(
                race_info,
                selected_mgp_race,
                index + 1,
                1,
                event_url,
            )

    def manual_slot_score(
        self, selected_mgp_race: int, selected_rh_class: int, event_url: str
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

            if raceclass.round_type == 1:
                yield from self._parse_heat_group_data(
                    selected_mgp_race, event_url, races
                )

            elif (
                self._rhapi.db.raceclass_attribute_value(selected_rh_class, "mgp_mode")
                == MultiGPMode.PREDEFINED_HEATS
            ):
                yield from self._parse_heat_data(selected_mgp_race, event_url, races)

            else:
                yield from self._parse_zippyq_data(selected_mgp_race, event_url, races)

        races: list[SavedRaceMeta] = self._rhapi.db.races_by_raceclass(
            selected_rh_class
        )

        if not self.slot_score(generate_score_data(races)):
            return False

        message = "Results successfully pushed to MultiGP."
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))
        return True

    # Automatially push results of ZippyQ heat
    def auto_slot_score(self, args):

        race_info = self._rhapi.db.race_by_id(args["race_id"])
        class_id = race_info.class_id

        # ZippyQ checks
        if self._rhapi.db.raceclass_attribute_value(class_id, "zippyq_class") != "1":
            return

        selected_race = self._rhapi.db.raceclass_attribute_value(
            class_id, "mgp_raceclass_id"
        )
        gq_active = self._rhapi.db.option("global_qualifer_event") == "1"

        if gq_active:
            self._rhapi.db.option_set("consecutivesCount", 3)
            verification_status = self._verification.get_system_status()
            for key, value in verification_status.items():
                if not value:
                    message = f"Stopping Results push - {key}"
                    self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                    logger.warning(message)
                    return

        if self._rhapi.db.raceclass_attribute_value(class_id, "gq_class") == "1":
            self.clear_uuid()
            mgp_raceclass_id = self._rhapi.db.raceclass_attribute_value(
                class_id, "mgp_raceclass_id"
            )
            self._rhapi.db.option_set("mgp_race_id", mgp_raceclass_id)
            message, uuid = runPushMGP(self._rhapi)
            if uuid is None:
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                return
            event_url = getURLfromFPVS(self._rhapi, uuid)
            self._rhapi.ui.broadcast_ui("format")
        elif all(self._generate_fpvscores_conditions()):
            mgp_raceclass_id = self._rhapi.db.raceclass_attribute_value(
                class_id, "mgp_raceclass_id"
            )
            self._rhapi.db.option_set("mgp_race_id", mgp_raceclass_id)
            message, uuid = runPushMGP(self._rhapi)
            if uuid is None:
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                event_url = None
            else:
                event_url = getURLfromFPVS(self._rhapi, uuid)
                self._rhapi.db.option_set("event_uuid_toolkit", uuid)
                self._rhapi.ui.broadcast_ui("format")
        else:
            uuid = self._rhapi.db.option("event_uuid_toolkit")
            event_url = None

        # Upload Results
        message = "Automatically uploading race data..."
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))
        heat_info = self._rhapi.db.heat_by_id(race_info.heat_id)

        heat_ids = []
        for heat in self._rhapi.db.heats_by_class(class_id):
            heat_ids.append(heat.id)

        round_num = heat_ids.index(heat_info.id) + 1

        if self.slot_score(
            race_info,
            selected_race,
            False,
            round_num,
            event_url=event_url,
        ):
            message = "Data successfully pushed to MultiGP."
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))

    def push_bracketed_rankings(self, selected_mgp_race: int, selected_rh_class: int):
        """
        Pushes the overall rankings of the selected RotorHazard race class
        to the MultiGP race.

        :param selected_mgp_race: The set MultiGP race
        :param selected_rh_class: The selected RotorHazard race class
        """

        if selected_rh_class == "" or selected_rh_class is None:
            return

        if rankings := self._rhapi.db.raceclass_ranking(selected_rh_class):
            win_condition = None
            data = rankings["ranking"]

        elif results_list := self._rhapi.db.raceclass_results(selected_rh_class):
            primary_leaderboard = results_list["meta"]["primary_leaderboard"]
            win_condition = results_list["meta"]["win_condition"]
            data = results_list[primary_leaderboard]

        else:
            return

        if rankings or (results_list and win_condition):
            results = []

            for pilot in data:
                if multigp_id := int(
                    self._rhapi.db.pilot_attribute_value(
                        pilot["pilot_id"], "mgp_pilot_id"
                    )
                ):
                    class_position = pilot["position"]
                    result_dict = {"orderNumber": class_position, "pilotId": multigp_id}
                    results.append(result_dict)
                else:
                    logger.warning(
                        "Pilot %s does not have a MultiGP Pilot ID. Skipping...",
                        {pilot["pilot_id"]},
                    )

            if self._multigp.push_overall_race_results(selected_mgp_race, results):
                message = "Rankings pushed to MultiGP"
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            else:
                message = "Failed to push rankings to MultiGP"
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))

    def _push_gq_results(self):

        self._rhapi.db.option_set("consecutivesCount", 3)
        verification_status = self._verification.get_system_status()
        for key, value in verification_status.items():
            if not value:
                message = f"Stopping Results push - {key}"
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                logger.warning(message)
                return

        self._rhapi.db.option_set("push_fpvs", "1")
        self.clear_uuid()
        message, uuid = runPushMGP(self._rhapi)
        if uuid is None:
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return
        self._rhapi.ui.broadcast_ui("format")
        event_url = getURLfromFPVS(self._rhapi, uuid)

    def push_results(self, _args: dict | None = None) -> None:
        """
        Pushes the results of a RotorHazard class to MultiGP

        :param _args: _description_, defaults to None
        """

        db_pilot: Pilot
        for db_pilot in self._rhapi.db.pilots:
            if not self.get_mgp_pilot_id(db_pilot.id):
                message = f"{db_pilot.callsign} does not have a MultiGP Pilot ID. Stopping results push..."
                self._rhapi.ui.message_alert(self._rhapi.language.__(message))
                return

        gq_active = self._rhapi.db.option("global_qualifer_event") == "1"

        if gq_active:
            self._rhapi.db.option_set("consecutivesCount", 3)
            verification_status = self._verification.get_system_status()
            for key, value in verification_status.items():
                if not value:
                    message = f"Stopping Results push - {key}"
                    self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                    logger.warning(message)
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

        if gq_active:
            self._rhapi.db.option_set("push_fpvs", "1")
            self.clear_uuid()
            message, uuid = runPushMGP(self._rhapi)
            if uuid is None:
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                return
            self._rhapi.ui.broadcast_ui("format")
            event_url = getURLfromFPVS(self._rhapi, uuid)
        elif all(self._generate_fpvscores_conditions()):
            message, uuid = runPushMGP(self._rhapi)
            if uuid is None:
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                return
            else:
                event_url = getURLfromFPVS(self._rhapi, uuid)
                self._rhapi.db.option_set("event_uuid_toolkit", uuid)
                self._rhapi.ui.broadcast_ui("format")
        else:
            uuid = self._rhapi.db.option("event_uuid_toolkit")
            event_url = None

        # Determine results formating
        message = "Starting to push results to MultiGP... This may take some time..."
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))

        # Rankings Push
        for index, race in enumerate(
            json.loads(self._rhapi.db.option("mgp_event_races"))
        ):
            if gq_active:
                for rh_class in self._rhapi.db.raceclasses:
                    mgp_id = self._rhapi.db.raceclass_attribute_value(
                        rh_class.id, "mgp_raceclass_id"
                    )
                    if mgp_id == race["mgpid"]:
                        break
                else:
                    message = "Imported Global Qualifier class not found... aborting results push"
                    self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                    return
                if not self.manual_slot_score(race["mgpid"], rh_class.id, event_url):
                    return
            else:
                if not self.manual_slot_score(
                    race["mgpid"],
                    self._rhapi.db.option(f"results_select_{index}"),
                    event_url,
                ):
                    return

        # Rankings Push
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
            else:
                self.push_bracketed_rankings(
                    race["mgpid"], self._rhapi.db.option(f"ranks_select_{index}")
                )
