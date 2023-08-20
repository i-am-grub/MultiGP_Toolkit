import logging
import RHUtils
from eventmanager import Evt
from RHUI import UIField, UIFieldType, UIFieldSelectOption
from plugins.multigp_interface.multigpAPI import multigpAPI

logger = logging.getLogger(__name__)

class RHmanager():

    _multigp_cred_set = False

    def __init__(self, rhapi):
        self._rhapi = rhapi
        self.multigp = multigpAPI()

    def verify_creds(self, args):

        if self._multigp_cred_set is False:

            self.multigp.set_apiKey(self._rhapi.db.option('apiKey'))

            if self.multigp.pull_chapter():
                chapter_name = self.multigp.get_chapterName()
                self._rhapi.ui.message_notify("API key for " + chapter_name   + " has been recognized")
            else:
                self._rhapi.ui.message_notify("API key cannot be verified. Please check the entered key or the RotorHazard system's internet connection")
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

            self.setup_plugin()
            self._rhapi.ui.message_notify("MultiGP tools are set up and are new assesible under their respective menus.")

    def setup_plugin(self):
        self._rhapi.events.on(Evt.LAPS_SAVE, self.auto_slot_score)
        self._rhapi.events.on(Evt.LAPS_RESAVE, self.auto_slot_score)

        self.setup_main_tools()
        self.setup_zippyq()

    def setup_main_tools(self):
        # Panel   
        self._rhapi.ui.register_panel('multigp_tools', 'MultiGP Tools', 'format', order=0)

        # Import Tools
        self.setup_race_selector('multigp_tools', 'race_select')
        self._rhapi.ui.register_quickbutton('multigp_tools', 'import_pilots', 'Import Pilots', self.import_pilots)
        self._rhapi.ui.register_quickbutton('multigp_tools', 'import_class', 'Import Race', self.import_class)

        # Export Tools
        self.results_class_selector()
        
        slot_score = UIField('slot_score', 'Automatically push heat results', field_type = UIFieldType.CHECKBOX)
        self._rhapi.fields.register_option(slot_score, 'multigp_tools')

        self._rhapi.ui.register_quickbutton('multigp_tools', 'push_results', 'Push Class Results', self.push_results)
        self._rhapi.ui.register_quickbutton('multigp_tools', 'push_bracket', 'Push Class Rankings', self.push_bracketed_rankings)
        self._rhapi.ui.register_quickbutton('multigp_tools', 'finalize_results', 'Finalize Event', self.finalize_results)

    def setup_zippyq(self):
        # Panel   
        self._rhapi.ui.register_panel('zippyq', 'ZippyQ', 'run', order=0)

    # Race selector
    def setup_race_selector(self, ui_panel, name):
        self.multigp.pull_races()
        race_list = []
        for race_label in self.multigp.get_races():
            race = UIFieldSelectOption(value = race_label, label = race_label)
            race_list.append(race)

        race_selector = UIField(name, 'MultiGP Event', field_type = UIFieldType.SELECT, options = race_list)
        self._rhapi.fields.register_option(race_selector, ui_panel)

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

        self._rhapi.ui.message_notify("Pilots imported. Please refresh the page for them to appear.")

    # Import classes from event
    def import_class(self, args):
        selected_race = self._rhapi.db.option('race_select')
        self._rhapi.ui.message_notify("Starting class setup for " + selected_race)
        
        self.multigp.pull_race_data(selected_race)
        schedule = self.multigp.get_schedule()
        num_rounds = len(schedule['rounds'])

        race_class = self._rhapi.db.raceclass_add(name=selected_race, rounds=num_rounds)
        db_pilots = self._rhapi.db.pilots
        slot_list = []
        for heat in schedule['rounds'][0]['heats']:
            heat_data = self._rhapi.db.heat_add(name=heat['name'], raceclass=race_class.id)
            rh_slots = self._rhapi.db.slots_by_heat(heat_data.id)
            
            for index, entry in enumerate(heat['entries']):
                db_match = None
                try:
                    for db_pilot in db_pilots:
                        if db_pilot.callsign == entry['userName']:
                            db_match = db_pilot
                            break
                except:
                    continue
                
                if db_match:
                    slot_list.append({'slot_id':rh_slots[index].id, 'pilot':db_match.id})
        
        self._rhapi.db.slots_alter_fast(slot_list)
        self._rhapi.ui.message_notify("Race class imported. Please refresh the page for it to appear.")

    # Select class for bracketed results
    def results_class_selector(self):
        class_list = []
        for event_class in self._rhapi.db.raceclasses:
            race_class = UIFieldSelectOption(value = event_class.id, label = event_class.name)
            class_list.append(race_class)

        class_selector = UIField('class_select', 'RH Event Class', field_type = UIFieldType.SELECT, options = class_list)
        self._rhapi.fields.register_option(class_selector, 'multigp_tools')

    # Slot and Score
    def slot_score(self, race_info, selected_race):
        for result in race_info.results["by_race_time"]:
            round = race_info.round_id
            heat = race_info.heat_id
            slot = result["node"]
            pilotID = self._rhapi.db.pilot_attribute_value(result["pilot_id"], 'multigp_id')
            pilot_score = result["points"]
            totalLaps = result["laps"]
            totalTime = result["total_time_raw"] * .001
            fastestLapTime = result["fastest_lap_raw"] * .001
            fastestConsecutiveLapsTime = result["consecutives_raw"] * .001
            consecutives_base = result["consecutives_base"]
                
            if not self.multigp.push_slot_and_score(selected_race, round, heat, slot, pilotID, 
                    pilot_score, totalLaps, totalTime, fastestLapTime, fastestConsecutiveLapsTime, consecutives_base):
                self._rhapi.ui.message_notify("Results push to MultiGP failed. Check the timer's internet connection.")

    # Automatially push results of heat
    def auto_slot_score(self, args):
        if self._rhapi.db.option('slot_score'):
            race_info = self._rhapi.db.race_by_id(args['race_id'])
            class_id = race_info.class_id
            selected_race = self._rhapi.db.raceclass_by_id(class_id).name
            self.slot_score(race_info, selected_race)            

    # Push class results
    def push_results(self, args):
        selected_race = self._rhapi.db.option('race_select')
        selected_class = self._rhapi.db.option('class_select')

        races = self._rhapi.db.races_by_raceclass(selected_class)
        for race_info in races:
            self.slot_score(race_info, selected_race)

        self._rhapi.ui.message_notify("Results pushed to MultiGP.")

    # Push class ranking
    def push_bracketed_rankings(self, args):
        selected_class = self._rhapi.db.option('class_select')
        results_class = self._rhapi.db.raceclass_ranking(selected_class)
        results = []
        for pilot in results_class["ranking"]:
            multigp_id = int(self._rhapi.db.pilot_attribute_value(pilot['pilot_id'],'multigp_id'))
            class_position = (pilot['position'])
            result_dict = {"orderNumber" : class_position, "pilotId": multigp_id}
            results.append(result_dict)
            logger.info(result_dict)

        push_status =self.multigp.push_overall_race_results(self._rhapi.db.option('race_select'), results)
        logger.info(push_status)
        if push_status:
            self._rhapi.ui.message_notify("Rankings pushed to MultiGP")
        else:
            self._rhapi.ui.message_notify("Failed to push rankings to MultiGP")

    # Finalize race results
    def finalize_results(self, args):
        push_status = self.multigp.finalize_results(self._rhapi.db.option('race_select'))
        logger.info(push_status)
        if push_status:
            self._rhapi.ui.message_notify("Results finalized on MultiGP")
        else:
            self._rhapi.ui.message_notify("Failed to finalize results on MultiGP")