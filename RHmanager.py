import logging
from dataclasses import dataclass
from eventmanager import Evt
from RHUI import UIField, UIFieldType, UIFieldSelectOption
from RHRace import WinCondition, StartBehavior

from plugins.MultiGP_Toolkit.multigpAPI import multigpAPI
from plugins.MultiGP_Toolkit.miniFPVscores import getURLfromFPVS, uploadToFPVS, runClearFPVS

logger = logging.getLogger(__name__)

@dataclass
class race_format():
    name: str
    win_condition: WinCondition

class RHmanager():

    _multigp_cred_set = False

    def __init__(self, rhapi):
        self._rhapi = rhapi
        self.multigp = multigpAPI()

    def verify_creds(self, args):

        if self._multigp_cred_set is False:

            self.multigp.set_apiKey(self._rhapi.db.option('apiKey'))

            chapter_name = self.multigp.pull_chapter()
            if chapter_name:
                message = f"API key for {chapter_name} has been recognized"
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            else:
                message = "API key cannot be verified. Please check the entered key or the RotorHazard system's internet connection"
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                return

            self._multigp_cred_set = True

            self.setup_plugin()
            message = "MultiGP tools can now be accessed under the Format tab."
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))

    def setup_plugin(self):
        self._rhapi.events.on(Evt.LAPS_SAVE, self.auto_tools)
        self._rhapi.events.on(Evt.LAPS_RESAVE, self.auto_slot_score)
        self._rhapi.events.on(Evt.CLASS_ADD, self.results_class_selector)
        self._rhapi.events.on(Evt.CLASS_DUPLICATE, self.results_class_selector)
        self._rhapi.events.on(Evt.CLASS_ALTER, self.results_class_selector)
        self._rhapi.events.on(Evt.CLASS_DELETE, self.results_class_selector)

        # Panel   
        self._rhapi.ui.register_panel('multigp_tools', 'MultiGP Tools', 'format', order=0)

        # Import Tools
        self.setup_race_selector()
        self._rhapi.ui.register_quickbutton('multigp_tools', 'refresh_events', 'Refresh MultiGP Races', self.setup_race_selector)
        self._rhapi.ui.register_quickbutton('multigp_tools', 'import_pilots', 'Import Pilots', self.import_pilots)
        self._rhapi.ui.register_quickbutton('multigp_tools', 'import_class', 'Import Race', self.import_class)
        
        # Export Tools
        self.results_class_selector()

        auto_slot_score_text = self._rhapi.language.__('Automatically push ZippyQ race results')
        auto_slot_score = UIField('auto_slot_score', auto_slot_score_text, field_type = UIFieldType.CHECKBOX)
        self._rhapi.fields.register_option(auto_slot_score, 'multigp_tools')

        auto_zippy_text = self._rhapi.language.__('Automatically setup next ZippyQ round')
        auto_zippy = UIField('auto_zippy', auto_zippy_text, field_type = UIFieldType.CHECKBOX)
        self._rhapi.fields.register_option(auto_zippy, 'multigp_tools')

        zippyq_round_text = self._rhapi.language.__('ZippyQ round number')
        zippyq_round = UIField('zippyq_round', zippyq_round_text, field_type = UIFieldType.BASIC_INT, value = 1)
        self._rhapi.fields.register_option(zippyq_round, 'multigp_tools')

        zippyq_round_text = self._rhapi.language.__('FPVScores Event UUID')
        fpv_scores = UIField('event_uuid', zippyq_round_text, UIFieldType.TEXT)
        self._rhapi.fields.register_option(fpv_scores, 'multigp_tools')

        self._rhapi.ui.register_quickbutton('multigp_tools', 'zippyq_import', 'Import ZippyQ Round', self.manual_zippyq)
        self._rhapi.ui.register_quickbutton('multigp_tools', 'push_results', 'Push Class Results', self.push_results)
        self._rhapi.ui.register_quickbutton('multigp_tools', 'push_bracket', 'Push Class Rankings', self.push_bracketed_rankings)     
        self._rhapi.ui.register_quickbutton('multigp_tools', 'finalize_results', 'Finalize Event', self.finalize_results)
        self._rhapi.ui.register_quickbutton('multigp_tools', 'fpvscores_upload', 'Upload FPVScores Data', uploadToFPVS, self._rhapi)
        self._rhapi.ui.register_quickbutton('multigp_tools', 'fpvscores_clear', 'Clear FPVScores Data', runClearFPVS, self._rhapi)

    # Automatic ZippyQ tools
    def auto_tools(self, args):
        race_info = self._rhapi.db.race_by_id(args['race_id'])

        # Verify the rounds meet ZippyQ criteria
        if self._rhapi.db.raceclass_by_id(race_info.class_id).rounds <= 1: 
            self.auto_slot_score(race_info, args)
            self.auto_zippyq(race_info, args)

    # Race selector
    def setup_race_selector(self, args = None):
        races = self.multigp.pull_races()
        race_list = [UIFieldSelectOption(value = None, label = "")]
        for race_label in races:
            race = UIFieldSelectOption(value = race_label, label = race_label)
            race_list.append(race)

        race_selector = UIField('race_select', 'MultiGP Race', field_type = UIFieldType.SELECT, options = race_list)
        self._rhapi.fields.register_option(race_selector, 'multigp_tools')

        self._rhapi.ui.broadcast_ui('format')

    # Import pilots and set MultiGP PilotID
    def import_pilots(self, args):
        selected_race = self._rhapi.db.option('race_select')
        if not selected_race:
            message = "Select a MultiGP Race to import pilots from"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return
        db_pilots = self._rhapi.db.pilots
        race_data = self.multigp.pull_race_data(selected_race)

        for mgp_pilot in race_data['entries']:
            mgp_pilot_name = f"{mgp_pilot['firstName']} {mgp_pilot['lastName']}"

            for db_pilot in db_pilots:
                if db_pilot.callsign == mgp_pilot['userName']:
                    db_pilot, _ = self._rhapi.db.pilot_alter(db_pilot.id, name = mgp_pilot_name)
                    break
            else:
                db_pilot = self._rhapi.db.pilot_add(name = mgp_pilot_name, callsign = mgp_pilot['userName'])

            self._rhapi.db.pilot_alter(db_pilot.id, attributes = {'multigp_id': mgp_pilot['pilotId']})

        self._rhapi.ui.broadcast_pilots()
        message = "Pilots imported"
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))

    # Import classes from event
    def import_class(self, args):
        selected_race = self._rhapi.db.option('race_select')
        if not selected_race:
            message = "Select a MultiGP Race to import"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return

        try:
            race_data = self.multigp.pull_race_data(selected_race)
        except:
            message = "Failed to import race. On MultiGP, make sure your heats are generated or change the event to use ZippyQ."
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return

        schedule = race_data['schedule']
        MGP_format = race_data['scoringFormat']
        race_description = race_data['description']

        if MGP_format == '0':
            set_format = race_format('MGP: Aggregate Laps', WinCondition.MOST_PROGRESS)
        elif MGP_format == '1':
            set_format = race_format('MGP: Fastest Lap', WinCondition.FASTEST_LAP)
        else:
            set_format = race_format('MGP: Fastest Consecutive Laps', WinCondition.FASTEST_CONSECUTIVE)

        # Register Race Formats
        rh_formats = self._rhapi.db.raceformats
        for rh_format in rh_formats:
            if rh_format.name == set_format.name:
                format_id = rh_format.id
                break
        else:
            format_id = self._rhapi.db.raceformat_add(name=set_format.name, win_condition=set_format.win_condition, 
                                    race_time_sec = 120, staging_fixed_tones = 3, start_behavior=StartBehavior.HOLESHOT)
            
        # Adjust points for format
        if race_data['scoringDisabled'] == "0":
            self._rhapi.db.raceformat_alter(format_id, points_method="Position", points_settings={"points_list": "10,6,4,2,1,0"})
        else:
            self._rhapi.db.raceformat_alter(format_id, points_method="Position", points_settings={"points_list": "0,0,0,0,0,0"})

        # Import Class
        if race_data['disableSlotAutoPopulation'] == "0":
            num_rounds = len(schedule['rounds'])
            heat_advance_type = 1

            race_class = self._rhapi.db.raceclass_add(name=selected_race, raceformat=format_id, description=race_description, rounds=num_rounds, heat_advance_type=heat_advance_type)
            db_pilots = self._rhapi.db.pilots
            slot_list = []
            for heat in schedule['rounds'][0]['heats']:
                heat_data = self._rhapi.db.heat_add(name=heat['name'], raceclass=race_class.id)
                rh_slots = self._rhapi.db.slots_by_heat(heat_data.id)
                
                for index, entry in enumerate(heat['entries']):
                    if 'pilotId' in entry:
                        mgp_pilot_name = entry['firstName'] + " " + entry['lastName']
                        for db_pilot in db_pilots:
                            if db_pilot.callsign == entry['userName']:
                                break
                        else:
                            db_pilot = self._rhapi.db.pilot_add(name = mgp_pilot_name, callsign = entry['userName'])

                        self._rhapi.db.pilot_alter(db_pilot.id, attributes = {'multigp_id': entry['pilotId']})
                        slot_list.append({'slot_id':rh_slots[index].id, 'pilot':db_pilot.id})
                    else:
                        continue
            
            self._rhapi.db.slots_alter_fast(slot_list)
            
        else:
            num_rounds = 0
            heat_advance_type = 0
            race_class = self._rhapi.db.raceclass_add(name=selected_race, raceformat=format_id, description=race_description, rounds=num_rounds, heat_advance_type=heat_advance_type)

        self._rhapi.ui.broadcast_raceclasses()
        self._rhapi.ui.broadcast_raceformats()
        self._rhapi.ui.broadcast_pilots()
        self._rhapi.ui.broadcast_ui('format')
        message = "Race class imported."
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))

    # Setup RH Class selector
    def results_class_selector(self, args = None):
        class_list = [UIFieldSelectOption(value = None, label = "")]
        
        for event_class in self._rhapi.db.raceclasses:
            race_class = UIFieldSelectOption(value = event_class.id, label = event_class.name)
            class_list.append(race_class)
        
        class_selector = UIField('class_select', 'RotorHazard Class', field_type = UIFieldType.SELECT, options = class_list)
        self._rhapi.fields.register_option(class_selector, 'multigp_tools')

        self._rhapi.ui.broadcast_ui('format')

    # Configure ZippyQ round
    def zippyq(self, raceclass_id, selected_race, heat_num):
        data = self.multigp.pull_additional_rounds(selected_race, heat_num)
        db_pilots = self._rhapi.db.pilots

        try:
            heat_name = data['rounds'][0]['name']
        except:
            message = "ZippyQ round doesn't exist"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return

        slot_list = []
        for heat in data['rounds'][0]['heats']:
            heat_data = self._rhapi.db.heat_add(name=heat_name, raceclass=raceclass_id)
            rh_slots = self._rhapi.db.slots_by_heat(heat_data.id)
            
            for index, entry in enumerate(heat['entries']):
                db_match = None
                try:
                    for db_pilot in db_pilots:
                        if db_pilot.callsign == entry['userName']:
                            db_match = db_pilot
                            break

                    if db_match:
                        slot_list.append({'slot_id':rh_slots[index].id, 'pilot':db_match.id})
                    else:
                        mgp_pilot_name = entry['firstName'] + " " + entry['lastName']
                        db_pilot = self._rhapi.db.pilot_add(name = mgp_pilot_name, callsign = entry['userName'])
                        self._rhapi.db.pilot_alter(db_pilot.id, attributes = {'multigp_id': entry['pilotId']})
                        slot_list.append({'slot_id':rh_slots[index].id, 'pilot':db_pilot.id})
                except:
                    continue
        
        self._rhapi.db.slots_alter_fast(slot_list)
        self._rhapi.ui.broadcast_pilots()
        self._rhapi.ui.broadcast_heats()
        message = "ZippyQ round imported."
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))

        return heat_data

    # Manually trigger ZippyQ round configuration
    def manual_zippyq(self, args):
        selected_race = self._rhapi.db.option('race_select')
        selected_class = self._rhapi.db.option('class_select')
        if not selected_race or not selected_class:
            message = "Select a MultiGP Race to import round from and a RH Class to add the round to"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return
        
        self.zippyq(selected_class, selected_race, self._rhapi.db.option('zippyq_round'))

    # Automatically trigger next ZippyQ round configuration
    def auto_zippyq(self, race_info, args): 

        if self._rhapi.db.option('auto_zippy') == "1":

            message = "Automatically downloading next ZippyQ round..."
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            
            class_id = race_info.class_id
            selected_race = self._rhapi.db.raceclass_by_id(class_id).name
            next_round = race_info.heat_id + 1

            heat_data = self.zippyq(class_id, selected_race, next_round)
            data = {}
            data['heat'] = heat_data.id
            self._rhapi.race._heat_set(data)

    # Slot and Score
    def slot_score(self, race_info, selected_race, eventURL = None):
        num_rounds = self._rhapi.db.raceclass_by_id(race_info.class_id).rounds
        results = self._rhapi.db.race_results(race_info.id)["by_race_time"]

        if num_rounds >= 2:
            for result in results:
                if self.custom_round_number < race_info.round_id:
                    self.custom_round_number = race_info.round_id
                    self.round_pilots = []

                if result["pilot_id"] in self.round_pilots:
                    self.override_round_heat = True
                    self.custom_round_number += 1
                    self.custom_heat_number = 1
                    self.round_pilots = []

        for result in results:

            if num_rounds <= 1:
                round = race_info.heat_id
                heat = 1
            elif self.override_round_heat:
                round = self.custom_round_number
                heat = self.custom_heat_number
            else:
                round = race_info.round_id
                heat = race_info.heat_id
            slot = result["node"] + 1

            race_data = {}
            race_data['pilotId'] = self._rhapi.db.pilot_attribute_value(result["pilot_id"], 'multigp_id')
            race_data['score'] = result["points"]
            race_data['totalLaps'] = result["laps"]
            race_data['totalTime'] = result["total_time_raw"] * .001
            race_data['fastestLapTime'] = result["fastest_lap_raw"] * .001

            if result["consecutives_base"] == 3:
                race_data['fastest3ConsecutiveLapsTime'] = result["consecutives_raw"] * .001
            elif result["consecutives_base"] == 2:
                race_data['fastest2ConsecutiveLapsTime'] = result["consecutives_raw"] * .001

            if eventURL:
                race_data['liveTimeEventUrl'] = eventURL

            self.round_pilots.append(result["pilot_id"])
                
            if not self.multigp.push_slot_and_score(selected_race, round, heat, slot, race_data):
                message = "Results push to MultiGP FAILED. Check the timer's internet connection."
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                return False
        else:
            self.custom_heat_number += 1
            return True

    # Automatially push results of ZippyQ heat
    def auto_slot_score(self, race_info, _args):

        self.override_round_heat = False
        self.round_pilots = []
        self.custom_round_number = 1
        self.custom_heat_number = 1

        class_id = race_info.class_id
        selected_race = self._rhapi.db.raceclass_by_id(class_id).name

        if self._rhapi.db.option('auto_slot_score') == "1":

            message = "Automatically uploading results..."
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))

            if self.slot_score(race_info, selected_race):
                message = "Results successfully pushed to MultiGP."
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))

    # Push class results
    def push_results(self, _args):

        def sort_by_id(race_info):
            return race_info.id

        eventURL = None
        FPSeventURL = getURLfromFPVS(self._rhapi)
        if FPSeventURL:
            eventURL = FPSeventURL

        selected_race = self._rhapi.db.option('race_select')
        selected_class = self._rhapi.db.option('class_select')
        
        self.override_round_heat = False
        self.round_pilots = []
        self.custom_round_number = 1
        self.custom_heat_number = 1

        if not selected_race or not selected_class:
            message = "Select a RH Class to pull results from and a MultiGP Race to send results to"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return
        else:
            message = "Starting to push results to MultiGP..."
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))

        races = self._rhapi.db.races_by_raceclass(selected_class)
        races.sort(key=sort_by_id)

        for race_info in races:
            if not self.slot_score(race_info, selected_race, eventURL):
                return

        message = "Results successfully pushed to MultiGP."
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))

    # Push class ranking
    def push_bracketed_rankings(self, _args):
        selected_race = self._rhapi.db.option('race_select')
        selected_class = self._rhapi.db.option('class_select')
        if not selected_race or not selected_class:
            message = "Select a RH Class to pull rankings from and a MultiGP Race to send rankings to"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return

        results_class = self._rhapi.db.raceclass_ranking(selected_class)
        results = []
        for pilot in results_class["ranking"]:
            multigp_id = int(self._rhapi.db.pilot_attribute_value(pilot['pilot_id'], 'multigp_id'))
            class_position = (pilot['position'])
            result_dict = {"orderNumber" : class_position, "pilotId" : multigp_id}
            results.append(result_dict)

        push_status = self.multigp.push_overall_race_results(selected_race, results)
        if push_status:
            message = "Rankings pushed to MultiGP"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
        else:
            message = "Failed to push rankings to MultiGP"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))

    # Finalize race results
    def finalize_results(self, _args):
        selected_race = self._rhapi.db.option('race_select')
        if not selected_race:
            message = "Select a MultiGP Race to finalize"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return

        push_status = self.multigp.finalize_results(selected_race)
        if push_status:
            message = "Results finalized on MultiGP"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
        else:
            message = "Failed to finalize results on MultiGP"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))