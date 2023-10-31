import logging
import RHUtils
import json
import requests
from eventmanager import Evt
from RHUI import UIField, UIFieldType, UIFieldSelectOption

logger = logging.getLogger(__name__)

def initialize(rhapi):

    RH = RHmanager(rhapi)

    multigp_id = UIField(name = 'multigp_id', label = 'MultiGP Pilot ID', field_type = UIFieldType.TEXT)
    rhapi.fields.register_pilot_attribute(multigp_id)

    rhapi.ui.register_panel('multigp_cred', 'MultiGP Credentials', 'settings', order=0)

    apikey_field = UIField(name = 'apiKey', label = 'Chapter API Key', field_type = UIFieldType.PASSWORD)
    rhapi.fields.register_option(apikey_field, 'multigp_cred')

    rhapi.ui.register_quickbutton('multigp_cred', 'submit_apikey', 'Verify Credentials', RH.verify_creds)

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
                message = "API key for " + chapter_name + " has been recognized"
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
        self.setup_main_tools()

    def auto_tools(self, args):
        self.auto_slot_score(args)
        self.auto_zippyq(args)

    def setup_main_tools(self):
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

        auto_zippy_text = self._rhapi.language.__('Automatically pull next ZippyQ round')
        auto_zippy = UIField('auto_zippy', auto_zippy_text, field_type = UIFieldType.CHECKBOX)
        self._rhapi.fields.register_option(auto_zippy, 'multigp_tools')

        zippyq_round_text = self._rhapi.language.__('ZippyQ round number')
        zippyq_round = UIField('zippyq_round', zippyq_round_text, field_type = UIFieldType.BASIC_INT, value = 1)
        self._rhapi.fields.register_option(zippyq_round, 'multigp_tools')

        self._rhapi.ui.register_quickbutton('multigp_tools', 'zippyq_import', 'Import ZippyQ Round', self.manual_zippyq)
        self._rhapi.ui.register_quickbutton('multigp_tools', 'push_results', 'Push Class Results', self.push_results)
        self._rhapi.ui.register_quickbutton('multigp_tools', 'push_bracket', 'Push Class Rankings', self.push_bracketed_rankings)     
        self._rhapi.ui.register_quickbutton('multigp_tools', 'finalize_results', 'Finalize Event', self.finalize_results)

    # Race selector
    def setup_race_selector(self, args = None):
        self.multigp.pull_races()
        race_list = [UIFieldSelectOption(value = None, label = "")]
        for race_label in self.multigp.get_races():
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

        self.multigp.pull_race_data(selected_race)
        schedule = self.multigp.get_schedule()

        info = """Note: Any race class with the Rounds field set to a value **less than 2** will have it's results pushed with the MultiGP round number set to the race's heat number, and the MultiGP heat set to 1. This special formating is required for ZippyQ results."""
        translated_info = self._rhapi.language.__(info)

        if self.multigp.get_disableSlotAutoPopulation() == "0":
            num_rounds = len(schedule['rounds'])
            heat_advance_type = 1

            race_class = self._rhapi.db.raceclass_add(name=selected_race, description=translated_info, rounds=num_rounds, heat_advance_type=heat_advance_type)
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
            
        else:
            num_rounds = 1
            heat_advance_type = 0
            race_class = self._rhapi.db.raceclass_add(name=selected_race, description=translated_info, rounds=num_rounds, heat_advance_type=heat_advance_type)

        self._rhapi.ui.broadcast_raceclasses()
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
        self.multigp.pull_additional_rounds(selected_race, heat_num)
        data = self.multigp.get_round()
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
    def auto_zippyq(self, args): 
        if self._rhapi.db.option('auto_zippy') == "1":

            message = "Automatically downloading next ZippyQ round..."
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))

            race_info = self._rhapi.db.race_by_id(args['race_id'])
            class_id = race_info.class_id
            selected_race = self._rhapi.db.raceclass_by_id(class_id).name
            next_round = race_info.heat_id + 1

            self.zippyq(class_id, selected_race, next_round)

    # Slot and Score
    def slot_score(self, race_info, selected_race):
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
            slot = result["node"] + 1
            pilotID = self._rhapi.db.pilot_attribute_value(result["pilot_id"], 'multigp_id')
            pilot_score = result["points"]
            totalLaps = result["laps"]
            totalTime = result["total_time_raw"] * .001
            fastestLapTime = result["fastest_lap_raw"] * .001
            fastestConsecutiveLapsTime = result["consecutives_raw"] * .001
            consecutives_base = result["consecutives_base"]

            if num_rounds < 2:
                round = race_info.heat_id
                heat = 1
            elif self.override_round_heat:
                round = self.custom_round_number
                heat = self.custom_heat_number
            else:
                round = race_info.round_id
                heat = race_info.heat_id

            self.round_pilots.append(result["pilot_id"])
                
            if not self.multigp.push_slot_and_score(selected_race, round, heat, slot, pilotID, 
                    pilot_score, totalLaps, totalTime, fastestLapTime, fastestConsecutiveLapsTime, consecutives_base):
                message = "Results push to MultiGP FAILED. Check the timer's internet connection."
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                return False
        else:
            self.custom_heat_number += 1
            return True

    # Automatially push results of ZippyQ heat
    def auto_slot_score(self, args):

        race_info = self._rhapi.db.race_by_id(args['race_id'])
        class_id = race_info.class_id
        selected_race = self._rhapi.db.raceclass_by_id(class_id).name
        num_rounds = self._rhapi.db.raceclass_by_id(class_id).rounds

        if self._rhapi.db.option('auto_slot_score') == "1" and num_rounds < 2:

            message = "Automatically uploading results..."
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))

            if self.slot_score(race_info, selected_race):
                message = "Results successfully pushed to MultiGP."
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))

    # Push class results
    def push_results(self, args):

        selected_race = self._rhapi.db.option('race_select')
        selected_class = self._rhapi.db.option('class_select')
        
        self.custom_round_number = 1
        self.custom_heat_number = 1
        self.override_round_heat = False
        self.round_pilots = []

        if not selected_race or not selected_class:
            message = "Select a RH Class to pull results from and a MultiGP Race to send results to"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return
        else:
            message = "Starting to push results to MultiGP..."
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))

        races = self._rhapi.db.races_by_raceclass(selected_class)

        temp_list = []
        for race_info in races:
            temp_list.append(race_info.id)
            if not self.slot_score(race_info, selected_race):
                return
            
        logger.info(temp_list)

        message = "Results successfully pushed to MultiGP."
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))

    # Push class ranking
    def push_bracketed_rankings(self, args):
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
    def finalize_results(self, args):
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


class multigpAPI():
    
    # https://www.multigp.com/apidocumentation/
    _apiKey = None
    _sessionID = None
    _userName = None
    _chapterId = None
    _chapterName = None
    _avaliable_events = []
    _events_keys = {}
    _race_name = None
    _race_description = None
    _race_pilots = []
    _scoringFormat = None
    _schedule = {}
    _disableSlotAutoPopulation = None
    _round_data = {}

    def _request_and_download(self, url, json_request):
        header = {'Content-type': 'application/json'}
        response = requests.post(url, headers=header, data=json_request, timeout=5)

        try:
            returned_json = json.loads(response.text)
        except:
            returned_json = {'status' : False}
        finally:
            return returned_json
        
    #
    # API Setup
    #

    def set_apiKey(self, apiKey:str):
        self._apiKey = apiKey
        
    def pull_chapter(self):
        url = 'https://www.multigp.com/mgp/multigpwebservice/chapter/findChapterFromApiKey'
        data = {
            'apiKey' : self._apiKey
        }
        json_request = json.dumps(data)
        returned_json = self._request_and_download(url, json_request)

        if returned_json['status']:
            self._chapterId = returned_json['chapterId']
            self._chapterName = returned_json['chapterName']
            logger.info(self._chapterName)

        return returned_json['status']

    def get_chapterName(self):
        return self._chapterName

    def set_sessionID(self, username:str, password:str):
        url = 'https://www.multigp.com/mgp/multigpwebservice/user/login'
        data = {
            'username' : username,
            'password' : password,
            'apiKey' : self._apiKey
        }
        json_request = json.dumps(data)
        returned_json = self._request_and_download(url, json_request)

        if returned_json['status']:
            self._sessionID = returned_json['sessionId']
            self._userName = returned_json['data']['userName']
            return None
        else:
            return returned_json['errors']
    
    def get_userName(self):
        return self._userName

    #
    # Data from MultiGP
    #

    def pull_races(self):

        url = 'https://www.multigp.com/mgp/multigpwebservice/race/listForChapter?chapterId=' + self._chapterId
        data = {
            'apiKey' : self._apiKey
        }
        json_request = json.dumps(data)
        returned_json = self._request_and_download(url, json_request)

        if returned_json['status']:
            self._avaliable_events = []
            self._events_keys = {}

            for race in returned_json['data']:
                self._avaliable_events.append(race['name'])
                self._events_keys[race['name']] = race['id']

        return returned_json['status']
        
    def get_races(self):
        return self._avaliable_events
    
    def pull_race_data(self, selected_race:str):

        url = 'https://www.multigp.com/mgp/multigpwebservice/race/view?id=' + self._events_keys[selected_race]
        data = {
            'apiKey' : self._apiKey
        }
        json_request = json.dumps(data)
        returned_json = self._request_and_download(url, json_request)

        if returned_json['status']:
            self._race_name = returned_json['data']['name']
            self._race_description = returned_json['data']['description']
            self._scoringFormat = returned_json['data']['scoringFormat']
            self._race_pilots = returned_json['data']['entries']
            self._schedule = returned_json['data']['schedule']
            self._disableSlotAutoPopulation = returned_json['data']['disableSlotAutoPopulation']

        return returned_json['status']
    
    def get_scoringformat(self):
        return self._scoringFormat
    
    def get_disableSlotAutoPopulation(self):
        return self._disableSlotAutoPopulation
    
    def get_pilots(self):
        return self._race_pilots
    
    def get_schedule(self):
        return self._schedule

    def pull_additional_rounds(self, selected_race:str, round:int):
        url = 'https://www.multigp.com/mgp/multigpwebservice/race/getAdditionalRounds?id=' + self._events_keys[selected_race] + '&startFromRound=' + str(round)
        data = {
            'apiKey' : self._apiKey
        }
        json_request = json.dumps(data)
        returned_json = self._request_and_download(url, json_request)

        if returned_json['status']:
            self._round_data = returned_json['data']

        return returned_json['status']
    
    def get_round(self):
        return self._round_data

    #
    # Data to MultiGP
    #

    # Capture pilots times and scores
    def push_slot_and_score(self, selected_race:str, round:int, heat:int, slot:int, pilotID:int, pilot_score:int,
                            totalLaps:int, totalTime:float, fastestLapTime:float, fastestConsecutiveLapsTime:float, consecutives_base:int):

        url = 'https://www.multigp.com/mgp/multigpwebservice/race/assignslot/id/' + self._events_keys[selected_race] + '/cycle/' + str(round) + '/heat/' + str(heat) + '/slot/' + str(slot)
        data = {
            'data' : {
                'pilotId' : pilotID,
                'score' : pilot_score,
                'totalLaps' : totalLaps,
                'totalTime' : totalTime,
                'fastestLapTime' : fastestLapTime,
            },
            #'sessionId' : self._sessionID,
            'apiKey' : self._apiKey
        }
        if consecutives_base == 3:
            data['data']['fastest3ConsecutiveLapsTime'] = fastestConsecutiveLapsTime
        elif consecutives_base == 2:
            data['data']['fastest2ConsecutiveLapsTime'] = fastestConsecutiveLapsTime

        json_request = json.dumps(data)
        returned_json = self._request_and_download(url, json_request)

        return returned_json['status']

    # Final results from brackets
    def push_overall_race_results(self, selected_race:str, bracket_results:list):

        url = 'https://www.multigp.com/mgp/multigpwebservice/race/captureOverallRaceResult?id=' + self._events_keys[selected_race]
        data = {
            'data' : {
                'raceId' : self._events_keys[selected_race],
                'bracketResults' : bracket_results 
                    # [
                        # { orderNumber : Number, // the finish order for this pilot
                        # pilotId: Number // the specified pilot
                        # },
                    # ]
            },
            'apiKey' : self._apiKey
        }
        json_request = json.dumps(data)
        returned_json = self._request_and_download(url, json_request)

        return returned_json['status']
    
    def finalize_results(self, selected_race:str):

        url = 'https://www.multigp.com/mgp/multigpwebservice/race/finalize?id=' + self._events_keys[selected_race]
        data = {
            #'sessionId' : self._sessionID,
            'apiKey' : self._apiKey
        }
        json_request = json.dumps(data)
        returned_json = self._request_and_download(url, json_request)

        return returned_json['status']
