import sys
import logging
import json
import requests
from dataclasses import dataclass
from eventmanager import Evt
from enum import Enum

from Database import HeatAdvanceType
from RHRace import WinCondition, StartBehavior
from RHUI import UIField, UIFieldType

from plugins.MultiGP_Toolkit.multigpAPI import multigpAPI
from plugins.MultiGP_Toolkit.UImanager import UImanager
import plugins.MultiGP_Toolkit.miniFPVscores as miniFPVscores

if sys.version_info.minor == 12:
    import plugins.MultiGP_Toolkit.systemVerification.py312 as systemVerification
elif sys.version_info.minor == 11:
    import plugins.MultiGP_Toolkit.systemVerification.py311 as systemVerification
elif sys.version_info.minor == 10:
    import plugins.MultiGP_Toolkit.systemVerification.py310 as systemVerification
elif sys.version_info.minor == 9:
    import plugins.MultiGP_Toolkit.systemVerification.py39 as systemVerification
elif sys.version_info.minor == 8:
    import plugins.MultiGP_Toolkit.systemVerification.py38 as systemVerification

logger = logging.getLogger(__name__)

@dataclass
class race_format():
    name: str
    win_condition: WinCondition
    race_time_sec: int = 120
    unlimited_time: bool = False
    start_behavior: StartBehavior = StartBehavior.HOLESHOT
    team_racing_mode: bool = False
    mgp_gq: bool = False

class mgp_formats(Enum):
    AGGREGATE = race_format('MGP: Aggregate Laps', WinCondition.MOST_PROGRESS)
    FASTEST = race_format('MGP: Fastest Lap', WinCondition.FASTEST_LAP)
    CONSECUTIVE = race_format('MGP: Fastest Consecutive Laps', WinCondition.FASTEST_CONSECUTIVE)
    GLOBAL = race_format("2024 MGP Global Qualifier", WinCondition.FASTEST_CONSECUTIVE, mgp_gq=True)

class RHmanager(UImanager):

    _multigp_cred_set = False
    _mgp_races = {}
    _system_verification = systemVerification.systemVerification()
    _pilot_urls = False

    def __init__(self, rhapi):
        self._rhapi = rhapi
        self.multigp = multigpAPI()
        self.FPVscores_installed = 'plugins.fpvscores' in sys.modules

        self._rhapi.events.on(Evt.STARTUP, self.startup, name='startup')
        self._rhapi.events.on(Evt.DATA_EXPORT_INITIALIZE, miniFPVscores.register_handlers)
        self._rhapi.events.on(Evt.RACE_STAGE, self.verify_race, name='verify_race')
        self._rhapi.events.on(Evt.CLASS_ALTER, self.verify_class, name='verify_class')
        self._rhapi.events.on(Evt.RACE_FORMAT_ALTER, self.verify_format, name='verify_format')
        self._rhapi.events.on(Evt.RACE_FORMAT_DELETE, self.verify_classes, name='verify_classes')
        self._rhapi.events.on(Evt.DATABASE_RESET, self.reset_event_metadata, name='reset_event_metadata')
        self._rhapi.events.on(Evt.DATABASE_RECOVER, self.update_panels, name='update_panels')
        self._rhapi.events.on(Evt.LAPS_SAVE, self.generate_pilot_list, name='generate_pilot_list')

    def startup(self, _args):
        if self._rhapi.db.option('store_pilot_url') ==  "1":
            self._pilot_urls = True
            pilotPhotoUrl = UIField(name = "PilotDetailPhotoURL", label = "Pilot Photo URL", field_type = UIFieldType.TEXT)
            self._rhapi.fields.register_pilot_attribute(pilotPhotoUrl)

        self.verify_creds()

    #
    # Event Metadata Management    
    #

    def clear_uuid(self, _args = None):
        self._rhapi.db.option_set('event_uuid', '')

    def reset_event_metadata(self, _args = None):
        self._rhapi.db.option_set('event_uuid', '')
        self._rhapi.db.option_set('mgp_race_id', '')
        self._rhapi.db.option_set('zippyq_races', 0)
        self._rhapi.db.option_set('global_qualifer_event', '0')
        self.clear_multi_class_selector()
        self._rhapi.db.option_set('mgp_event_races', '[]')
        self._rhapi.db.option_set('results_select', '')
        self._rhapi.db.option_set('ranks_select', '')
        self.update_panels()

    def set_frequency_profile(self, args):
        fprofile_id = self._rhapi.db.heat_attribute_value(args['heat_id'], 'heat_profile_id')
        if fprofile_id:
            self._rhapi.race.frequencyset = fprofile_id
            self._rhapi.ui.broadcast_frequencies()

    def generate_pilot_list(self, args = None):
        race_info = self._rhapi.db.race_by_id(args['race_id'])
        heat_info = self._rhapi.db.heat_by_id(race_info.heat_id)
        
        race_pilots = {}
        for slot in self._rhapi.db.slots_by_heat(heat_info.id):
            if slot.pilot_id == 0:
                continue
            else:
                race_pilots[slot.pilot_id] = slot.node_index

        self._rhapi.db.race_alter(race_info.id, attributes={'race_pilots' : json.dumps(race_pilots)})

    #
    # Helpers
    #

    def _get_MGPpilotID(self, pilot_id):
        entry = self._rhapi.db.pilot_attribute_value(pilot_id, 'mgp_pilot_id')
        if entry:
            return entry.strip()
        else:
            return None

    #
    # Chapter API Key Verification
    #

    def verify_creds(self):

        key = self._rhapi.db.option('mgp_api_key')
        if key:
            self.multigp.set_apiKey(key)
        else:
            return

        self._chapter_name = self.multigp.pull_chapter()

        if self._chapter_name:
            logger.info(f"API key for {self._chapter_name} has been recognized")
        else:
            logger.info(f"MultiGP API key cannot be verified.")
            return
        
        self.setup_plugin()

    #
    # Setup Plugin's Online Tools
    #

    def setup_plugin(self):
        self._rhapi.events.on(Evt.LAPS_SAVE, self.auto_zippyq, name='auto_zippyq')
        self._rhapi.events.on(Evt.LAPS_SAVE, self.auto_slot_score, name='auto_slot_score')
        self._rhapi.events.on(Evt.LAPS_RESAVE, self.auto_slot_score, name='auto_slot_score')

        self._rhapi.events.on(Evt.CLASS_ADD, self.zq_class_selector, name='update_zq_selector')
        self._rhapi.events.on(Evt.CLASS_DUPLICATE, self.zq_class_selector, name='update_zq_selector')
        self._rhapi.events.on(Evt.CLASS_ALTER, self.zq_class_selector, name='update_zq_selector')
        self._rhapi.events.on(Evt.CLASS_DELETE, self.zq_class_selector, name='update_zq_selector')
        self._rhapi.events.on(Evt.DATABASE_RESET, self.zq_class_selector, name='update_zq_selector')
        self._rhapi.events.on(Evt.DATABASE_RECOVER, self.zq_class_selector, name='update_zq_selector')

        self._rhapi.events.on(Evt.CLASS_ADD, self.results_class_selector, name='update_res_selector')
        self._rhapi.events.on(Evt.CLASS_DUPLICATE, self.results_class_selector, name='update_res_selector')
        self._rhapi.events.on(Evt.CLASS_ALTER, self.results_class_selector, name='update_res_selector')
        self._rhapi.events.on(Evt.CLASS_DELETE, self.results_class_selector, name='update_res_selector')
        self._rhapi.events.on(Evt.DATABASE_RESET, self.results_class_selector, name='update_res_selector')
        self._rhapi.events.on(Evt.DATABASE_RECOVER, self.results_class_selector, name='update_res_selector')

        self._rhapi.events.on(Evt.HEAT_ALTER, self.zq_race_selector, name='zq_race_selector')
        self._rhapi.events.on(Evt.LAPS_SAVE, self.zq_race_selector, name='zq_race_selector')
        self._rhapi.events.on(Evt.OPTION_SET, self.zq_pilot_selector, name='zq_pilot_selector')

        super().__init__()

        # Show relative Panels
        self.update_panels()

    #
    # Database Search
    #

    def pilot_search(self, db_pilots, mgp_pilot):
        for db_pilot in db_pilots:
            if mgp_pilot['pilotId'] == self._get_MGPpilotID(db_pilot.id):
                break
        else:
            mgp_pilot_name = mgp_pilot['firstName'] + " " + mgp_pilot['lastName']
            db_pilot = self._rhapi.db.pilot_add(name = mgp_pilot_name, callsign = mgp_pilot['userName'])
            attrs = {'mgp_pilot_id': mgp_pilot['pilotId']}

            if self._pilot_urls:
                attrs["PilotDetailPhotoURL"] = mgp_pilot["profilePictureUrl"]

            self._rhapi.db.pilot_alter(db_pilot.id, attributes = attrs)

        return db_pilot.id

    def format_search(self, db_formats, mgp_format):
        for rh_format in db_formats:

            GQ_SETTINGS = [
                self._rhapi.db.raceformat_attribute_value(rh_format.id, 'gq_format') == "1",
                mgp_format.mgp_gq,
                rh_format.name == mgp_format.name,
            ]

            if all(GQ_SETTINGS):
                format_id = rh_format.id
                break

            elif rh_format.name == mgp_format.name and not mgp_format.mgp_gq:
                format_id = rh_format.id
                break
        else:
            format_id = self._rhapi.db.raceformat_add(name=mgp_format.name, win_condition=mgp_format.win_condition, unlimited_time=mgp_format.unlimited_time,
                                    race_time_sec = mgp_format.race_time_sec, start_behavior=mgp_format.start_behavior, staging_delay_tones=2, staging_fixed_tones=3,
                                    team_racing_mode=mgp_format.team_racing_mode).id
            self._rhapi.db.raceformat_alter(format_id, attributes={'gq_format':mgp_format.mgp_gq})

        return format_id
    
    def fprofile_search(self, frequencyset):
        imported_set = json.dumps(frequencyset)
        frequencyset_names = []
        for profile in self._rhapi.db.frequencysets:
            frequencyset_names.append(profile.name)
            if profile.frequencies == imported_set:
                self._rhapi.db.option_set('currentProfile', profile.id)
                break
        else:
            index = 1
            base = "MultiGP Profile"
            while(f"{base} {index}" in frequencyset_names):
                index += 1
            profile = self._rhapi.db.frequencyset_add(name=f"{base} {index}", frequencies=imported_set)

        return profile.id
    
    #
    # Event Setup
    #

    # Import pilots
    def import_pilots(self, args):
        selected_race = self._rhapi.db.option('mgp_race_id')
        if not selected_race:
            message = "Select a MultiGP Race to import pilots from"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return
        db_pilots = self._rhapi.db.pilots
        race_data = self.multigp.pull_race_data(selected_race)

        for mgp_pilot in race_data['entries']:
            self.pilot_search(db_pilots, mgp_pilot)

        self._rhapi.ui.broadcast_pilots()
        message = "Pilots imported"
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))

    def setup_event(self, args):
        selected_race = self._rhapi.db.option('sel_mgp_race_id')
        if not selected_race:
            message = "Select a MultiGP Race to import"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return
        
        # Pull race data
        race_data = self.multigp.pull_race_data(selected_race)
        
        if self._rhapi.db.option('auto_logo') == '1':
            url = race_data['chapterImageFileName']
            file_name = url.split("/")[-1]
            save_location = "static/user/" + file_name
            response = requests.get(url)

            with open(save_location, mode="wb") as file:
                file.write(response.content)

            self._rhapi.config.set_item('UI', "timerLogo", file_name)

        rh_db = [
            self._rhapi.db.races,
            self._rhapi.db.heats,
            self._rhapi.db.raceclasses,
        ]

        if any(rh_db) or self._rhapi.db.option('mgp_race_id'):
            message = "Archive Race, Heat, Class, and Pilot data before continuing. Under the Event panel >> Archive/New Event >> Archive Event."
            self._rhapi.ui.message_alert(self._rhapi.language.__(message))
            return
        
        if race_data['raceType'] == '2':
            logger.info("Importing GQ race")
            verification_status = self._system_verification.get_system_status()
            for key, value in verification_status.items():
                if not value:
                    message = f"Global Qualifier not imported - {key}"
                    self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                    logger.warning(message)
                    return
                
        self._rhapi.db.option_set('mgp_race_id', selected_race)
        self._rhapi.db.option_set('eventName', race_data["name"])
        self._rhapi.db.option_set('eventDescription', race_data["description"])
        
        mgp_event_races = []
        if int(race_data["childRaceCount"]) > 0:
            for race in race_data["races"]:
                imported_data = self.multigp.pull_race_data(race["id"])
                self.import_class(race["id"], imported_data)
                mgp_event_races.append({'mgpid' : race["id"] , 'name' : race["name"]})
        else:
            self.import_class(selected_race, race_data)
            mgp_event_races.append({'mgpid' : selected_race, 'name' : race_data["name"]})
        self._rhapi.db.option_set('mgp_event_races', json.dumps(mgp_event_races))

        self._rhapi.ui.broadcast_raceclasses()
        self._rhapi.ui.broadcast_raceformats()
        self._rhapi.ui.broadcast_pilots()
        self._rhapi.ui.broadcast_frequencyset()
        self.update_panels()
        message = "Race class imported."
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))

    # Import classes from event
    def import_class(self, selected_race, race_data):
        
        schedule = race_data['schedule']
        MGP_format = race_data['scoringFormat']
        rh_race_name = race_data["name"]

        # Setup race format
        if race_data['raceType'] == '2':
            mgp_format = mgp_formats.GLOBAL.value
            self._rhapi.db.option_set('consecutivesCount', 3)
            self._rhapi.db.option_set('global_qualifer_event', '1')
            rh_race_name = mgp_format.name
        elif MGP_format == '0':
            logger.info("Importing standard race")
            mgp_format = mgp_formats.AGGREGATE.value
            self._rhapi.db.option_set('consecutivesCount', 3)
        elif MGP_format == '1':
            logger.info("Importing standard race")
            mgp_format = mgp_formats.FASTEST.value
            self._rhapi.db.option_set('consecutivesCount', 3)
        elif MGP_format == '2':
            logger.info("Importing standard race")
            mgp_format = mgp_formats.CONSECUTIVE.value
            self._rhapi.db.option_set('consecutivesCount', 3)
        elif MGP_format == '6':
            logger.info("Importing standard race")
            mgp_format = mgp_formats.CONSECUTIVE.value
            self._rhapi.db.option_set('consecutivesCount', 2)
        else:
            message = "Unrecognized MultiGP Format.Stopping Import"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return

        # Register Race Formats
        rh_formats = self._rhapi.db.raceformats
        format_id = self.format_search(rh_formats, mgp_format)
        
        # Adjust points for format
        if race_data['scoringDisabled'] == "0":
            self._rhapi.db.raceformat_alter(format_id, points_method="Position", points_settings={"points_list": "10,6,4,2,1,0"})
        else:
            self._rhapi.db.raceformat_alter(format_id, points_method=False)

        # Import Class
        if race_data['disableSlotAutoPopulation'] == "0" and 'rounds' in schedule:
            num_rounds = len(schedule['rounds'])
            race_class = self._rhapi.db.raceclass_add(name=rh_race_name, raceformat=format_id, win_condition='',
                                                      description="Imported Controlled class from MultiGP", rounds=num_rounds, heat_advance_type=HeatAdvanceType.NEXT_HEAT)
            db_pilots = self._rhapi.db.pilots
            slot_list = []

            default_profile = self._rhapi.db.frequencysets[0].frequencies
            num_of_slots = len(json.loads(default_profile)["f"])
            if len(schedule['rounds'][0]['heats'][0]['entries']) > num_of_slots:
                message = "Attempted to import race with more slots than avaliable nodes. Please decrease the number of slots used on MultiGP"
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                return

            for hindex, heat in enumerate(schedule['rounds'][0]['heats']):
                heat_data = self._rhapi.db.heat_add(name=f"Heat {hindex + 1}", raceclass=race_class.id)
                rh_slots = self._rhapi.db.slots_by_heat(heat_data.id)

                frequencyset = {'b':[],'c':[],'f':[]}
                count = 0

                for pindex, mgp_pilot in enumerate(heat['entries']):
                    count += 1
                    if 'pilotId' in mgp_pilot:
                        db_pilot_id = self.pilot_search(db_pilots, mgp_pilot)
                        slot_list.append({'slot_id':rh_slots[pindex].id, 'pilot':db_pilot_id})

                    frequencyset['b'].append(mgp_pilot["band"])
                    if mgp_pilot["channel"]:
                        frequencyset['c'].append(int(mgp_pilot["channel"]))
                    else: 
                        frequencyset['c'].append(None)
                    frequencyset['f'].append(int(mgp_pilot["frequency"]))

                while(count < num_of_slots):
                    count += 1
                    frequencyset['b'].append(None)
                    frequencyset['c'].append(None)
                    frequencyset['f'].append(0)

                fprofile_id = self.fprofile_search(frequencyset)
                self._rhapi.db.heat_alter(heat_data.id, attributes = {'heat_profile_id': fprofile_id})

            self._rhapi.db.slots_alter_fast(slot_list)
            self._rhapi.db.raceclass_alter(race_class.id, attributes = {'mgp_raceclass_id': selected_race, 'zippyq_class' : False, 'gq_class' : mgp_format.mgp_gq})
            self._rhapi.race.frequencyset = fprofile_id

        elif race_data['disableSlotAutoPopulation'] == "0":
            num_rounds = 0
            race_class = self._rhapi.db.raceclass_add(name=rh_race_name, raceformat=format_id, win_condition='',
                                                      description="Imported Controlled class from MultiGP", rounds=num_rounds, heat_advance_type=HeatAdvanceType.NEXT_HEAT)
            self._rhapi.db.raceclass_alter(race_class.id, attributes = {'mgp_raceclass_id': selected_race, 'zippyq_class' : False, 'gq_class' : mgp_format.mgp_gq})
            
        else:
            zippyq_races = self._rhapi.db.option('zippyq_races')
            zippyq_races += 1
            self._rhapi.db.option_set('zippyq_races', zippyq_races)
            race_class = self._rhapi.db.raceclass_add(name=rh_race_name, raceformat=format_id, win_condition='', 
                                                      description="Imported ZippyQ class from MultiGP", rounds=1, heat_advance_type=HeatAdvanceType.NONE)
        
            self._rhapi.db.raceclass_alter(race_class.id, attributes = {'mgp_raceclass_id': selected_race, 'zippyq_class' : True, 'gq_class' : mgp_format.mgp_gq})

    #
    # ZippyQ
    #

    # Configure ZippyQ round
    def zippyq(self, raceclass_id, selected_race, heat_num):
        data = self.multigp.pull_additional_rounds(selected_race, heat_num)

        try:
            heat_name = data['rounds'][0]['name']
        except IndexError:
            message = "Additional ZippyQ rounds not found"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return

        db_pilots = self._rhapi.db.pilots
        slot_list = []
        
        default_profile = self._rhapi.db.frequencysets[0].frequencies
        num_of_slots = len(json.loads(default_profile)["f"])
        if len(data['rounds'][0]['heats'][0]['entries']) > num_of_slots:
            message = "Attempted to import race with more slots than avaliable nodes. Please decrease the number of slots used on MultiGP"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return

        for hindex, heat in enumerate(data['rounds'][0]['heats']):
            heat_data = self._rhapi.db.heat_add(name=heat_name, raceclass=raceclass_id)
            rh_slots = self._rhapi.db.slots_by_heat(heat_data.id)

            frequencyset = {'b':[],'c':[],'f':[]}
            count = 0
            
            for pindex, mgp_pilot in enumerate(heat['entries']):
                count += 1
                if 'pilotId' in mgp_pilot:
                    db_pilot_id = self.pilot_search(db_pilots, mgp_pilot)
                    slot_list.append({'slot_id':rh_slots[pindex].id, 'pilot':db_pilot_id})

                frequencyset['b'].append(mgp_pilot["band"])
                if mgp_pilot["channel"]:
                    frequencyset['c'].append(int(mgp_pilot["channel"]))
                else: 
                    frequencyset['c'].append(None)
                frequencyset['f'].append(int(mgp_pilot["frequency"]))

            while(count < num_of_slots):
                count += 1
                frequencyset['b'].append(None)
                frequencyset['c'].append(None)
                frequencyset['f'].append(0)

            fprofile_id = self.fprofile_search(frequencyset)
            self._rhapi.db.heat_alter(heat_data.id, attributes = {'heat_profile_id': fprofile_id})
        
        self._rhapi.db.slots_alter_fast(slot_list)
        self._rhapi.ui.broadcast_pilots()
        self._rhapi.ui.broadcast_heats()
        message = "ZippyQ round imported."
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))

        return heat_data

    # Manually trigger ZippyQ round configuration
    def manual_zippyq(self, args):

        class_id = self._rhapi.db.option('zq_class_select')
        
        if not class_id:
            message = "ZippyQ class not found"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return

        selected_race = self._rhapi.db.raceclass_attribute_value(class_id, 'mgp_raceclass_id')
        
        class_races = self._rhapi.db.races_by_raceclass(class_id)
        races_length = len(class_races)

        class_heats = self._rhapi.db.heats_by_class(class_id)
        heats_length = len(class_heats)

        if races_length != heats_length:
            message = "ZippyQ: Complete all races before importing next round"
            self._rhapi.ui.message_alert(self._rhapi.language.__(message))
            return
        
        heat_data = self.zippyq(class_id, selected_race, races_length + 1)
        
        if self._rhapi.db.option('active_import') == '1':
            try:
                self._rhapi.race.heat = heat_data.id
            finally:
                pass

    # Automatically trigger next ZippyQ round configuration
    def auto_zippyq(self, args): 
        race_info = self._rhapi.db.race_by_id(args['race_id'])
        class_id = race_info.class_id

        if self._rhapi.db.raceclass_attribute_value(class_id, 'zippyq_class') != "1" or self._rhapi.db.option('auto_zippy') != "1":
            return

        message = "Automatically downloading next ZippyQ round..."
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))

        next_round = len(self._rhapi.db.heats_by_class(class_id)) + 1

        selected_race = self._rhapi.db.raceclass_attribute_value(class_id, 'mgp_raceclass_id')
        heat_data = self.zippyq(class_id, selected_race, next_round)

        if self._rhapi.db.option('active_import') == '1':
            try:
                self._rhapi.race.heat = heat_data.id
            finally:
                pass

    #
    # Event Results
    #
        
    def return_pack(self, args = None):
        race_id = self._rhapi.db.option('zq_race_select')
        pilot_id = self._rhapi.db.option('zq_pilot_select')
        
        if race_id and pilot_id:
            race_pilots = json.loads(self._rhapi.db.race_attribute_value(race_id, 'race_pilots'))
            if pilot_id in race_pilots:
                del race_pilots[pilot_id]
                self._rhapi.db.race_alter(race_id, attributes={'race_pilots' : json.dumps(race_pilots)})
                self.zq_pilot_selector(args = {'option' : 'zq_race_select'})

    # Slot and Score
    def slot_score(self, race_info, selected_race, multi_round, set_round_num, heat_number = 1, eventURL = None):
        results = self._rhapi.db.race_results(race_info.id)["by_race_time"]
        race_pilots = json.loads(self._rhapi.db.race_attribute_value(race_info.id, 'race_pilots'))

        for pilot_id in race_pilots:

            for result in results:
                if result["pilot_id"] == int(pilot_id):
                    break
            else:
                result = None

            if not multi_round:
                round_num = set_round_num
                heat_num = 1
            else:
                round_num = race_info.round_id
                heat_num = heat_number

            slot_num = race_pilots[pilot_id] + 1

            race_data = {}

            mgp_pilot_id = self._get_MGPpilotID(pilot_id)
            if mgp_pilot_id:
                race_data['pilotId'] = mgp_pilot_id
            else:
                pilot_info = self._rhapi.db.pilot_by_id(pilot_id)
                message = f'{pilot_info.callsign} does not have a MultiGP Pilot ID. Stopping results push...'
                logger.warning(message)
                self._rhapi.ui.message_alert(self._rhapi.language.__(message))
                return False

            if result:
                race_data['score'] = result["points"]
                race_data['totalLaps'] = result["laps"]
                race_data['totalTime'] = round(result["total_time_raw"] * .001, 3)
                race_data['fastestLapTime'] = round(result["fastest_lap_raw"] * .001, 3)

                if result["consecutives_base"] == 3:
                    race_data['fastest3ConsecutiveLapsTime'] = round(result["consecutives_raw"] * .001, 3)
                elif result["consecutives_base"] == 2:
                    race_data['fastest2ConsecutiveLapsTime'] = round(result["consecutives_raw"] * .001, 3)
            else:
                race_data['totalLaps'] = 0
            
            if eventURL:
                race_data['liveTimeEventUrl'] = eventURL

            if self.multigp.push_slot_and_score(selected_race, round_num, heat_num, slot_num, race_data):
                logger.info(f'Pushed results for {selected_race}: Round {round_num}, Heat {heat_num}, Solt {slot_num}')
            else:
                message = "Results push to MultiGP FAILED."
                self._rhapi.ui.message_alert(self._rhapi.language.__(message))
                return False

        return True

    # Automatially push results of ZippyQ heat
    def auto_slot_score(self, args):

        race_info = self._rhapi.db.race_by_id(args['race_id'])
        class_id = race_info.class_id

        # ZippyQ checks
        if self._rhapi.db.raceclass_attribute_value(class_id, 'zippyq_class') != "1":
            return

        selected_race = self._rhapi.db.raceclass_attribute_value(class_id, 'mgp_raceclass_id')
        gq_active = self._rhapi.db.option('global_qualifer_event') == "1"

        if gq_active:
            self._rhapi.db.option_set('consecutivesCount', 3)
            verification_status = self._system_verification.get_system_status()
            for key, value in verification_status.items():
                if not value:
                    message = f"Stopping Results push - {key}"
                    self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                    logger.warning(message)
                    return

        # Handle FPVScores
        FPVS_CONDITIONALS = [
            self._rhapi.db.option('push_fpvs') == '1', 
            miniFPVscores.linkedMGPOrg(self._rhapi) or self._rhapi.db.option('event_uuid')
        ]

        if self._rhapi.db.raceclass_attribute_value(class_id, 'gq_class') == "1":
            self.clear_uuid()
            mgp_raceclass_id = self._rhapi.db.raceclass_attribute_value(class_id, 'mgp_raceclass_id')
            self._rhapi.db.option_set('mgp_race_id', mgp_raceclass_id)
            message, uuid = miniFPVscores.runPushMGP(self._rhapi)
            if uuid is None:
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                return
            eventURL = miniFPVscores.getURLfromFPVS(self._rhapi, uuid)
            self._rhapi.ui.broadcast_ui('format')
        elif all(FPVS_CONDITIONALS):
            mgp_raceclass_id = self._rhapi.db.raceclass_attribute_value(class_id, 'mgp_raceclass_id')
            self._rhapi.db.option_set('mgp_race_id', mgp_raceclass_id)
            message, uuid = miniFPVscores.runPushMGP(self._rhapi)
            if uuid is None:
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                eventURL = None
            else:
                eventURL = miniFPVscores.getURLfromFPVS(self._rhapi, uuid)
                self._rhapi.db.option_set('event_uuid', uuid)
                self._rhapi.ui.broadcast_ui('format')
        else:
            uuid = self._rhapi.db.option('event_uuid')
            eventURL = None

        # Upload Results
        message = "Automatically uploading race data..."
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))
        heat_info = self._rhapi.db.heat_by_id(race_info.heat_id)

        heat_ids = []
        for heat in self._rhapi.db.heats_by_class(class_id):
            heat_ids.append(heat.id)

        round_num = heat_ids.index(heat_info.id) + 1

        if self.slot_score(race_info, selected_race, False, round_num, eventURL=eventURL):
            message = "Data successfully pushed to MultiGP."
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))

    def manual_slot_score(self, selected_mgp_race, selected_rh_class, eventURL):

        def sort_by_round(race_info):
            return race_info.round_id

        races = self._rhapi.db.races_by_raceclass(selected_rh_class)
        races.sort(key=sort_by_round)

        if self._rhapi.db.raceclass_attribute_value(selected_rh_class, 'zippyq_class') == "1":
            multi_round = False
        else:
            multi_round = True

        if multi_round:
            class_heats = []
            for heat in self._rhapi.db.heats_by_class(selected_rh_class):
                class_heats.append(heat.id)
            class_heats.sort()

        # Upload Results
        heat_number = 0
        for index, race_info in enumerate(races):
            if multi_round:
                heat_number = class_heats.index(race_info.heat_id) + 1

            if not self.slot_score(race_info, selected_mgp_race, multi_round, index + 1, heat_number=heat_number, eventURL=eventURL):
                return False
        else:
            message = "Results successfully pushed to MultiGP."
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return True

    # Push class results
    def push_results(self, _args):

        for db_pilot in self._rhapi.db.pilots:
            if not self._get_MGPpilotID(db_pilot.id):
                message = f'{db_pilot.callsign} does not have a MultiGP Pilot ID. Stopping results push...'
                self._rhapi.ui.message_alert(self._rhapi.language.__(message))
                return

        gq_active = self._rhapi.db.option('global_qualifer_event') == "1"

        if gq_active:
            self._rhapi.db.option_set('consecutivesCount', 3)
            verification_status = self._system_verification.get_system_status()
            for key, value in verification_status.items():
                if not value:
                    message = f"Stopping Results push - {key}"
                    self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                    logger.warning(message)
                    return
        else:
            for index, race in enumerate(json.loads(self._rhapi.db.option('mgp_event_races'))):
                selected_results = self._rhapi.db.option(f'results_select_{index}')
                if selected_results == "":
                    message = f"Choose a class to upload results for {race['name']}"
                    self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                    return

        # Handle FPVScores        
        FPVS_CONDITIONALS = [
            self._rhapi.db.option('push_fpvs') == '1', 
            miniFPVscores.linkedMGPOrg(self._rhapi) or self._rhapi.db.option('event_uuid')
        ]

        if gq_active:
            self._rhapi.db.option_set('push_fpvs', '1')
            self.clear_uuid()
            message, uuid = miniFPVscores.runPushMGP(self._rhapi)
            if uuid is None:
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                return
            self._rhapi.ui.broadcast_ui('format')
            eventURL = miniFPVscores.getURLfromFPVS(self._rhapi, uuid)
        elif all(FPVS_CONDITIONALS):
            message, uuid = miniFPVscores.runPushMGP(self._rhapi)
            if uuid is None:
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                return
            else:
                eventURL = miniFPVscores.getURLfromFPVS(self._rhapi, uuid)
                self._rhapi.db.option_set('event_uuid', uuid)
                self._rhapi.ui.broadcast_ui('format')
        else:
            uuid = self._rhapi.db.option('event_uuid')
            eventURL = None

        # Determine results formating        
        message = "Starting to push results to MultiGP... This may take some time..."
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))

        # Rankings Push
        for index, race in enumerate(json.loads(self._rhapi.db.option('mgp_event_races'))):
            if gq_active:
                for rh_class in self._rhapi.db.raceclasses:
                    mgp_id = self._rhapi.db.raceclass_attribute_value(rh_class.id, 'mgp_raceclass_id')
                    if mgp_id == race['mgpid']:
                        break
                else: 
                    message = "Imported Global Qualifier class not found... aborting results push"
                    self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                    return
                if not self.manual_slot_score(race['mgpid'], rh_class.id, eventURL):
                    return
            else:
                if not self.manual_slot_score(race['mgpid'], self._rhapi.db.option(f'results_select_{index}'), eventURL):
                    return

        # Rankings Push
        for index, race in enumerate(json.loads(self._rhapi.db.option('mgp_event_races'))):
            if gq_active:
                if self._system_verification.capture_race_results(race['mgpid']):
                    message = "Successfully processed Global Qualifer race results"
                    self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                else:
                    message = "Failed to process Global Qualifer race results"
                    self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            else:
                self.push_bracketed_rankings(race['mgpid'], self._rhapi.db.option(f'ranks_select_{index}'))

    # Push class ranking
    def push_bracketed_rankings(self, selected_mgp_race, selected_rh_class):

        if selected_rh_class == "" or selected_rh_class is None:
            return

        results = []

        rankings = self._rhapi.db.raceclass_ranking(selected_rh_class)
        results_list = self._rhapi.db.raceclass_results(selected_rh_class)

        if rankings:
            win_condition = None
            data = rankings["ranking"]
        elif results_list:
            primary_leaderboard = results_list["meta"]["primary_leaderboard"]
            win_condition = results_list["meta"]["win_condition"]
            data = results_list[primary_leaderboard]

        if rankings or (results_list and win_condition):
            for pilot in data:
                multigp_id = int(self._rhapi.db.pilot_attribute_value(pilot['pilot_id'], 'mgp_pilot_id'))
                if multigp_id:
                    class_position = (pilot['position'])
                    result_dict = {"orderNumber" : class_position, "pilotId" : multigp_id}
                    results.append(result_dict)
                else:
                    logger.warning(f'Pilot {pilot["pilot_id"]} does not have a MultiGP Pilot ID. Skipping...')

            push_status = self.multigp.push_overall_race_results(selected_mgp_race, results)
            if push_status:
                message = "Rankings pushed to MultiGP"
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            else:
                message = "Failed to push rankings to MultiGP"
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))

    #
    # Race Verification
    #
    
    def verify_race(self, args):

        if not self._rhapi.db.option('mgp_race_id'):
            return

        heat_id = args['heat_id']
        heat_info = self._rhapi.db.heat_by_id(heat_id)
        
        if heat_info is None:
            return

        # Verify pilot only occupy one slot in heat
        slots = self._rhapi.db.slots_by_heat(heat_id)
        heat_pilots = []
        pilot_counter = 0
        for slot_info in slots:
            if slot_info.pilot_id == 0:
                continue
            elif slot_info.pilot_id in heat_pilots:
                self._rhapi.race.stop()
                pilot_info = self._rhapi.db.pilot_by_id(slot_info.pilot_id)
                message = f"MultiGP Toolkit: {pilot_info.callsign} occupies more than one slot in current heat"
                self._rhapi.ui.message_alert(self._rhapi.language.__(message))
                return
            else:
                heat_pilots.append(slot_info.pilot_id)
                pilot_counter += 1

        if pilot_counter == 0:
            self._rhapi.race.stop()

        # Verify rounds for respective formats
        zq_state = self._rhapi.db.raceclass_attribute_value(heat_info.class_id, 'zippyq_class')
        num_completed_rounds = len(self._rhapi.db.races_by_heat(heat_id))
        for heat in self._rhapi.db.heats_by_class(heat_info.class_id):
            heat_rounds = self._rhapi.db.heat_max_round(heat.id)
            round_difference = num_completed_rounds - heat_rounds
            
            # ZippyQ - Repeated Round Check
            if zq_state == "1" and self._rhapi.db.heat_max_round(heat_id) > 0:
                self._rhapi.race.stop()
                message = f"ZippyQ: Round cannot be repeated"
                self._rhapi.ui.message_alert(self._rhapi.language.__(message))
                return
            
            # ZippyQ - Round Order Check
            elif zq_state == "1" and heat.id < heat_id and self._rhapi.db.heat_max_round(heat.id) == 0:
                self._rhapi.race.stop()
                check_heat = self._rhapi.db.heat_by_id(heat.id)
                message = f"ZippyQ: Complete {check_heat.name} before starting {heat_info.name}"
                self._rhapi.ui.message_alert(self._rhapi.language.__(message))
                return
            
            # Controlled - Multi Heat Pilot Check 
            elif zq_state != "1" and heat.id != heat_id:
                for solt in self._rhapi.db.slots_by_heat(heat.id):
                    if solt.pilot_id in heat_pilots:
                        pilot = self._rhapi.db.pilot_by_id(solt.pilot_id)
                        message = f"MultiGP Toolkit: {pilot.callsign} is in multiple heats within this class. MultiGP will only accept results from their last heat."
                        self._rhapi.ui.message_notify(self._rhapi.language.__(message))

        if self._rhapi.db.raceclass_attribute_value(heat_info.class_id, 'gq_class') != "1":
            return
        
        for heat in self._rhapi.db.heats_by_class(heat_info.class_id):
            heat_rounds = self._rhapi.db.heat_max_round(heat.id)
            round_difference = num_completed_rounds - heat_rounds
            
            # Controlled - Round Incrementing Check
            if zq_state != "1" and round_difference > 0:
                self._rhapi.race.stop()
                check_heat = self._rhapi.db.heat_by_id(heat.id)
                message = f"MultiGP Toolkit: Run {check_heat.name} before starting {heat_info.name}'s next round"
                self._rhapi.ui.message_alert(self._rhapi.language.__(message))
                return

        # GQ - System codebase check
        if not self._system_verification.get_integrity_check():
            self._rhapi.race.stop()
            message = f"Your system's codebase has been modified and is not approved to run Global Qualifier races"
            self._rhapi.ui.message_alert(self._rhapi.language.__(message))
            return

        # GQ - Minimum pilot check
        if pilot_counter < 3:
            self._rhapi.race.stop()
            message = f"GQ Rules: At least 3 pilots are required to start the race"
            self._rhapi.ui.message_alert(self._rhapi.language.__(message))
            return

    # GQ class settings
    def verify_class(self, args):
        class_id = args['class_id']

        if self._rhapi.db.raceclass_attribute_value(class_id, 'gq_class') != "1":
            return

        class_info = self._rhapi.db.raceclass_by_id(class_id)

        CLASS_CONDITIONS = [
            class_info.name == mgp_formats.GLOBAL.value.name,
            self._rhapi.db.raceformat_attribute_value(class_info.format_id, 'gq_format') == "1",
            class_info.win_condition == '',
        ]
        
        if not all(CLASS_CONDITIONS):
            rh_formats = self._rhapi.db.raceformats
            gq_format = mgp_formats.GLOBAL.value
            rh_format = self.format_search(rh_formats, gq_format)

            self._rhapi.db.raceclass_alter(class_info.id, name=gq_format.name, raceformat=rh_format, rounds=10, win_condition='')
            self._rhapi.ui.broadcast_raceclasses()
            self._rhapi.ui.broadcast_raceformats()

    # Verify all classes
    def verify_classes(self, _args):
        for raceclass in self._rhapi.db.raceclasses:
            args = {'class_id' : raceclass.id}
            self.verify_class(args)

    # GQ format settings
    def verify_format(self, args):
        format_id = args['race_format']

        if self._rhapi.db.raceformat_attribute_value(format_id, 'gq_format') != "1":
            return
        
        format_info = self._rhapi.db.raceformat_by_id(format_id)
        gq_format = mgp_formats.GLOBAL.value

        FORMAT_CONDITIONS = [
            format_info.name                == gq_format.name,
            format_info.race_time_sec       == gq_format.race_time_sec,
            format_info.win_condition       == gq_format.win_condition,
            format_info.unlimited_time      == gq_format.unlimited_time,
            format_info.start_behavior      == gq_format.start_behavior,
            format_info.team_racing_mode    == gq_format.team_racing_mode,
        ]

        if not all(FORMAT_CONDITIONS):
            self._rhapi.db.raceformat_alter(format_info.id, name=gq_format.name, race_time_sec=gq_format.race_time_sec, 
                                            unlimited_time=gq_format.unlimited_time, win_condition=gq_format.win_condition,
                                            start_behavior=gq_format.start_behavior, team_racing_mode=gq_format.team_racing_mode)
            self._rhapi.ui.broadcast_raceformats()