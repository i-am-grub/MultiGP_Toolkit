import RHUtils
from RHUI import UIField, UIFieldType, UIFieldSelectOption
import logging
from plugins.multigp_interface.multigpAPI import multigpAPI

logger = logging.getLogger(__name__)

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
    _pilot_bracket_push = False

    def __init__(self, rhapi):
        self._rhapi = rhapi
        self.multigp = multigpAPI()

    def verify_creds(self, args):

        if self._multigp_cred_set is False:

            self.multigp.set_apiKey(self._rhapi.db.option('apiKey'))

            self.multigp.pull_chapter()
            chapter_name = self.multigp.get_chapterName()
            if chapter_name:
                self._rhapi.ui.message_notify("API key for " + chapter_name + " has been recognized")
            else:
                self._rhapi.ui.message_notify("API key can not be verified. Please check the entered key or your internet connection")
                return
            
            errors = self.multigp.set_sessionID(self._rhapi.db.option('mgp_username'), self._rhapi.db.option('mgp_password'))
            if errors:
                for error in errors:
                    self._rhapi.ui.message_notify(errors[error])
                return
            else: 
                userName = self.multigp.get_userName()
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
            self.setup_race_selector('multigp_import', 'race_select')
            self.setup_import_buttons()
            
            self._multigp_importer_set = True

            self._rhapi.ui.message_notify("MultiGP import tools are now located under the Format tab.")

    def setup_export_menu(self, args):
        if self._multigp_exporter_set is False:
            self._rhapi.ui.register_panel('multigp_export', 'Export to MultiGP', 'format', order=1)

            self.setup_race_selector('multigp_export', 'race_select_export')
            self.results_class_selector()
            self.setup_export_buttons()

            self._multigp_exporter_set = True

            self._rhapi.ui.message_notify("MultiGP export tools are now located under the Format tab.")

    #
    # Import Event
    #

    # Race selector
    def setup_race_selector(self, ui_panel, name):
        if True: #self._races_set is False:
            self.multigp.pull_races()
            race_list = []
            for race_label in self.multigp.get_races():
                race = UIFieldSelectOption(value = race_label, label = race_label)
                race_list.append(race)

            race_selector = UIField(name, 'Select Race', field_type = UIFieldType.SELECT, options = race_list)
            self._rhapi.fields.register_option(race_selector, ui_panel)
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

        self.multigp.pull_race_data(selected_race)
        for mgp_pilot in self.multigp.get_pilots():

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

        self.multigp.pull_race_data(selected_race)
        schedule = self.multigp.get_schedule()

        num_rounds = len(schedule['rounds'])

        race_class = self._rhapi.db.raceclass_add(name='MultiGP Class', rounds=num_rounds)

        for heat in schedule['rounds'][0]['heats']:
            heat_data = self._rhapi.db.heat_add(name=heat['name'], raceclass= race_class)

            # TODO: Populate pilots to each heat on correct frequency

    #
    # Export Results
    #

    # Select class for bracketed results
    def results_class_selector(self):

        if self._race_class_set is False:
            class_list = []

            for event_class in self._rhapi.db.raceclasses:
                race_class = UIFieldSelectOption(value = event_class.id, label = event_class.name)
                class_list.append(race_class)

        class_selector = UIField('class_select', 'Select Class with Final Results', field_type = UIFieldType.SELECT, options = class_list)
        self._rhapi.fields.register_option(class_selector, 'multigp_export')

        self._race_class_set = True

    def setup_export_buttons(self):
        if self._pilot_bracket_push is False:
            self._rhapi.ui.register_quickbutton('multigp_export', 'push_bracket', 'Push Final Class Rankings', self.push_bracketed_results)
            self._pilot_import_set = True
        if self._finalize_button is False:
            self._rhapi.ui.register_quickbutton('multigp_export', 'finalize_results', 'Finalize MultiGP Event Results', self.finalize_results)
            self._pilot_import_set = True

    def push_bracketed_results(self, args):
        selected_class = self._rhapi.db.option('class_select')
        results_class = self._rhapi.db.raceclass_ranking(selected_class)
        results = []
        for pilot in results_class["ranking"]:
            multigp_id = int(self._rhapi.db.pilot_attribute_value(pilot['pilot_id'],'multigp_id'))
            class_position = (pilot['position'])
            result_dict = {"orderNumber" : class_position, "pilotId": multigp_id}
            results.append(result_dict)
            logger.info(result_dict)

        push_status =self.multigp.push_overall_race_results(self._rhapi.db.option('race_select_export'), results)
        logger.info(push_status)
        if push_status:
            self._rhapi.ui.message_notify("Results pushed to MultiGP")
        else:
            self._rhapi.ui.message_notify("Failed to push results to MultiGP")

    # Manual results push
    def push_results(self):
        # TODO
        pass

    # Finalize race results
    def finalize_results(self):
        push_status = self.multigp.finalize_results(self._rhapi.db.option('race_select_export'))
        logger.info(push_status)
        if push_status:
            self._rhapi.ui.message_notify("Results finalized on MultiGP")
        else:
            self._rhapi.ui.message_notify("Failed to finalize results on MultiGP")