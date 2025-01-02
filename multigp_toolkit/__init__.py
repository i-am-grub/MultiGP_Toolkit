import logging

from RHUI import UIField, UIFieldType, UIFieldSelectOption
from RHAPI import RHAPI

from .rhcoordinator import RaceSyncCoordinator
from .datamanager import MultiGPMode

logger = logging.getLogger(__name__)


def initialize(rhapi: RHAPI):
    """
    Initializes the plugin. Called by the RotorHazard system When
    registering the plugin.

    :param rhapi: The RotorHazard API object
    """

    # Pilot attributes
    mgp_pilot_id = UIField(
        name="mgp_pilot_id", label="MultiGP Pilot ID", field_type=UIFieldType.TEXT
    )
    rhapi.fields.register_pilot_attribute(mgp_pilot_id)

    # Class attributes
    mpg_race_id = UIField(
        name="mgp_raceclass_id",
        label="MultiGP Race ID",
        field_type=UIFieldType.TEXT,
        private=True,
    )
    rhapi.fields.register_raceclass_attribute(mpg_race_id)

    mode_options = []
    for mode in MultiGPMode:
        mode_options.append(UIFieldSelectOption(mode, mode.name))

    mgp_mode = UIField(
        name="mgp_mode",
        label="MultiGP Race Format",
        field_type=UIFieldType.SELECT,
        options=mode_options,
        value=0,
        private=False,
    )
    rhapi.fields.register_raceclass_attribute(mgp_mode)

    gq_class = UIField(
        name="gq_class", label="GQ Class", field_type=UIFieldType.CHECKBOX, private=True
    )
    rhapi.fields.register_raceclass_attribute(gq_class)

    # Heat attributes
    heat_profile_id = UIField(
        name="heat_profile_id",
        label="Heat Profile",
        field_type=UIFieldType.BASIC_INT,
        private=True,
    )
    rhapi.fields.register_raceformat_attribute(heat_profile_id)

    # Format attributes
    gq_format = UIField(
        name="gq_format",
        label="GQ Format",
        field_type=UIFieldType.CHECKBOX,
        private=True,
    )
    rhapi.fields.register_raceformat_attribute(gq_format)

    # Race attributes
    result_list = UIField(
        name="race_pilots",
        label="Pilot Result List",
        field_type=UIFieldType.TEXT,
        value="",
        private=True,
    )
    rhapi.fields.register_race_attribute(result_list)

    # Global attributes
    mgp_race_id = UIField(
        name="mgp_race_id",
        label="Import Race ID",
        field_type=UIFieldType.TEXT,
        value="",
        private=True,
    )
    rhapi.fields.register_option(mgp_race_id)
    zippyq_event = UIField(
        name="zippyq_races",
        label="ZippyQ Races",
        field_type=UIFieldType.BASIC_INT,
        value=0,
        private=True,
    )
    rhapi.fields.register_option(zippyq_event)
    global_qualifer_event = UIField(
        name="global_qualifer_event",
        label="GQ Event",
        field_type=UIFieldType.CHECKBOX,
        value="0",
        private=True,
    )
    rhapi.fields.register_option(global_qualifer_event)
    mgp_event_races = UIField(
        name="mgp_event_races",
        label="GQ Event",
        field_type=UIFieldType.TEXT,
        value="[]",
        private=True,
    )
    rhapi.fields.register_option(mgp_event_races)

    # MultiGP Credentials
    rhapi.ui.register_panel("multigp_set", "MultiGP Toolkit Settings", "settings")

    apikey_field = UIField(
        name="mgp_api_key",
        label="Chapter API Key",
        field_type=UIFieldType.PASSWORD,
        desc="Changes are active after a reboot. Plugin is setup when an internet connection is detected.",
        private=True,
    )
    rhapi.fields.register_option(apikey_field, "multigp_set")

    store_pilot_url = UIField(
        name="store_pilot_url",
        label="Store Pilot URL",
        field_type=UIFieldType.CHECKBOX,
        desc="Changes are active after a reboot. Stores the pilot's MultiGP profile image URL when importing a race.",
        private=True,
    )
    rhapi.fields.register_option(store_pilot_url, "multigp_set")

    # Plugin Functional Features
    RaceSyncCoordinator(rhapi)
