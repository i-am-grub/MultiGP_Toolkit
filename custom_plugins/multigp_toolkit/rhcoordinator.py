"""
System Event, Data, and User Interface Coordination
"""

import json
import logging
import os
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any, TypeVar, Union

import requests
from Database import (
    Heat,
    HeatNode,
    LapSource,
    Pilot,
    RaceClass,
    RaceFormat,
    SavedRaceMeta,
)
from eventmanager import Evt
from RHAPI import RHAPI
from RHRace import Crossing
from RHUI import UIField, UIFieldType

from .enums import DefaultMGPFormats, MGPMode
from .fpvscoresapi import register_handlers
from .multigpapi import MultiGPAPI
from .rsexporter import RaceSyncExporter
from .rsimporter import RaceSyncImporter
from .uimanager import UImanager

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
except ValueError as exc:
    raise ImportError(
        "Issue when importing modules. Try reinstalling this plugin."
    ) from exc

logger = logging.getLogger(__name__)
"""Module logger"""

T = TypeVar("T")
"""Generic for typing"""


class RaceSyncCoordinator:
    """
    The bridge between the user interface, system events, and dataflow
    """

    _system_verification = SystemVerification()
    """Instance of the system verification module"""

    def __init__(self, rhapi: RHAPI):
        self._rhapi: RHAPI = rhapi
        """Instance of RHAPI"""
        self._multigp = MultiGPAPI(self._rhapi)
        """Instance of the MultiGP API manager"""
        self._ui = UImanager(rhapi, self._multigp)
        """Instance of the toolkit user interface manager"""
        self._importer = RaceSyncImporter(self._rhapi, self._multigp)
        """Instance of the RaceSync importer"""
        self._exporter = RaceSyncExporter(
            self._rhapi, self._multigp, self._system_verification
        )
        """Instance of the RaceSync exporter"""

        self._rhapi.events.on(Evt.STARTUP, self.startup, name="startup")
        self._rhapi.events.on(Evt.RACE_STAGE, self.verify_race, name="verify_race")
        self._rhapi.events.on(Evt.CLASS_ALTER, self.verify_class, name="verify_class")
        self._rhapi.events.on(
            Evt.RACE_FORMAT_ALTER, self.verify_format, name="verify_format"
        )
        self._rhapi.events.on(
            Evt.RACE_FORMAT_DELETE, self.verify_classes, name="verify_classes"
        )
        self._rhapi.events.on(
            Evt.DATABASE_RESET, self.reset_event_metadata, name="reset_event_metadata"
        )
        self._rhapi.events.on(
            Evt.DATABASE_RECOVER, self._ui.update_panels, name="update_panels"
        )
        self._rhapi.events.on(
            Evt.LAPS_SAVE, self.store_pilot_list, name="store_pilot_list"
        )
        self._rhapi.events.on(
            Evt.RACE_LAP_RECORDED, self.verify_gq_lap, name="verify_gq_lap"
        )
        self._rhapi.events.on(Evt.DATA_EXPORT_INITIALIZE, register_handlers)

        self._rhapi.events.on(
            Evt.HEAT_ADD, self.assign_zippyq_round, name="assign_zippyq_round_add"
        )
        self._rhapi.events.on(
            Evt.HEAT_DUPLICATE, self.assign_zippyq_round, name="assign_zippyq_round_dup"
        )

    def startup(self, _args: Union[dict, None] = None):
        """
        Callback to setup specific features of the plugin on startup

        :param _args: Args passed to the callback function, defaults to None
        """
        self.register_aux_plugin_attrs()
        self.verify_creds()

    def register_aux_plugin_attrs(self):
        """
        Registers attributes used by other plugins. These attributes are only
        visible if the associated plugin is installed
        """

        hide_pilot_photos = hide_velocidrone = True

        for mod in sys.modules:
            if mod.startswith("plugins.rh_pilot_photos"):
                hide_pilot_photos = False
            elif mod.startswith("plugins.velocidrone_controls"):
                hide_velocidrone = False

        pilot_photo_url = UIField(
            name="PilotDetailPhotoURL",
            label="Pilot Photo URL",
            field_type=UIFieldType.TEXT,
            private=hide_pilot_photos,
        )
        self._rhapi.fields.register_pilot_attribute(pilot_photo_url)

        velo_uid = UIField(
            name="velo_uid",
            label="Velocidrone UID",
            field_type=UIFieldType.TEXT,
            private=hide_velocidrone,
        )
        self._rhapi.fields.register_pilot_attribute(velo_uid)

    def reset_event_metadata(self, _args: Union[dict, None] = None):
        """
        Callback to reset all parameters used by the toolkit. Typically called when
        the current event in the system has been deleted or archived

        :param _args: Args passed to the callback function, defaults to None
        """
        self._rhapi.db.option_set("push_fpvs", "0")
        self._rhapi.db.option_set("fpvscores_autoupload_mgp", "0")
        self._rhapi.db.option_set("event_uuid_toolkit", "")
        self._rhapi.db.option_set("mgp_race_id", "")
        self._rhapi.db.option_set("auto_zippy", "0")
        self._rhapi.db.option_set("active_import", "0")
        self._rhapi.db.option_set("zippyq_races", 0)
        self._rhapi.db.option_set("global_qualifer_event", "0")
        self._ui.clear_multi_class_selector()
        self._rhapi.db.option_set("mgp_event_races", "[]")
        self._rhapi.db.option_set("results_select", "")
        self._rhapi.db.option_set("ranks_select", "")
        self._ui.update_panels()

    def set_frequency_profile(self, args: Union[dict, None] = None):
        """
        Callback for setting the frequency profille for the server based on the
        active heat. Allows for switching the profile for different heats.

        :param args: Callback args
        """

        fprofile_id = self._rhapi.db.heat_attribute_value(
            args["heat_id"], "heat_profile_id"
        )
        if fprofile_id:
            self._rhapi.race.frequencyset = fprofile_id
            self._rhapi.ui.broadcast_frequencies()

    def store_pilot_list(self, args: Union[dict, None] = None):
        """
        Stores a list of pilots that participated in the race as an attribute.
        This list marks what pilots should have their data pushed. Removing a
        pilot from this list prevents their data from being pushed (ZippyQ pack
        return).

        :param args: Callback args, defaults to None
        """
        race_info: SavedRaceMeta = self._rhapi.db.race_by_id(args["race_id"])
        heat_info: Heat = self._rhapi.db.heat_by_id(race_info.heat_id)
        class_info: RaceClass = self._rhapi.db.raceclass_by_id(race_info.class_id)

        race_pilots = {}

        if class_info is not None:
            gq_class = self._rhapi.db.raceclass_attribute_value(
                class_info.id, "gq_class", "0"
            )
        else:
            gq_class = "0"

        if gq_class == "0" and self._rhapi.db.option("global_qualifer_event") == "1":
            message = (
                "Warning: Saving non-valid Global Qualifer race results. "
                "Use the imported class to generate valid results."
            )
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
        else:
            slot: HeatNode
            for slot in self._rhapi.db.slots_by_heat(heat_info.id):
                if slot.pilot_id == 0:
                    continue

                race_pilots[slot.pilot_id] = slot.node_index

        self._rhapi.db.race_alter(
            race_info.id, attributes={"race_pilots": json.dumps(race_pilots)}
        )

    def verify_creds(self) -> None:
        """
        Verify the chaper api key. Sets up the remaining features of the plugin
        if the chapter's data is found.
        """

        key = self._rhapi.db.option("mgp_api_key")
        if key:
            self._multigp.set_api_key(key)
        else:
            logger.warning("A MultiGP API key has not been entered into the system")
            return

        if chapter_name := self._multigp.pull_chapter():
            self._ui.set_chapter_name(chapter_name)
            logger.info("API key for %s has been recognized", chapter_name)
            self.setup_plugin()
        else:
            logger.warning("MultiGP API key cannot be verified.")

    def setup_plugin(self) -> None:
        """
        Setup additional system events and setup the UI panels to match
        the system state.
        """
        self._rhapi.events.on(
            Evt.LAPS_SAVE, self._importer.auto_zippyq, name="auto_zippyq"
        )
        self._rhapi.events.on(
            Evt.LAPS_SAVE, self._exporter.zippyq_slot_score, name="zippyq_slot_score"
        )
        self._rhapi.events.on(
            Evt.LAPS_RESAVE, self._exporter.zippyq_slot_score, name="zippyq_slot_score"
        )

        self._rhapi.events.on(
            Evt.CLASS_ADD, self._ui.zq_class_selector, name="update_zq_selector"
        )
        self._rhapi.events.on(
            Evt.CLASS_DUPLICATE, self._ui.zq_class_selector, name="update_zq_selector"
        )
        self._rhapi.events.on(
            Evt.CLASS_ALTER, self._ui.zq_class_selector, name="update_zq_selector"
        )
        self._rhapi.events.on(
            Evt.CLASS_DELETE, self._ui.zq_class_selector, name="update_zq_selector"
        )
        self._rhapi.events.on(
            Evt.DATABASE_RESET, self._ui.zq_class_selector, name="update_zq_selector"
        )
        self._rhapi.events.on(
            Evt.DATABASE_RECOVER, self._ui.zq_class_selector, name="update_zq_selector"
        )

        self._rhapi.events.on(
            Evt.CLASS_ADD, self._ui.results_class_selector, name="update_res_selector"
        )
        self._rhapi.events.on(
            Evt.CLASS_DUPLICATE,
            self._ui.results_class_selector,
            name="update_res_selector",
        )
        self._rhapi.events.on(
            Evt.CLASS_ALTER, self._ui.results_class_selector, name="update_res_selector"
        )
        self._rhapi.events.on(
            Evt.CLASS_DELETE,
            self._ui.results_class_selector,
            name="update_res_selector",
        )
        self._rhapi.events.on(
            Evt.DATABASE_RESET,
            self._ui.results_class_selector,
            name="update_res_selector",
        )
        self._rhapi.events.on(
            Evt.DATABASE_RECOVER,
            self._ui.results_class_selector,
            name="update_res_selector",
        )

        self._rhapi.events.on(
            Evt.HEAT_ALTER, self._ui.zq_race_selector, name="zq_race_selector"
        )
        self._rhapi.events.on(
            Evt.LAPS_SAVE, self._ui.zq_race_selector, name="zq_race_selector"
        )
        self._rhapi.events.on(
            Evt.OPTION_SET, self._ui.zq_pilot_selector, name="zq_pilot_selector"
        )

        self._ui.create_race_import_menu(self.setup_event)
        self._ui.create_pilot_import_menu(self._importer.import_pilots)
        self._ui.create_zippyq_controls(self._importer.manual_zippyq)
        self._ui.create_results_export_menu(self._exporter.manual_push_results)
        self._ui.create_gq_export_menu(self._exporter.manual_push_results)
        self._ui.create_zippyq_return(self.return_pack)

        self._ui.update_panels()

    def _generate_event_checks(
        self,
    ) -> Generator[Any, None, None]:
        """
        Lazy loaded checks before importing new event

        :yield: Object to be evaluated
        """
        yield self._rhapi.db.races
        yield self._rhapi.db.heats
        yield self._rhapi.db.raceclasses
        yield self._rhapi.db.option("mgp_race_id")

    def _download_race_data(self, selected_race: str) -> dict:
        """
        Dowloads data for a specific race

        :param selected_race: The id of the MultiGP race to download from
        :return: The dowloaded data
        """

        race_data: Union[dict[str, Any], None] = self._multigp.pull_race_data(
            selected_race
        )

        if race_data is None:
            raise RuntimeError("Race data not provided from MultiGP")

        if self._rhapi.db.option("auto_logo") == "1":
            url: str = race_data["chapterImageFileName"]
            file_name = url.split("/")[-1]

            rhapi_verion = (
                self._rhapi.API_VERSION_MAJOR,
                self._rhapi.API_VERSION_MINOR,
            )
            if rhapi_verion >= (1, 3):
                data_dir = Path(self._rhapi.server.data_dir)
                save_dir = data_dir.joinpath("shared")
                os.makedirs(save_dir, exist_ok=True)
                save_location = save_dir.joinpath(file_name)
            else:
                save_location = Path(f"static/user/{file_name}")

            try:
                response = requests.get(url, timeout=5)
            except requests.exceptions.MissingSchema:
                logger.warning("Chapter logo unavaliable to download")
                return race_data
            except requests.Timeout:
                logger.warning("Timed out when attempting to download logo")
            else:
                with open(save_location, mode="wb") as file:
                    file.write(response.content)

                self._rhapi.config.set_item("UI", "timerLogo", file_name)

        return race_data

    def _verification_checks(self, race_data: dict) -> bool:
        """
        Runs system verification checks based on the imported data

        :param race_data: The data for the race
        :return: Status of checks passing
        """
        if race_data["raceType"] == "2":
            logger.info("Importing GQ race")
            for msg, status in self._system_verification.get_system_status():
                if not status:
                    message = f"Global Qualifier not imported - {msg}"
                    self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                    logger.warning(message)
                    return False

        return True

    def _import_event(self, selected_race: int, race_data: dict) -> None:
        """
        Imports all races from an event into the RotorHazard system

        :param selected_race: The selected MultiGP event imported from
        :param race_data: The race data for the MultiGP event
        """
        mgp_event_races = []

        if int(race_data["childRaceCount"]) > 0:
            for race in race_data["races"]:
                imported_data = self._multigp.pull_race_data(race["id"])
                self._importer.import_class(race["id"], imported_data)
                mgp_event_races.append({"mgpid": race["id"], "name": race["name"]})
        else:
            self._importer.import_class(selected_race, race_data)
            mgp_event_races.append({"mgpid": selected_race, "name": race_data["name"]})

        self._rhapi.db.option_set("mgp_race_id", selected_race)
        self._rhapi.db.option_set("eventName", race_data["name"])
        self._rhapi.db.option_set("eventDescription", race_data["content"])

        if race_data["raceType"] == "2":
            self._rhapi.db.option_set("global_qualifer_event", "1")
        else:
            self._rhapi.db.option_set("global_qualifer_event", "0")

        self._rhapi.db.option_set("mgp_event_races", json.dumps(mgp_event_races))

        self._rhapi.ui.broadcast_raceclasses()
        self._rhapi.ui.broadcast_raceformats()
        self._rhapi.ui.broadcast_pilots()
        self._rhapi.ui.broadcast_frequencyset()
        self._ui.update_panels()
        message = "MultiGP event imported."
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))

    def setup_event(self, _args: Union[dict, None] = None) -> None:
        """
        Sets up the event from the race selected in the RHUI.

        :param _args: Args passed from the event call, defaults to None
        """
        selected_race = self._rhapi.db.option("sel_mgp_race_id")
        if not selected_race:
            message = "Select a MultiGP Race to import"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return

        if any(self._generate_event_checks()):
            message = (
                "Archive Race, Heat, and Class data before continuing. "
                "Under the Event panel >> Archive/New Event >> Archive Event."
            )
            self._rhapi.ui.message_alert(self._rhapi.language.__(message))
            return

        race_data = self._download_race_data(selected_race)

        if self._verification_checks(race_data):
            self._import_event(selected_race, race_data)

    def assign_zippyq_round(self, args: dict) -> None:
        """
        Assignes a zippyq round as a heat attribute

        :param args: Callback args, defaults to None
        """
        heat_id: int = args["heat_id"]
        heat: Heat = self._rhapi.db.heat_by_id(heat_id)
        heats: list[Heat] = self._rhapi.db.heats_by_class(heat.class_id)

        if self._rhapi.db.heat_attribute_value(heat_id, "downloaded_zippyq") == "1":
            return

        mode = self._rhapi.db.raceclass_attribute_value(heat.class_id, "mgp_mode")

        for heat_ in reversed(heats):
            if heat_.id == heat_id:
                continue

            previous_round = int(
                self._rhapi.db.heat_attribute_value(heat_.id, "zippyq_round_num")
            )
            current_round = previous_round + 1
            heat_attrs = {"zippyq_round_num": current_round}

            if mode == MGPMode.ZIPPYQ:
                phrase = self._rhapi.language.__("Round")
                self._rhapi.db.heat_alter(
                    heat_id, name=f"{phrase} {current_round}", attributes=heat_attrs
                )
            else:
                self._rhapi.db.heat_alter(heat_id, attributes=heat_attrs)

            break
        else:
            heat_attrs = {"zippyq_round_num": 1}
            if mode == MGPMode.ZIPPYQ:
                phrase = self._rhapi.language.__("Round")
                self._rhapi.db.heat_alter(
                    heat_id, name=f"{phrase} 1", attributes=heat_attrs
                )
            else:
                self._rhapi.db.heat_alter(heat_id, attributes=heat_attrs)

    def return_pack(self, _args: Union[dict, None] = None) -> None:
        """
        Returns a pilots pack for the race.

        :param _args: Callback args, defaults to None
        """
        race_id = self._rhapi.db.option("zq_race_select")
        pilot_id = self._rhapi.db.option("zq_pilot_select")
        pilot_info: Pilot = self._rhapi.db.pilot_by_id(pilot_id)

        if not race_id or not pilot_id:
            return

        race: SavedRaceMeta = self._rhapi.db.race_by_id(race_id)
        slots: list[HeatNode] = self._rhapi.db.slots_by_heat(race.heat_id)

        for slot in slots:
            if slot.pilot_id == int(pilot_id):
                self._rhapi.db.slot_alter(slot.id, pilot=0)

        race_pilots = json.loads(
            self._rhapi.db.race_attribute_value(race_id, "race_pilots")
        )

        if pilot_id in race_pilots:
            del race_pilots[pilot_id]
            self._rhapi.db.race_alter(
                race_id, attributes={"race_pilots": json.dumps(race_pilots)}
            )

        self._ui.zq_pilot_selector(args={"option": "zq_race_select"})

        message = f"Pack returned to {pilot_info.display_callsign}"
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))

    def _race_pilots_checks(self, heat_id: int, gq_active: bool) -> bool:
        """
        Checks to verify pilot data is correct for RaceSync and Global
        Qualifier rules

        :param heat_id: ID of the heat
        :param gq_active: Whether a Global Qualifier is active or not
        :return: The status of all the checks passing
        """

        slots: list[HeatNode] = self._rhapi.db.slots_by_heat(heat_id)
        heat_pilots = []
        pilot_counter = 0

        for slot_info in slots:
            if slot_info.pilot_id == 0:
                continue

            if slot_info.pilot_id in heat_pilots:
                pilot_info: Pilot = self._rhapi.db.pilot_by_id(slot_info.pilot_id)
                message = (
                    f"MultiGP Toolkit: {pilot_info.callsign} occupies "
                    "more than one slot in current heat"
                )
                self._rhapi.ui.message_alert(self._rhapi.language.__(message))
                return False

            heat_pilots.append(slot_info.pilot_id)
            pilot_counter += 1

        if pilot_counter == 0:
            return False

        if gq_active and pilot_counter < 3:
            message = "GQ Rules: At least 3 pilots are required to start the race"
            self._rhapi.ui.message_alert(self._rhapi.language.__(message))
            return False

        return True

    def _race_zippyq_checks(self, heat_info: Heat) -> bool:
        """
        ZippyQ race checks

        :param heat_info: The heat information to check
        :return: The status of all the checks passing
        """

        heat_id = heat_info.id

        heat: Heat
        for heat in reversed(self._rhapi.db.heats_by_class(heat_info.class_id)):
            if heat.id < heat_id and self._rhapi.db.heat_max_round(heat.id) == 0:
                check_heat: Heat = self._rhapi.db.heat_by_id(heat.id)
                message = f"ZippyQ: Complete {check_heat.display_name} before starting {heat_info.display_name}"
                self._rhapi.ui.message_alert(self._rhapi.language.__(message))
                return False

            if self._rhapi.db.heat_max_round(heat.id) != 0:
                break

        return True

    def _race_code_integrity_check(self) -> bool:
        """
        Checks to make sure the system is unmodified when running a
        Global Qualifier

        :return: The status of the check
        """
        if not self._system_verification.get_integrity_check():
            message = (
                "Your system's codebase has been modified and "
                "is not approved to run Global Qualifier races"
            )
            self._rhapi.ui.message_alert(self._rhapi.language.__(message))
            logger.warning(message)
            return False

        return True

    def generate_race_conditionals(
        self, heat_info: Heat
    ) -> Generator[bool, None, None]:
        """
        Generate the conditions to run a race with a MultiGP event
        imported

        :param heat_info: The heat to verify
        :yield: Status of checks
        """

        if gq_active := self._rhapi.db.raceclass_attribute_value(
            heat_info.class_id, "gq_class" == "1"
        ):
            yield self._race_code_integrity_check()

        yield self._race_pilots_checks(heat_info.id, gq_active)

        if (
            self._rhapi.db.raceclass_attribute_value(heat_info.class_id, "mgp_mode")
            != MGPMode.PREDEFINED_HEATS
        ):
            if self._rhapi.db.heat_max_round(heat_info.id) > 0:
                message = "MultiGP Race Type: Round cannot be repeated"
                self._rhapi.ui.message_alert(self._rhapi.language.__(message))
                yield False

        if (
            self._rhapi.db.raceclass_attribute_value(heat_info.class_id, "mgp_mode")
            == MGPMode.ZIPPYQ
        ):
            yield self._race_zippyq_checks(heat_info)

    def verify_race(self, args: Union[dict, None]) -> None:
        """
        Check to make sure all parameters are met to run a race

        :param args: Callback args
        """

        if not self._rhapi.db.option("mgp_race_id"):
            return

        heat_id = args["heat_id"]
        heat_info: Heat = self._rhapi.db.heat_by_id(heat_id)

        if heat_info is None:
            return

        if not all(self.generate_race_conditionals(heat_info)):
            self._rhapi.race.stop()

    def generate_class_conditionals(
        self, raceclass: RaceClass
    ) -> Generator[bool, None, None]:
        """
        Generates the conditiaonl checks for a race class

        :param raceclass: The raceclass to verify meets the RaceSync requirements
        :yield: The staus of each check
        """
        yield raceclass.name == DefaultMGPFormats.GLOBAL.format_name
        yield raceclass.win_condition == ""
        yield (
            self._rhapi.db.raceformat_attribute_value(raceclass.format_id, "gq_format")
            == "1"
        )

    def verify_class(self, args: dict) -> None:
        """
        Verify a raceclass meets the requirements for RaceSync

        :param args: Input args from the callback
        """

        class_id = args["class_id"]

        if self._rhapi.db.raceclass_attribute_value(class_id, "gq_class") != "1":
            return

        class_info = self._rhapi.db.raceclass_by_id(class_id)

        if not all(self.generate_class_conditionals(class_info)):
            rh_formats = self._rhapi.db.raceformats
            gq_format = DefaultMGPFormats.GLOBAL
            rh_format = self._importer.format_search(rh_formats, gq_format)

            self._rhapi.db.raceclass_alter(
                class_info.id,
                name=gq_format.format_name,
                raceformat=rh_format,
                rounds=10,
                win_condition="",
            )
            self._rhapi.ui.broadcast_raceclasses()
            self._rhapi.ui.broadcast_raceformats()

    def verify_classes(self, _args: Union[dict, None] = None) -> None:
        """
        Verifies all raceclasses in the database meet the RaceSync requirements

        :param _args: Input args from the callback, defaults to None
        """

        for raceclass in self._rhapi.db.raceclasses:
            args = {"class_id": raceclass.id}
            self.verify_class(args)

    def _generate_gp_format_conditionals(
        self, raceformat: RaceFormat
    ) -> Generator[bool, None, None]:
        """
        Generates the status of each of the format checks

        :param format: The race format to check
        :yield: The status of each check
        """

        gq_format = DefaultMGPFormats.GLOBAL
        yield raceformat.name == gq_format.format_name
        yield raceformat.race_time_sec == gq_format.race_time_sec
        yield raceformat.win_condition == gq_format.win_condition
        yield raceformat.unlimited_time == gq_format.unlimited_time
        yield raceformat.start_behavior == gq_format.start_behavior
        yield raceformat.team_racing_mode == gq_format.team_racing_mode

    def verify_format(self, args: dict) -> None:
        """
        Verifies the format to be Global Qualifier compatible

        :param args: Input args for the callback
        """
        format_id = args["race_format"]

        if self._rhapi.db.raceformat_attribute_value(format_id, "gq_format") != "1":
            return

        format_info: RaceFormat = self._rhapi.db.raceformat_by_id(format_id)
        gq_format = DefaultMGPFormats.GLOBAL

        if not all(self._generate_gp_format_conditionals(format_info)):
            self._rhapi.db.raceformat_alter(
                format_info.id,
                name=gq_format.format_name,
                race_time_sec=gq_format.race_time_sec,
                unlimited_time=gq_format.unlimited_time,
                win_condition=gq_format.win_condition,
                start_behavior=gq_format.start_behavior,
                team_racing_mode=gq_format.team_racing_mode,
            )
            self._rhapi.ui.broadcast_raceformats()

    def verify_gq_lap(self, args: dict) -> None:
        """
        Verifies the source for the lap when GQ are active

        :param args: Input args for the callback
        """

        lap_data: Crossing = args["lap"]

        if (
            self._rhapi.db.option("global_qualifer_event") == "1"
            and lap_data.source == LapSource.API
        ):
            self._rhapi.race.stop()
            message = (
                "Lap detection through additional plugins "
                "is not allowed for Global Qualifers"
            )
            self._rhapi.ui.message_alert(self._rhapi.language.__(message))
