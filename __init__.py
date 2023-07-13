import logging
import RHUtils
from RHUI import UIField, UIFieldType, UIFieldSelectOption
from plugins.multigp_interface.multigpAPI import multigpAPI

logger = logging.getLogger(__name__)

multigp = multigpAPI()

class RHmanager():

    _rhapi = None
    _multigp_cred_set = False
    _multigp_importer_set = False
    _multigp_exporter_set = False
    _pilot_import_set = False
    _races_set = False
    _class_import_set = False
    _race_class_set = False
    _push_results_set = False

    def __init__(self, rhapi):
        self._rhapi = rhapi

    def verify_creds(self, args):

        if self._multigp_cred_set is False:

            multigp.set_apiKey(self._rhapi.db.option('apiKey'))

            multigp.pull_chapter()
            chapter_name = multigp.get_chapterName()
            if chapter_name:
                self._rhapi.ui.message_notify("API key for " + chapter_name + " has been recognized")
            else:
                self._rhapi.ui.message_notify("API key can not be verified. Please check the entered key or your internet connection")
                return
            
            errors = multigp.set_sessionID(self._rhapi.db.option('mgp_username'), self._rhapi.db.option('mgp_password'))
            if errors:
                for error in errors:
                    self._rhapi.ui.message_notify(errors[error])
                return
            else: 
                userName = multigp.get_userName()
                self._rhapi.ui.message_notify(userName + " has been signed in for " + chapter_name + ". User will remained logged in until system reboot.")

            self._multigp_cred_set = True

            self.setup_import_menu()
            self._rhapi.ui.register_quickbutton('multigp_cred', 'multigp_exporter', 'Setup MultiGP Export Menu', self.setup_export_menu)
            self._rhapi.ui.message_notify("To ensure proper functionality, please setup the MultiGP Export Menu AFTER the event has been completed.")

    #
    # Setting up UI elements
    #

    def setup_import_menu(self):
        if self._multigp_importer_set is False:
            self._rhapi.ui.register_panel('multigp_import', 'Import from MultiGP', 'format', order=0)
            self.setup_race_selector()
            self.setup_import_buttons()
            
            self._multigp_importer_set = True

            self._rhapi.ui.message_notify("MultiGP import tools are now located under the Format tab.")

    def setup_export_menu(self, args):
        if self._multigp_exporter_set is False:
            self._rhapi.ui.register_panel('multigp_export', 'Export to MultiGP', 'format', order=1)
            self._multigp_exporter_set = True

    #
    # Import Event
    #

    # Race selector
    def setup_race_selector(self):
        if self._races_set is False:
            multigp.pull_races()
            race_list = []
            for race_label in multigp.get_races():
                race = UIFieldSelectOption(value = race_label, label = race_label)
                race_list.append(race)

            race_selector = UIField('race_select', 'Select Race', field_type = UIFieldType.SELECT, options = race_list)
            self._rhapi.fields.register_option(race_selector, 'multigp_import')
            self._races_set = True

    def setup_import_buttons(self):
        if self._pilot_import_set is False:
            self._rhapi.ui.register_quickbutton('multigp_import', 'import_pilots', 'Import Pilots', self.import_pilots)
            self._pilot_import_set = True
        if self._class_import_set is False:
            self._rhapi.ui.register_quickbutton('multigp_import', 'import_class', 'Import Race Class', self.import_class)
            self._pilot_import_set = True

    # Import pilots and set MultiGP PilotID
    def import_pilots(self, args):
        selected_race = self._rhapi.db.option('race_select')

        self._rhapi.ui.message_notify("Starting pilot import for " + selected_race)

        db_pilots = self._rhapi.db.pilots

        multigp.pull_race_data(selected_race)
        for mgp_pilot in multigp.get_pilots():

            db_match = None
            for db_pilot in db_pilots:
                    if db_pilot.callsign == mgp_pilot['userName']:
                        db_match = db_pilot
                        break

            mgp_pilot_name = mgp_pilot['firstName'] + " " + mgp_pilot['lastName']
            if db_match:
                db_pilot, _ = self._rhapi.db.pilot_alter(db_match.id, name = mgp_pilot_name)
            else:
                db_pilot = self._rhapi.db.pilot_add(name = mgp_pilot_name, callsign = mgp_pilot['userName'])

            self._rhapi.db.pilot_alter(db_pilot.id, attributes = {'multigp_id': mgp_pilot['pilotId']})

        self._rhapi.ui.message_notify("Pilots imported. Please refresh the page.")

    # Import Classes and events
    def import_class(self, args):
        selected_race = self._rhapi.db.option('race_select')

        self._rhapi.ui.message_notify("Starting class setup for " + selected_race)

        multigp.pull_race_data(selected_race)
        schedule = multigp.get_schedule()

        num_rounds = len(schedule['rounds'])

        race_class = self._rhapi.db.raceclass_add(name='MultiGP Class', rounds=num_rounds)

        for heat in schedule['rounds'][0]['heats']:
            heat_data = self._rhapi.db.heat_add(name=heat['name'], raceclass= race_class)

            # TODO: Populate pilots to each heat on correct frequency

    #
    # Export Results
    #

    # Select class for bracketed results
    def results_class_selector(self, args):

        if self._race_class_set is False:
            class_list = []
            for race_class in self._rhapi.db.raceclasses():
                classs = UIFieldSelectOption(value = race_class, label = race_class)
                class_list.append(classs)

        class_selector = UIField('class_select', 'Select Class with Final Results', field_type = UIFieldType.SELECT, options = class_list)
        self._rhapi.fields.register_option(class_selector, 'multigp_export')
        self._race_class_set = True

    # Slot & Score, Bracket Results, or Global Qualifier
    def push_type_selector(self):
        # TODO
        pass

    # Manual results push
    def push_results(self):
        # TODO
        pass

    # Finalize race results
    def finalize_results(self):
        # TODO
        pass


def initialize(rhapi):

    RH = RHmanager(rhapi)

    multigp_id = UIField(name = 'multigp_id', label = 'MultiGP Pilot ID', field_type = UIFieldType.TEXT)
    rhapi.fields.register_pilot_attribute(multigp_id)

    rhapi.ui.register_panel('multigp_cred', 'MultiGP Credentials', 'settings', order=0)

    apikey_field = UIField(name = 'apiKey', label = 'Chapter API Key', field_type = UIFieldType.TEXT)
    rhapi.fields.register_option(apikey_field, 'multigp_cred')

    username_field = UIField(name = 'mgp_username', label = 'MultiGP Username', field_type = UIFieldType.TEXT)
    rhapi.fields.register_option(username_field, 'multigp_cred')

    password_field = UIField(name = 'mgp_password', label = 'MultiGP Password', field_type = UIFieldType.TEXT)
    rhapi.fields.register_option(password_field, 'multigp_cred')

    rhapi.ui.register_quickbutton('multigp_cred', 'submit_apikey', 'Verify Credentials', RH.verify_creds)

    # TODO: sytem events
    # multigp.start_heat() on heat change