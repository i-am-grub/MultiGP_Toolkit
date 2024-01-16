import logging
from RHUI import UIField, UIFieldType
from plugins.MultiGP_Toolkit.RHmanager import RHmanager

logger = logging.getLogger(__name__)

def initialize(rhapi):

    RH = RHmanager(rhapi)

    mgp_pilot_id = UIField(name = 'mgp_pilot_id', label = 'MultiGP Pilot ID', field_type = UIFieldType.TEXT)
    rhapi.fields.register_pilot_attribute(mgp_pilot_id)
    
    mpg_race_id = UIField(name = 'mgp_raceclass_id', label = 'MultiGP Race ID', field_type = UIFieldType.TEXT)
    rhapi.fields.register_raceclass_attribute(mpg_race_id)
    zippyq_class = UIField(name = 'zippyq_class', label = 'ZippyQ Race', field_type = UIFieldType.CHECKBOX)
    rhapi.fields.register_raceclass_attribute(zippyq_class)
    gq_class = UIField(name = 'gq_class', label = 'GQ Class', field_type = UIFieldType.CHECKBOX)
    rhapi.fields.register_raceclass_attribute(gq_class)

    gq_format = UIField(name = 'gq_format', label = 'GQ Format', field_type = UIFieldType.CHECKBOX)
    rhapi.fields.register_raceformat_attribute(gq_format)

    rhapi.ui.register_panel('multigp_cred', 'MultiGP Credentials', 'settings')

    apikey_field = UIField(name = 'mgp_api_key', label = 'Chapter API Key', field_type = UIFieldType.PASSWORD)
    rhapi.fields.register_option(apikey_field, 'multigp_cred')

    rhapi.ui.register_quickbutton('multigp_cred', 'submit_apikey', 'Verify Credentials', RH.verify_creds)