"""
Import Data from RaceSync
"""

import json
import logging
from collections.abc import Generator
from typing import TypeVar, Union

from Database import (
    Heat,
    HeatAdvanceType,
    HeatNode,
    Pilot,
    Profiles,
    RaceClass,
    RaceFormat,
    SavedRaceMeta,
)
from gevent.lock import BoundedSemaphore
from RHAPI import RHAPI

from .enums import DefaultMGPFormats, MGPFormat, MGPMode
from .multigpapi import MultiGPAPI

T = TypeVar("T")
"""Generic type variable"""

logger = logging.getLogger(__name__)
"""Logger for the module"""


class RaceSyncImporter:
    """Actions for importing data from RaceSync"""

    def __init__(
        self,
        rhapi: RHAPI,
        multigp: MultiGPAPI,
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
        self._zippq_lock = BoundedSemaphore()
        """Lock for ensuring zippyq pulls"""

    def pilot_search(
        self, mgp_pilot: dict[str, T], *, update_attrs: bool = False
    ) -> int:
        """
        Attempt to match a MultiGP pilot with a RH pilot from a provided list.
        Create a new pilot if a match is not found.

        :param db_pilots: The list of RH pilots to use for matching
        :param mgp_pilot: The MultiGP pilot to attempt to match
        :param update_attrs: Update the pilot attributes even when seaching for pilot
        :return: The id of the RH pilot that was either matched or created
        """
        if ids := self._rhapi.db.pilot_ids_by_attribute(
            "mgp_pilot_id", mgp_pilot["pilotId"]
        ):
            pilot_id = ids[0]

            if not update_attrs:
                return pilot_id

        else:
            mgp_pilot_name = f"{mgp_pilot['firstName']} {mgp_pilot['lastName']}"
            db_pilot: Pilot = self._rhapi.db.pilot_add(
                name=mgp_pilot_name, callsign=mgp_pilot["userName"]
            )

            pilot_id = db_pilot.id

        attrs = {"mgp_pilot_id": mgp_pilot["pilotId"]}

        if "profilePictureUrl" in mgp_pilot:
            attrs.update(
                {
                    "PilotDetailPhotoURL": mgp_pilot["profilePictureUrl"],
                }
            )

        if "velocidroneUid" in mgp_pilot:
            attrs.update(
                {
                    "velo_uid": mgp_pilot["velocidroneUid"],
                }
            )

        self._rhapi.db.pilot_alter(pilot_id, attributes=attrs)

        return int(pilot_id)

    def _generate_gq_format_checks(
        self, race_format: RaceFormat, mgp_format: MGPFormat
    ) -> Generator[bool, None, None]:
        """
        Lazily run checks for global qualifier conditions

        :param race_format: The database format to check
        :param mgp_format: The MultiGP format to match to the race_format
        :yield: The status of each check
        """
        yield mgp_format.mgp_gq
        yield race_format.name == mgp_format.format_name
        yield (
            self._rhapi.db.raceformat_attribute_value(race_format.id, "gq_format")
            == "1"
        )

    def format_search(self, db_formats: list[RaceFormat], mgp_format: MGPFormat) -> int:
        """
        Attempt to match a MultiGP format with a RH format from a provided list.
        Create a new format if a match is not found.

        :param db_formats: The list of RH formats to use for matching
        :param mgp_format: The MultiGP format to match
        :return: The id of the RH format that was either matched or created.
        """

        for rh_format in db_formats:
            if all(self._generate_gq_format_checks(rh_format, mgp_format)) or (
                rh_format.name == mgp_format.format_name and not mgp_format.mgp_gq
            ):
                format_id = rh_format.id
                break

        else:
            race_format: RaceFormat = self._rhapi.db.raceformat_add(
                name=mgp_format.format_name,
                win_condition=mgp_format.win_condition,
                unlimited_time=mgp_format.unlimited_time,
                race_time_sec=mgp_format.race_time_sec,
                start_behavior=mgp_format.start_behavior,
                staging_delay_tones=2,
                staging_fixed_tones=3,
                team_racing_mode=mgp_format.team_racing_mode,
            )
            format_id = race_format.id
            self._rhapi.db.raceformat_alter(
                format_id, attributes={"gq_format": mgp_format.mgp_gq}
            )

        return int(format_id)

    def fprofile_search(self, frequencyset: dict[str, list]) -> int:
        """
        Search the database for a matching frequency profile.
        Creates a new profile if not found.
        Sets the matched or created profile as active.

        :param frequencyset: The frequency set to search for in the
        database
        :return: The id of the frequency set
        """
        imported_set = json.dumps(frequencyset)
        frequencyset_names = []

        profiles: list[Profiles] = self._rhapi.db.frequencysets
        for profile in profiles:
            frequencyset_names.append(profile.name)
            if profile.frequencies == imported_set:
                self._rhapi.db.option_set("currentProfile", profile.id)
                break
        else:
            index = 1
            base = "MultiGP Profile"
            while f"{base} {index}" in frequencyset_names:
                index += 1
            profile = self._rhapi.db.frequencyset_add(
                name=f"{base} {index}", frequencies=imported_set
            )

        return int(profile.id)

    def import_pilots(self, _args: Union[dict, None] = None) -> None:
        """
        Imports pilots from the race selected in the RHUI.

        :param _args: Args passed from the event call, defaults to {}
        """
        selected_race = self._rhapi.db.option("mgp_race_id")

        if not selected_race:
            message = "Select a MultiGP Race to import pilots from"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return

        race_data = self._multigp.pull_race_data(selected_race)

        if race_data is None:
            message = "Bad race data"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return

        for mgp_pilot in race_data["entries"]:
            self.pilot_search(mgp_pilot, update_attrs=True)

        self._rhapi.ui.broadcast_pilots()
        message = "Pilots imported"
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))

    def _generate_format_from_data(
        self, race_data: dict[str, T]
    ) -> Union[MGPFormat, None]:
        """
        Generates the format from the race data

        :param race_data: RaceSync race data
        :return: The generated race format or None
        """
        _mgp_format = race_data["scoringFormat"]

        if _mgp_format == "0":
            logger.info("Importing standard race")
            mgp_format = DefaultMGPFormats.AGGREGATE
            self._rhapi.db.option_set("consecutivesCount", 3)
        elif _mgp_format == "1":
            logger.info("Importing standard race")
            mgp_format = DefaultMGPFormats.FASTEST
            self._rhapi.db.option_set("consecutivesCount", 3)
        elif _mgp_format == "2":
            logger.info("Importing standard race")
            mgp_format = DefaultMGPFormats.CONSECUTIVE
            self._rhapi.db.option_set("consecutivesCount", 3)
        elif _mgp_format == "6":
            logger.info("Importing standard race")
            mgp_format = DefaultMGPFormats.CONSECUTIVE
            self._rhapi.db.option_set("consecutivesCount", 2)
        else:
            return None

        if race_data["raceType"] == "2":
            # Switch from
            mgp_format = DefaultMGPFormats.GLOBAL
            # to
            # mgp_format = replace(mgp_format, format_name=GQ_FORMAT_NAME, mgp_gq=True)
            # once formats can be locked from plugins:

        return mgp_format

    def _generate_race_format(
        self, race_data: dict[str, T]
    ) -> Union[tuple[int, MGPFormat], None]:
        """
        Parse the race data from RaceSync. Use it to find a format
        in the RH database. If format not found, add a new format.

        :param race_data: RaceSync race data
        :return: The found or created format id paired with the MultiGP race format.
        None if unable to reconize the format from MultiGP.
        """

        if (mgp_format := self._generate_format_from_data(race_data)) is None:
            return None

        rh_formats = self._rhapi.db.raceformats
        format_id = self.format_search(rh_formats, mgp_format)

        if race_data["scoringDisabled"] == "0":
            self._rhapi.db.raceformat_alter(
                format_id,
                points_method="Position",
                points_settings={"points_list": "10,6,4,2,1,0"},
            )
        else:
            self._rhapi.db.raceformat_alter(format_id, points_method=False)

        return format_id, mgp_format

    def _setup_raceclass_heats(
        self,
        raceclass_id: RaceClass,
        heat_data: list,
        heat_name: Union[str, None] = None,
    ) -> Heat:
        """
        Setup heats for imported raceclass

        :param race_class: The raceclass to save to
        :param heats: The heat data from MultiGP
        :return: The last heat generated from the schedule
        """

        slot_list = []

        for hindex, heat in enumerate(heat_data):
            heat_data: Heat = self._rhapi.db.heat_add(
                name=f"Heat {hindex + 1}" if heat_name is None else heat_name,
                raceclass=raceclass_id,
            )
            rh_slots: list[HeatNode] = self._rhapi.db.slots_by_heat(heat_data.id)

            frequencyset: dict[str, list] = {"b": [], "c": [], "f": []}
            count = 0

            for pindex, mgp_pilot in enumerate(heat["entries"]):
                count += 1
                if "pilotId" in mgp_pilot:
                    db_pilot_id = self.pilot_search(mgp_pilot)
                    slot_list.append(
                        {"slot_id": rh_slots[pindex].id, "pilot": db_pilot_id}
                    )

                frequencyset["b"].append(mgp_pilot["band"])
                if mgp_pilot["channel"]:
                    frequencyset["c"].append(int(mgp_pilot["channel"]))
                else:
                    frequencyset["c"].append(None)
                frequencyset["f"].append(int(mgp_pilot["frequency"]))

            while count < len(self._rhapi.interface.seats):
                count += 1
                frequencyset["b"].append(None)
                frequencyset["c"].append(None)
                frequencyset["f"].append(0)

            fprofile_id = self.fprofile_search(frequencyset)
            self._rhapi.db.heat_alter(
                heat_data.id, attributes={"heat_profile_id": fprofile_id}
            )

        self._rhapi.db.slots_alter_fast(slot_list)
        self._rhapi.race.frequencyset = fprofile_id

        return heat_data

    def _setup_populated_rounds(
        self,
        selected_race: int,
        format_data: tuple[int, MGPFormat],
        race_data: dict[str, T],
    ) -> None:
        """
        Setup a new raceclass with predefined heat data from MultiGP

        :param selected_race: The MultiGP race id
        :param format_id: The id of the format to set the class to.
        :param race_data: Downloaded MultiGP race data
        """

        rounds: list = race_data["schedule"]["rounds"]
        heats: list = rounds[0]["heats"]

        format_id, mgp_format = format_data

        race_class: RaceClass = self._rhapi.db.raceclass_add(
            name=str(race_data["name"]),
            raceformat=format_id,
            win_condition="",
            round_type=1,
            description=str(race_data["content"]),
            rounds=len(rounds),
            heat_advance_type=HeatAdvanceType.NEXT_HEAT,
        )

        self._setup_raceclass_heats(race_class.id, heats)

        self._rhapi.db.raceclass_alter(
            race_class.id,
            attributes={
                "mgp_raceclass_id": selected_race,
                "mgp_mode": MGPMode.PREDEFINED_HEATS,
                "gq_class": mgp_format.mgp_gq,
            },
        )

    def _run_seat_check(self, schedule_data: dict) -> bool:
        """
        Checks to see if the number of slots on the MultiGP race exceeds
        the number of nodes installed on the timer

        :param race_data: The race schedule from MultiGP
        :return: The status of the check
        """

        num_of_slots = len(self._rhapi.interface.seats)
        if len(schedule_data["rounds"][0]["heats"][0]["entries"]) > num_of_slots:
            message = (
                "Attempted to import race with more slots than avaliable nodes. "
                "Please decrease the number of slots used on MultiGP"
            )
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            logger.warning(message)
            return False

        return True

    def import_class(self, selected_race: int, race_data: dict[str, T]) -> None:
        """
        Setup a new raceclass within the RHUI based on the import MultiGP race(s).

        :param selected_race: The id of the MultiGP race
        :param race_data: The imported race data
        """
        if (format_data := self._generate_race_format(race_data)) is None:
            message = "Unrecognized MultiGP Format. Stopping Import"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return

        format_id, mgp_format = format_data
        rh_race_name = str(race_data["name"])

        for mgp_pilot in race_data["entries"]:
            self.pilot_search(mgp_pilot, update_attrs=True)

        if (
            race_data["disableSlotAutoPopulation"] == "0"
            and "rounds" in race_data["schedule"]
        ):
            if not self._run_seat_check(race_data["schedule"]):
                return

            self._setup_populated_rounds(selected_race, format_data, race_data)

        elif race_data["disableSlotAutoPopulation"] == "0":
            num_rounds = 0
            race_class: RaceClass = self._rhapi.db.raceclass_add(
                name=rh_race_name,
                raceformat=format_id,
                win_condition="",
                round_type=1,
                description=str(race_data["content"]),
                rounds=num_rounds,
                heat_advance_type=HeatAdvanceType.NEXT_HEAT,
            )
            self._rhapi.db.raceclass_alter(
                race_class.id,
                attributes={
                    "mgp_raceclass_id": selected_race,
                    "mgp_mode": MGPMode.PREDEFINED_HEATS,
                    "gq_class": mgp_format.mgp_gq,
                },
            )

        else:
            zippyq_races = self._rhapi.db.option("zippyq_races")
            zippyq_races += 1
            self._rhapi.db.option_set("zippyq_races", zippyq_races)
            race_class = self._rhapi.db.raceclass_add(
                name=rh_race_name,
                raceformat=format_id,
                win_condition="",
                round_type=0,
                description=str(race_data["content"]),
                rounds=1,
                heat_advance_type=HeatAdvanceType.NONE,
            )

            self._rhapi.db.raceclass_alter(
                race_class.id,
                attributes={
                    "mgp_raceclass_id": selected_race,
                    "mgp_mode": MGPMode.ZIPPYQ,
                    "gq_class": mgp_format.mgp_gq,
                },
            )

            self._rhapi.db.option_set("zippyq_races", zippyq_races)

    def zippyq(
        self, raceclass_id: int, selected_race: str, round_num: int
    ) -> Union[Heat, None]:
        """
        Imports a single ZippyQ round

        :param raceclass_id: The raceclass to import the ZippyQ round into
        :param selected_race: The MultiGP race to import the ZippyQ from
        :param round_num: The round number to pull from RaceSync
        :return: The import ZippyQ round as a Heat or None if failed
        to import.
        """

        data: Union[dict[str, list], None] = self._multigp.pull_additional_rounds(
            selected_race, round_num
        )

        if data is None:
            message = "Data not found when attempting to import ZippyQ round"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return None

        if not data["rounds"]:
            message = "Additional ZippyQ rounds not found"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return None

        current_round = int(data["rounds"][0]["currentRound"])
        if current_round != round_num:
            data = self._multigp.pull_additional_rounds(selected_race, current_round)
            round_num = current_round

            if data is None:
                message = "Data not found when attempting to import ZippyQ round"
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                return None

        if not self._run_seat_check(data):
            return None

        heat_data = self._setup_raceclass_heats(
            raceclass_id, data["rounds"][0]["heats"], data["rounds"][0]["name"]
        )

        attrs = {"zippyq_round_num": round_num, "downloaded_zippyq": "1"}
        translation = self._rhapi.language.__("Round")
        self._rhapi.db.heat_alter(
            heat_data.id, name=f"{translation} {round_num}", attributes=attrs
        )

        self._rhapi.ui.broadcast_pilots()
        self._rhapi.ui.broadcast_heats()
        message = f"ZippyQ Round {round_num} imported."
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))

        return heat_data

    def manual_zippyq(self, _args: Union[dict, None] = None) -> None:
        """
        Used to manually trigger a ZippyQ import from the RHUI

        :param _args: Args passed from the event call, defaults to {}
        """
        if self._zippq_lock.locked():
            message = "ZippyQ: Import already in progress"
            self._rhapi.ui.message_alert(self._rhapi.language.__(message))
            return

        with self._zippq_lock:
            class_id = self._rhapi.db.option("zq_class_select")

            if not class_id:
                message = "ZippyQ class not found"
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                return

            selected_race = self._rhapi.db.raceclass_attribute_value(
                class_id, "mgp_raceclass_id"
            )

            class_heats: list[Heat] = self._rhapi.db.heats_by_class(class_id)
            if class_heats:
                last_round_num = int(
                    self._rhapi.db.heat_attribute_value(
                        class_heats[-1].id, "zippyq_round_num"
                    )
                )
            else:
                last_round_num = 0

            heat_data = self.zippyq(class_id, selected_race, last_round_num + 1)
            if heat_data is None:
                return

            if self._rhapi.db.option("active_import") == "1":
                self._rhapi.race.heat = heat_data.id

    def auto_zippyq(self, args: dict) -> None:
        """
        Automatically import the next ZippyQ round into the same
        race class as the race that tiggered the import.

        :param args: Args passed from the event call, defaults to {}
        """
        if self._zippq_lock.locked():
            return

        with self._zippq_lock:
            race_info: SavedRaceMeta = self._rhapi.db.race_by_id(args["race_id"])
            class_id = int(race_info.class_id)

            if (
                self._rhapi.db.raceclass_attribute_value(class_id, "mgp_mode")
                != MGPMode.ZIPPYQ
                or self._rhapi.db.option("auto_zippy") != "1"
            ):
                return

            message = "Automatically downloading next ZippyQ round..."
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))

            class_heats = self._rhapi.db.heats_by_class(class_id)

            last_round_num = int(
                self._rhapi.db.heat_attribute_value(
                    class_heats[-1].id, "zippyq_round_num"
                )
            )

            selected_race = self._rhapi.db.raceclass_attribute_value(
                class_id, "mgp_raceclass_id"
            )

            heat_data = self.zippyq(class_id, selected_race, last_round_num + 1)
            if heat_data is None:
                return

            if self._rhapi.db.option("active_import") == "1":
                self._rhapi.race.heat = heat_data.id
