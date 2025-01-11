"""
User Interface Management
"""

import json
from collections.abc import Callable

from RHAPI import RHAPI
from RHUI import UIField, UIFieldType, UIFieldSelectOption
from Database import Pilot, Heat, RaceClass, SavedRaceMeta

from .enums import MGPMode
from .multigpapi import MultiGPAPI
from .fpvscoresapi import standard_plugin_not_installed


class UImanager:
    """
    Manage the UI updates for the plugin
    """

    _rhapi: RHAPI
    _multigp: MultiGPAPI
    _chapter_name: str
    """The imported chapter name"""

    def __init__(self, rhapi: RHAPI, multigp: MultiGPAPI):
        self._rhapi = rhapi
        """A stored instance of RHAPI"""
        self._multigp = multigp
        """A stored instance of the MultiGP API manager"""

    def update_panels(self, _args: dict | None = None):
        """
        Updates the shown panels based on the current system configuration

        :param _args: Default args passed to the function, defaults to None
        """

        if not self._rhapi.db.option("mgp_api_key"):
            return

        if self._rhapi.db.option("mgp_race_id") != "":
            self.show_race_import_menu(False)
            self.show_pilot_import_menu()

            if self._rhapi.db.option("zippyq_races") > 0:
                self.show_zippyq_controls()
                self.show_zippyq_return()

            if self._rhapi.db.option("global_qualifer_event") == "1":
                self.show_gq_export_menu()
            else:
                self.show_results_export_menu()

        else:
            self.show_race_import_menu()
            self.show_pilot_import_menu(False)
            self.show_zippyq_controls(False)
            self.show_zippyq_return(False)
            self.show_results_export_menu(False)
            self.show_gq_export_menu(False)

        self._rhapi.ui.broadcast_ui("format")
        self._rhapi.ui.broadcast_ui("marshal")
        self._rhapi.ui.broadcast_ui("run")

    def set_chapter_name(self, chapter_name: str):
        """
        Sets the chapter name to use in the user interface

        :param chapter_name: The chapter name
        """
        self._chapter_name = chapter_name

    def create_race_import_menu(self, callback: Callable):
        """
        Generates the race import menu

        :param callback: The callback to register the button to.
        """
        self._rhapi.ui.register_panel(
            "multigp_race_import",
            f"MultiGP Race Import - {self._chapter_name}",
            "",
            order=0,
        )
        self.mgp_event_selector()

        auto_logo = UIField(
            "auto_logo",
            "Download Logo",
            desc="Download and set chapter logo from MultiGP on [Import Event]",
            field_type=UIFieldType.CHECKBOX,
        )
        self._rhapi.fields.register_option(auto_logo, "multigp_race_import")

        self._rhapi.ui.register_quickbutton(
            "multigp_race_import",
            "refresh_events",
            "Refresh MultiGP Events",
            self.mgp_event_selector,
            args={"refreshed": True},
        )
        self._rhapi.ui.register_quickbutton(
            "multigp_race_import", "import_mgp_event", "Import Event", callback
        )

    def show_race_import_menu(self, show=True):
        """
        Either Displays or hides the pilot import menu

        :param show: Shows the race import menu if `True`,
        hides the menu if set to `False`, defaults to True
        """
        if show:
            self._rhapi.ui.register_panel(
                "multigp_race_import",
                f"MultiGP Race Import - {self._chapter_name}",
                "format",
                order=0,
            )
        else:
            self._rhapi.ui.register_panel(
                "multigp_race_import",
                f"MultiGP Race Import - {self._chapter_name}",
                "",
                order=0,
            )

    def create_pilot_import_menu(self, callback: Callable):
        """
        Creates the pilots import menu.

        :param callback: The callback to register the button to.
        """
        self._rhapi.ui.register_panel(
            "multigp_pilot_import", "MultiGP Pilot Import", "", order=0
        )
        self._rhapi.ui.register_quickbutton(
            "multigp_pilot_import", "import_pilots", "Import Pilots", callback
        )

    def show_pilot_import_menu(self, show=True):
        """
        Either Displays or hides the pilot import menu

        :param show: Shows the pilot import menu if `True`,
        hides the menu if set to `False`, defaults to True
        """
        if show:
            self._rhapi.ui.register_panel(
                "multigp_pilot_import", "MultiGP Pilot Import", "format", order=0
            )
        else:
            self._rhapi.ui.register_panel(
                "multigp_pilot_import", "MultiGP Pilot Import", "", order=0
            )

    def create_zippyq_controls(self, callback: Callable):
        """
        Creates the ZippyQ controls menu

        :param callback: The callback to register the button to.
        """
        self._rhapi.ui.register_panel("zippyq_controls", "ZippyQ Controls", "", order=0)

        auto_zippy_text = self._rhapi.language.__("Use Automatic ZippyQ Import")
        auto_zippy = UIField(
            "auto_zippy",
            auto_zippy_text,
            desc="Automatically downloads and sets the next ZippyQ round on race finish.",
            field_type=UIFieldType.CHECKBOX,
        )
        self._rhapi.fields.register_option(auto_zippy, "zippyq_controls")

        active_import_text = self._rhapi.language.__("Active Race on Import")
        active_import = UIField(
            "active_import",
            active_import_text,
            desc="Automatically set the downloaded round as the active race on import",
            field_type=UIFieldType.CHECKBOX,
        )
        self._rhapi.fields.register_option(active_import, "zippyq_controls")

        self.zq_class_selector()

        self._rhapi.ui.register_quickbutton(
            "zippyq_controls",
            "zippyq_import",
            "Import Next ZippyQ Round",
            callback,
        )

    def show_zippyq_controls(self, show=True):
        """
        Either Displays or hides the zippyq import menu

        :param show: Shows the ZippyQ control menu if `True`,
        hides the menu if set to `False`, defaults to True
        """
        if show:
            self._rhapi.ui.register_panel(
                "zippyq_controls", "ZippyQ Controls", "format", order=0
            )
        else:
            self._rhapi.ui.register_panel(
                "zippyq_controls", "ZippyQ Controls", "", order=0
            )

    def create_zippyq_return(self, callback: Callable):
        """
        Creates the ZippyQ pack return menu.

        :param callback: The callback to register for the button press
        """
        self._rhapi.ui.register_panel(
            "zippyq_return", "ZippyQ Pack Return", "", order=0
        )
        self.zq_race_selector()
        self.zq_pilot_selector()

        self._rhapi.ui.register_quickbutton(
            "zippyq_return", "return_pack", "Return Pack", callback
        )

    def show_zippyq_return(self, show=True):
        """
        Either Displays or hides the ZippyQ pack return menu

        :param show: Shows the ZippyQ pack return menu if `True`, hides
        the menu if set to `False`, defaults to True
        """
        if show:
            self._rhapi.ui.register_panel(
                "zippyq_return", "ZippyQ Pack Return", "marshal", order=0
            )
        else:
            self._rhapi.ui.register_panel(
                "zippyq_return", "ZippyQ Pack Return", "", order=0
            )

    def create_results_export_menu(self, callback: Callable):
        """
        Create the results export menu

        :param fpvs_installed: Whether the FPVScores-Sync plugin is installed or not
        :param callback: The callback to use for uploading
        """
        self._rhapi.ui.register_panel(
            "results_controls", "MultiGP Results Controls", "", order=0
        )

        push_fpvs_text = self._rhapi.language.__("Upload to FPVScores on Results Push")
        push_fpvs = UIField(
            "push_fpvs",
            push_fpvs_text,
            desc=(
                "FPVScores Event UUID is optional when your "
                "MGP Chapter is linked to an FPVScores Organization"
            ),
            field_type=UIFieldType.CHECKBOX,
        )
        self._rhapi.fields.register_option(push_fpvs, "results_controls")

        fpv_scores_auto_text = self._rhapi.language.__("FPVScores Auto Sync")
        fpv_scores_auto = UIField(
            "fpvscores_autoupload_mgp",
            fpv_scores_auto_text,
            desc="Enable or disable automatic syncing. A network connection is required.",
            value=False,
            field_type=UIFieldType.CHECKBOX,
            private=not standard_plugin_not_installed(),
        )

        if standard_plugin_not_installed():

            self._rhapi.fields.register_option(fpv_scores_auto, "results_controls")

            fpv_scores_text = self._rhapi.language.__("FPVScores Event UUID")
            fpv_scores = UIField(
                "event_uuid_toolkit",
                fpv_scores_text,
                desc="Provided by FPVScores",
                value="",
                field_type=UIFieldType.TEXT,
            )
            self._rhapi.fields.register_option(fpv_scores, "results_controls")

        else:
            self._rhapi.fields.register_option(fpv_scores_auto)

        self.results_class_selector()

        self._rhapi.ui.register_quickbutton(
            "results_controls", "push_results", "Push Event Results", callback
        )

    def show_results_export_menu(self, show=True):
        """
        Either Displays or hides the results export menu

        :param show: Shows the results export menu if `True`, hides the menu if set to `False`,
        defaults to True
        """
        if show:
            self._rhapi.ui.register_panel(
                "results_controls", "MultiGP Results Controls", "format", order=0
            )
        else:
            self._rhapi.ui.register_panel(
                "results_controls", "MultiGP Results Controls", "", order=0
            )

    def create_gq_export_menu(self, callback: Callable):
        """
        Generates the Global Qualifier export menu,

        :param callback: The callback to register for the button press
        """
        self._rhapi.ui.register_panel(
            "gqresults_controls", "MultiGP Results Controls", "", order=0
        )
        self._rhapi.ui.register_quickbutton(
            "gqresults_controls",
            "push_gqresults",
            "Push Event Results",
            callback,
        )

    def show_gq_export_menu(self, show=True):
        """
        Either Displays or hides the Global Qualifier export menu

        :param show: Shows the Global Qualifier export menu if `True`, hides the menu if
        set to `False`, defaults to True
        """
        if show:
            self._rhapi.ui.register_panel(
                "gqresults_controls", "MultiGP Results Controls", "format", order=0
            )
        else:
            self._rhapi.ui.register_panel(
                "gqresults_controls", "MultiGP Results Controls", "", order=0
            )

    def mgp_event_selector(self, args: dict | None = None):
        """
        Generates or updates the selector for MultiGP event importing

        :param args: args passed as the button callback, defaults to None
        """
        mgp_races = self._multigp.pull_races()
        race_list = [UIFieldSelectOption(value=None, label="")]

        for race_id, name in mgp_races.items():
            race_selection = UIFieldSelectOption(
                value=race_id, label=f"({race_id}) {name}"
            )
            race_list.append(race_selection)

        race_selector = UIField(
            "sel_mgp_race_id",
            "MultiGP Event",
            desc="Event Selection",
            field_type=UIFieldType.SELECT,
            options=race_list,
        )
        self._rhapi.fields.register_option(race_selector, "multigp_race_import")

        if args is not None and "refreshed" in args:
            self._rhapi.ui.broadcast_ui("format")

    def results_class_selector(self, args: dict | None = None):
        """
        Generates or updates the selector for pushing race results

        :param args: Callback args, defaults to None
        """
        result_class_list = [UIFieldSelectOption(value="", label="")]
        rank_class_list = [
            UIFieldSelectOption(value="", label="Let MultiGP Calculate Overall Results")
        ]

        event_class: RaceClass
        for event_class in self._rhapi.db.raceclasses:
            race_class = UIFieldSelectOption(
                value=event_class.id, label=event_class.name
            )
            result_class_list.append(race_class)
            rank_class_list.append(race_class)

        event_races = json.loads(self._rhapi.db.option("mgp_event_races"))

        for index, race in enumerate(event_races):
            results_selector = UIField(
                f"results_select_{index}",
                f'Race Data: ({race["mgpid"]}) {race["name"]}',
                desc="Class holding the race data to be pushed to MultiGP",
                field_type=UIFieldType.SELECT,
                options=result_class_list,
            )
            self._rhapi.fields.register_option(results_selector, "results_controls")

            ranking_selector = UIField(
                f"ranks_select_{index}",
                f'Overall Results: ({race["mgpid"]}) {race["name"]}',
                desc="Class holding the Overall Results to be pushed to MultiGP.",
                field_type=UIFieldType.SELECT,
                options=rank_class_list,
            )
            self._rhapi.fields.register_option(ranking_selector, "results_controls")

        if args is not None and "refreshed" in args:
            self._rhapi.ui.broadcast_ui("format")

    def clear_multi_class_selector(self):
        """
        Clears all selectors that were generated for an imported multi-class
        event.
        """

        multi_event = json.loads(self._rhapi.db.option("mgp_event_races"))

        for index, _ in enumerate(multi_event):
            results_selector = UIField(
                f"results_select_{index}", "", field_type=UIFieldType.SELECT, options=[]
            )
            self._rhapi.fields.register_option(results_selector, "")

            ranking_selector = UIField(
                f"ranks_select_{index}", "", field_type=UIFieldType.SELECT, options=[]
            )
            self._rhapi.fields.register_option(ranking_selector, "")

    def zq_race_selector(self, _args: dict | None = None):
        """
        Generates or updates the selector for choosing a race to remove
        a ZippyQ pack from

        :param _args: Args provided by the callback, defaults to None
        """
        race_list = [UIFieldSelectOption(value=None, label="")]

        race: SavedRaceMeta
        for race in self._rhapi.db.races:
            if (
                self._rhapi.db.raceclass_attribute_value(race.class_id, "mgp_mode")
                == MGPMode.ZIPPYQ
            ):
                class_info: RaceClass = self._rhapi.db.raceclass_by_id(race.class_id)
                heat_info: Heat = self._rhapi.db.heat_by_id(race.heat_id)
                race_info = UIFieldSelectOption(
                    value=race.id, label=f"{class_info.name} - {heat_info.name}"
                )
                race_list.append(race_info)

        race_selector = UIField(
            "zq_race_select",
            "Race Result",
            field_type=UIFieldType.SELECT,
            options=race_list,
        )
        self._rhapi.db.option_set("zq_race_select", "")
        self._rhapi.fields.register_option(race_selector, "zippyq_return")

    def zq_pilot_selector(self, args: dict | None = None):
        """
        Generates or updates the selector for choosing a pilot to remove
        a ZippyQ pack from

        :param args: Callback args, defaults to None
        """

        if args is not None and args["option"] != "zq_race_select":
            return

        pilot_list = [UIFieldSelectOption(value=None, label="")]

        if race_id := self._rhapi.db.option("zq_race_select"):
            for pilot in json.loads(
                self._rhapi.db.race_attribute_value(race_id, "race_pilots")
            ):
                pilot_info: Pilot = self._rhapi.db.pilot_by_id(pilot)
                pilot_option = UIFieldSelectOption(
                    value=pilot_info.id, label=pilot_info.callsign
                )
                pilot_list.append(pilot_option)

        race_selector = UIField(
            "zq_pilot_select",
            "Pilot",
            desc=(
                "Prevents the upload of race data for selected Pilot in selected Race. "
                "NOTE: Local data is NOT deleted in this process"
            ),
            field_type=UIFieldType.SELECT,
            options=pilot_list,
        )
        self._rhapi.fields.register_option(race_selector, "zippyq_return")

        if args is not None and args["option"] == "zq_race_select":
            self._rhapi.ui.broadcast_ui("marshal")

    def zq_class_selector(self, _args: dict | None = None):
        """
        Generates or updates the selector for selecting the ZippyQ
        class from a multi-class event

        :param _args: Generic args passed to the callback, defaults to None
        """
        result_class_list = []
        zq_count = self._rhapi.db.option("zippyq_races")

        if zq_count > 1:
            rh_class: RaceClass
            for rh_class in self._rhapi.db.raceclasses:
                zq_state = self._rhapi.db.raceclass_attribute_value(
                    rh_class.id, "mgp_mode"
                )
                if zq_state == MGPMode.ZIPPYQ:
                    result_class_list.append(
                        UIFieldSelectOption(value=rh_class.id, label=rh_class.name)
                    )

            zq_class_select = UIField(
                "zq_class_select",
                "ZippyQ Class",
                desc="Select class to use with [Import Next ZippyQ Round]",
                field_type=UIFieldType.SELECT,
                options=result_class_list,
            )
            self._rhapi.fields.register_option(zq_class_select, "zippyq_controls")

        elif zq_count == 1:
            zq_class_select = UIField(
                "zq_class_select", "", field_type=UIFieldType.BASIC_INT
            )
            self._rhapi.fields.register_option(zq_class_select, "")

            for rh_class in self._rhapi.db.raceclasses:
                zq_state = self._rhapi.db.raceclass_attribute_value(
                    rh_class.id, "mgp_mode"
                )

                if zq_state == MGPMode.ZIPPYQ:
                    self._rhapi.db.option_set("zq_class_select", rh_class.id)
                    break
            else:
                self._rhapi.db.option_set("zq_class_select", 0)
