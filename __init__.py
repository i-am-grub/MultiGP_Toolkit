import logging
from RHUI import UIField, UIFieldType
from plugins.MultiGP_Toolkit.RHmanager import RHmanager

logger = logging.getLogger(__name__)

PLUGIN_VERSION = 'v1.2.0'

def initialize(rhapi):

    logger.info(PLUGIN_VERSION)

    RH = RHmanager(rhapi)

    multigp_id = UIField(name = 'multigp_id', label = 'MultiGP Pilot ID', field_type = UIFieldType.TEXT)
    rhapi.fields.register_pilot_attribute(multigp_id)

    rhapi.ui.register_panel('multigp_cred', 'MultiGP Credentials', 'settings')

    apikey_field = UIField(name = 'apiKey', label = 'Chapter API Key', field_type = UIFieldType.PASSWORD)
    rhapi.fields.register_option(apikey_field, 'multigp_cred')

    rhapi.ui.register_quickbutton('multigp_cred', 'submit_apikey', 'Verify Credentials', RH.verify_creds)