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

    # Race attributes
    result_list = UIField(name = 'race_pilots', label = 'Pilot Result List', field_type = UIFieldType.TEXT, value = '')
    rhapi.fields.register_race_attribute(result_list)

    # Global attributes
    mgp_race_id = UIField(name = 'mgp_race_id', label = 'Import Race ID', field_type = UIFieldType.TEXT, value='')
    rhapi.fields.register_option(mgp_race_id)
    zippyq_event = UIField(name = 'zippyq_races', label = 'ZippyQ Races', field_type = UIFieldType.BASIC_INT, value=0)
    rhapi.fields.register_option(zippyq_event)
    global_qualifer_event = UIField(name = 'global_qualifer_event', label = 'GQ Event', field_type = UIFieldType.CHECKBOX, value='0')
    rhapi.fields.register_option(global_qualifer_event)
    mgp_event_races = UIField(name = 'mgp_event_races', label = 'GQ Event', field_type = UIFieldType.TEXT, value='[]')
    rhapi.fields.register_option(mgp_event_races)

    # MultiGP Credentials
    rhapi.ui.register_panel('multigp_set', 'MultiGP Toolkit Settings', 'settings')
    
    apikey_field = UIField(name = 'mgp_api_key', label = 'Chapter API Key', field_type = UIFieldType.PASSWORD,
                           desc="Changes are active after a reboot. Plugin is setup when an internet connection is detected.")
    rhapi.fields.register_option(apikey_field, 'multigp_set')

    store_pilot_url = UIField(name = 'store_pilot_url', label = 'Store Pilot URL', field_type = UIFieldType.CHECKBOX,
                           desc="Changes are active after a reboot. Stores the pilot's MultiGP profile image URL when importing a race.")
    rhapi.fields.register_option(store_pilot_url, 'multigp_set')

    # Plugin Functional Features
    RHmanager(rhapi)