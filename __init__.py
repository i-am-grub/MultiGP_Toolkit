import logging
from RHUI import UIField, UIFieldType
from plugins.MultiGP_Toolkit.RHmanager import RHmanager

logger = logging.getLogger(__name__)

def initialize(rhapi):

    # Pilot attributes
    mgp_pilot_id = UIField(name = 'mgp_pilot_id', label = 'MultiGP Pilot ID', field_type = UIFieldType.TEXT)
    rhapi.fields.register_pilot_attribute(mgp_pilot_id)

    # Class attributes
    mpg_race_id = UIField(name = 'mgp_raceclass_id', label = 'MultiGP Race ID', field_type = UIFieldType.TEXT)
    rhapi.fields.register_raceclass_attribute(mpg_race_id)
    zippyq_class = UIField(name = 'zippyq_class', label = 'ZippyQ Race', field_type = UIFieldType.CHECKBOX)
    rhapi.fields.register_raceclass_attribute(zippyq_class)
    gq_class = UIField(name = 'gq_class', label = 'GQ Class', field_type = UIFieldType.CHECKBOX)
    rhapi.fields.register_raceclass_attribute(gq_class)

    # Heat attributes
    heat_profile_id = UIField(name = 'heat_profile_id', label = 'Heat Profile', field_type = UIFieldType.BASIC_INT)
    rhapi.fields.register_raceformat_attribute(heat_profile_id)

    # Format attributes
    gq_format = UIField(name = 'gq_format', label = 'GQ Format', field_type = UIFieldType.CHECKBOX)
    rhapi.fields.register_raceformat_attribute(gq_format)

    # Global attributes
    mgp_race_id = UIField(name = 'mgp_race_id', label = 'Import Race ID', field_type = UIFieldType.TEXT, value='')
    rhapi.fields.register_option(mgp_race_id)
    zippyq_event = UIField(name = 'zippyq_event', label = 'ZippyQ Event', field_type = UIFieldType.CHECKBOX, value='0')
    rhapi.fields.register_option(zippyq_event)
    global_qualifer_event = UIField(name = 'global_qualifer_event', label = 'GQ Event', field_type = UIFieldType.CHECKBOX, value='0')
    rhapi.fields.register_option(global_qualifer_event)

    # MultiGP Credentials
    rhapi.ui.register_panel('multigp_cred', 'MultiGP Credentials', 'settings')
    apikey_field = UIField(name = 'mgp_api_key', label = 'Chapter API Key', field_type = UIFieldType.PASSWORD,
                           desc="Changes are active after a reboot. Plugin is setup when an internet connection is detected.")
    rhapi.fields.register_option(apikey_field, 'multigp_cred')

    # Plugin Functional Features
    RHmanager(rhapi)