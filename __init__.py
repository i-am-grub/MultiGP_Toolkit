import logging
import RHUtils
from RHUI import UIField, UIFieldType, UIFieldSelectOption
from plugins.MultiGP_Toolkit.RHmanager import RHmanager

logger = logging.getLogger(__name__)

def initialize(rhapi):

    RH = RHmanager(rhapi)

    multigp_id = UIField(name = 'multigp_id', label = 'MultiGP Pilot ID', field_type = UIFieldType.TEXT)
    rhapi.fields.register_pilot_attribute(multigp_id)

    rhapi.ui.register_panel('multigp_cred', 'MultiGP Credentials', 'settings', order=0)

    apikey_field = UIField(name = 'apiKey', label = 'Chapter API Key', field_type = UIFieldType.TEXT)
    rhapi.fields.register_option(apikey_field, 'multigp_cred')

    username_field = UIField(name = 'mgp_username', label = 'MultiGP Username', field_type = UIFieldType.TEXT)
    rhapi.fields.register_option(username_field, 'multigp_cred')

    password_field = UIField(name = 'mgp_password', label = 'MultiGP Password', field_type = UIFieldType.PASSWORD)
    rhapi.fields.register_option(password_field, 'multigp_cred')

    rhapi.ui.register_quickbutton('multigp_cred', 'submit_apikey', 'Verify Credentials', RH.verify_creds)