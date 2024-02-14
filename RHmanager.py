import sys
import logging
import json
from dataclasses import dataclass
from eventmanager import Evt
from enum import Enum

from Database import HeatAdvanceType
from RHUI import UIField, UIFieldType, UIFieldSelectOption
from RHRace import WinCondition, StartBehavior

from plugins.MultiGP_Toolkit.multigpAPI import multigpAPI
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

class RHmanager():

    _multigp_cred_set = False
    _mgp_races = {}
    _system_verification = systemVerification.systemVerification()

    def __init__(self, rhapi):
        self._rhapi = rhapi
        self.multigp = multigpAPI()
        self.FPVscores_installed = 'plugins.fpvscores' in sys.modules

        self._rhapi.events.on(Evt.STARTUP, self.verify_creds, name='verify_creds')
        self._rhapi.events.on(Evt.DATA_EXPORT_INITIALIZE, miniFPVscores.register_handlers)
        self._rhapi.events.on(Evt.RACE_STAGE, self.verify_race, name='verify_race')
        self._rhapi.events.on(Evt.CLASS_ALTER, self.verify_class, name='verify_class')
        self._rhapi.events.on(Evt.RACE_FORMAT_ALTER, self.verify_format, name='verify_format')
        self._rhapi.events.on(Evt.RACE_FORMAT_DELETE, self.verify_classes, name='verify_classes')
        self._rhapi.events.on(Evt.DATABASE_RESET, self.reset_event_metadata, name='reset_event_metadata')
        self._rhapi.events.on(Evt.DATABASE_RECOVER, self.restore_race_metadata, name='restore_race_metadata')
        self._rhapi.events.on(Evt.HEAT_SET, self.set_frequency_profile, name='set_frequency_profile')
        
    #
    # Metadata Management    
    #

    def clear_uuid(self, _args = None):
        self._rhapi.db.option_set('event_uuid', '')

    def reset_event_metadata(self, _args = None):
        self._rhapi.db.option_set('event_uuid', '')
        self._rhapi.db.option_set('mgp_race_id', '')
        self._rhapi.db.option_set('zippyq_event', '0')
        self._rhapi.db.option_set('global_qualifer_event', '0')
        self.update_panels()
        self._rhapi.ui.broadcast_ui('format')

    def restore_race_metadata(self, _args = None):
        self.update_panels()
        self._rhapi.ui.broadcast_ui('format')

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

    def verify_creds(self, args):

        key = self._rhapi.db.option('mgp_api_key')
        if key:
            self.multigp.set_apiKey(key)
        else:
            return

        try:
            self._chapter_name = self.multigp.pull_chapter()
        except:
            logger.info(f"Please check the entered key or the RotorHazard system's internet connection")
            return

        if self._chapter_name:
            logger.info(f"API key for {self._chapter_name} has been recognized")
        else:
            logger.info(f"API key cannot be verified.")
            return
        
        self.setup_plugin()

    #
    # Setup Plugin's Tools
    #

    def setup_plugin(self):
        self._rhapi.events.on(Evt.LAPS_SAVE, self.auto_zippyq, name='auto_zippyq')
        self._rhapi.events.on(Evt.LAPS_SAVE, self.auto_slot_score, name='auto_slot_score')
        self._rhapi.events.on(Evt.LAPS_RESAVE, self.auto_slot_score, name='auto_slot_score')
        self._rhapi.events.on(Evt.CLASS_ADD, self.results_class_selector)
        self._rhapi.events.on(Evt.CLASS_DUPLICATE, self.results_class_selector)
        self._rhapi.events.on(Evt.CLASS_ALTER, self.results_class_selector, name='update_selector')
        self._rhapi.events.on(Evt.CLASS_DELETE, self.results_class_selector)
        self._rhapi.events.on(Evt.DATABASE_RESET, self.results_class_selector, name='reset_classes')

        # Setup Panels in Background
        self.create_race_import_menu()
        self.create_pilot_import_menu()
        self.create_zippyq_controls()
        self.create_results_export_menu()
        self.create_gq_export_menu()

        self.update_panels()
        self._rhapi.ui.broadcast_ui('format')

    def update_panels(self):
        race_imported = self._rhapi.db.option('mgp_race_id') != ''
        zippyq_event = self._rhapi.db.option('zippyq_event') == '1'
        gq_event = self._rhapi.db.option('global_qualifer_event') == '1'

        if race_imported:
            self.show_race_import_menu(False)
            self.show_pilot_import_menu()

            if zippyq_event:
                self.show_zippyq_controls()

            if gq_event:
                self.show_gq_export_menu()
            else:
                self.show_results_export_menu()

        else:
            self.show_race_import_menu()
            self.show_pilot_import_menu(False)
            self.show_zippyq_controls(False)
            self.show_results_export_menu(False)
            self.show_gq_export_menu(False)

        self._rhapi.ui.broadcast_ui('format')

    def create_race_import_menu(self):
        self._rhapi.ui.register_panel('multigp_race_import', f'MultiGP Race Import - {self._chapter_name}', '', order=0)
        self.setup_race_selector()
        self._rhapi.ui.register_quickbutton('multigp_race_import', 'refresh_events', 'Refresh MultiGP Races', self.setup_race_selector, args = {'refreshed':True})
        self._rhapi.ui.register_quickbutton('multigp_race_import', 'import_class', 'Import Race', self.import_class)

    def show_race_import_menu(self, hidden = True):
        if hidden:
            self._rhapi.ui.register_panel('multigp_race_import', f'MultiGP Race Import - {self._chapter_name}', 'format', order=0)
        else:
            self._rhapi.ui.register_panel('multigp_race_import', f'MultiGP Race Import - {self._chapter_name}', '', order=0)

    def create_pilot_import_menu(self):
        self._rhapi.ui.register_panel('multigp_pilot_import', f'MultiGP Pilot Import', '', order=0)
        self._rhapi.ui.register_quickbutton('multigp_pilot_import', 'import_pilots', 'Import Pilots', self.import_pilots)

    def show_pilot_import_menu(self, hidden = True):
        if hidden:
            self._rhapi.ui.register_panel('multigp_pilot_import', f'MultiGP Pilot Import', 'format', order=0)
        else:
            self._rhapi.ui.register_panel('multigp_pilot_import', f'MultiGP Pilot Import', '', order=0)

    def create_zippyq_controls(self):
        self._rhapi.ui.register_panel('zippyq_controls', f'ZippyQ Controls', '', order=0)
        
        auto_zippy_text = self._rhapi.language.__('Use Automatic ZippyQ Tools')
        auto_zippy = UIField('auto_zippy', auto_zippy_text, desc="Auto Round Import / Auto Results Push", field_type = UIFieldType.CHECKBOX)
        self._rhapi.fields.register_option(auto_zippy, 'zippyq_controls')

        zippyq_round_text = self._rhapi.language.__('ZippyQ round number')
        zippyq_round = UIField('zippyq_round', zippyq_round_text, desc="Round to be imported by [Import ZippyQ Round]", field_type = UIFieldType.BASIC_INT, value = 1)
        self._rhapi.fields.register_option(zippyq_round, 'zippyq_controls')

        self._rhapi.ui.register_quickbutton('zippyq_controls', 'zippyq_import', 'Import ZippyQ Round', self.manual_zippyq)

    def show_zippyq_controls(self, hidden = True):
        if hidden:
            self._rhapi.ui.register_panel('zippyq_controls', f'ZippyQ Controls', 'format', order=0)
        else:
            self._rhapi.ui.register_panel('zippyq_controls', f'ZippyQ Controls', '', order=0)

    def create_results_export_menu(self):
        self._rhapi.ui.register_panel('results_controls', f'MultiGP Results Controls', '', order=0)

        self.results_class_selector()

        push_fpvs_text = self._rhapi.language.__('Upload to FPVScores on Results Push')
        push_fpvs = UIField('push_fpvs', push_fpvs_text, desc="FPVScores Event UUID is optional when your MGP Chapter is linked to an FPVScores Organization", field_type = UIFieldType.CHECKBOX)
        self._rhapi.fields.register_option(push_fpvs, 'results_controls')

        if not self.FPVscores_installed:
            fpv_scores_text = self._rhapi.language.__('FPVScores Event UUID')
            fpv_scores = UIField('event_uuid', fpv_scores_text, desc="Provided by FPVScores", field_type = UIFieldType.TEXT)
            self._rhapi.fields.register_option(fpv_scores, 'results_controls')

        self._rhapi.ui.register_quickbutton('results_controls', 'push_results', 'Push Event Results', self.push_results)

    def show_results_export_menu(self, hidden = True):
        if hidden:
            self._rhapi.ui.register_panel('results_controls', f'MultiGP Results Controls', 'format', order=0)
        else:
            self._rhapi.ui.register_panel('results_controls', f'MultiGP Results Controls', '', order=0)

    def create_gq_export_menu(self):
        self._rhapi.ui.register_panel('gqresults_controls', f'MultiGP Results Controls', '', order=0)
        self._rhapi.ui.register_quickbutton('gqresults_controls', 'push_gqresults', 'Push Event Results', self.push_results)

    def show_gq_export_menu(self, hidden = True):
        if hidden:
            self._rhapi.ui.register_panel('gqresults_controls', f'MultiGP Results Controls', 'format', order=0)
        else:
            self._rhapi.ui.register_panel('gqresults_controls', f'MultiGP Results Controls', '', order=0)

    # Race selector
    def setup_race_selector(self, args = None):
        self._mgp_races = self.multigp.pull_races()
        race_list = [UIFieldSelectOption(value = None, label = "")]
        for id, name in self._mgp_races.items():
            race_selection = UIFieldSelectOption(value = id, label = f"({id}) {name}")
            race_list.append(race_selection)

        race_selector = UIField('sel_mgp_race_id', 'MultiGP Race', desc="Event Selection", field_type = UIFieldType.SELECT, options = race_list)
        self._rhapi.fields.register_option(race_selector, 'multigp_race_import')

        if args:
            self._rhapi.ui.broadcast_ui('format')

    # Setup RH Class selector
    def results_class_selector(self, args = None):
        class_list = [UIFieldSelectOption(value = None, label = "")]
        
        for event_class in self._rhapi.db.raceclasses:
            race_class = UIFieldSelectOption(value = event_class.id, label = event_class.name)
            class_list.append(race_class)
        
        results_selector = UIField('results_select', 'Results Class', desc="Class holding the results to be pushed to MultiGP", field_type = UIFieldType.SELECT, options = class_list)
        self._rhapi.fields.register_option(results_selector, 'results_controls')

        ranking_selector = UIField('ranks_select', 'Rankings Class', desc="Class holding the rankings to be pushed to MultiGP. Only works if the selected class is using a ranking method", field_type = UIFieldType.SELECT, options = class_list)
        self._rhapi.fields.register_option(ranking_selector, 'results_controls')

        if args:
            self._rhapi.ui.broadcast_ui('format')

    def set_frequency_profile(self, args):
        fprofile_id = self._rhapi.db.heat_attribute_value(args['heat_id'], 'heat_profile_id')
        if fprofile_id:
            self._rhapi.race.frequencyset = fprofile_id
            self._rhapi.ui.broadcast_frequencies()

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
            self._rhapi.db.pilot_alter(db_pilot.id, attributes = {'mgp_pilot_id': mgp_pilot['pilotId']})

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

    # Import classes from event
    def import_class(self, args):
        selected_race = self._rhapi.db.option('sel_mgp_race_id')
        if not selected_race:
            message = "Select a MultiGP Race to import"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return
        
        rh_db = [
            self._rhapi.db.races,
            self._rhapi.db.heats,
            self._rhapi.db.raceclasses,
            self._rhapi.db.pilots,
        ]

        if any(rh_db) or self._rhapi.db.option('mgp_race_id'):
            message = "Please archive Race, Heat, Class, and Pilot data before continuing. Under the Event panel >> Archive/New Event >> Archive Event."
            self._rhapi.ui.message_alert(self._rhapi.language.__(message))
            return

        # Pull race data
        race_data = self.multigp.pull_race_data(selected_race)
        schedule = race_data['schedule']
        MGP_format = race_data['scoringFormat']

        # Setup race format
        if race_data['raceType'] == '2':
            logger.info("Importing GQ race")
            verification_status = self._system_verification.get_system_status()
            for key, value in verification_status.items():
                if not value:
                    message = f"Global Qualifier not imported - {key}"
                    self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                    logger.warning(message)
                    return
            else:
                mgp_format = mgp_formats.GLOBAL.value
                self._rhapi.db.option_set('consecutivesCount', 3)
                self._rhapi.db.option_set('global_qualifer_event', '1')
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
        
        self._rhapi.db.option_set('mgp_race_id', selected_race)
        self._rhapi.db.option_set('eventName', race_data["name"])
        self._rhapi.db.option_set('eventDescription', race_data["description"])

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
            race_class = self._rhapi.db.raceclass_add(name=self._mgp_races[selected_race], raceformat=format_id, win_condition='',
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

            imported_set = json.dumps(frequencyset)
            frequencyset_names = []
            for fset in self._rhapi.db.frequencysets:
                frequencyset_names.append(fset.name)
                if json.loads(fset.frequencies)["f"] == frequencyset["f"]:
                    self._rhapi.db.option_set('currentProfile', fset.id)
                    break
            else:
                index = 1
                base = "MultiGP Profile"
                while(f"{base} {index}" in frequencyset_names):
                    index += 1
                new_profile = self._rhapi.db.frequencyset_add(name=f"{base} {index}", frequencies=imported_set)
                self._rhapi.db.option_set('currentProfile', new_profile.id)

        elif race_data['disableSlotAutoPopulation'] == "0":
            num_rounds = 0
            race_class = self._rhapi.db.raceclass_add(name=self._mgp_races[selected_race], raceformat=format_id, win_condition='',
                                                      description="Imported Controlled class from MultiGP", rounds=num_rounds, heat_advance_type=HeatAdvanceType.NEXT_HEAT)
            self._rhapi.db.raceclass_alter(race_class.id, attributes = {'mgp_raceclass_id': selected_race, 'zippyq_class' : False, 'gq_class' : mgp_format.mgp_gq})
            
        else:
            self._rhapi.db.option_set('zippyq_event', '1')
            race_class = self._rhapi.db.raceclass_add(name=self._mgp_races[selected_race], raceformat=format_id, win_condition='', 
                                                      description="Imported ZippyQ class from MultiGP", rounds=1, heat_advance_type=HeatAdvanceType.NONE)
        
            self._rhapi.db.raceclass_alter(race_class.id, attributes = {'mgp_raceclass_id': selected_race, 'zippyq_class' : True, 'gq_class' : mgp_format.mgp_gq})

        self.update_panels()

        self._rhapi.ui.broadcast_raceclasses()
        self._rhapi.ui.broadcast_raceformats()
        self._rhapi.ui.broadcast_pilots()
        self._rhapi.ui.broadcast_frequencyset()
        self._rhapi.ui.broadcast_ui('format')
        message = "Race class imported."
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))

    #
    # ZippyQ
    #

    # Configure ZippyQ round
    def zippyq(self, raceclass_id, selected_race, heat_num):
        data = self.multigp.pull_additional_rounds(selected_race, heat_num)
        db_pilots = self._rhapi.db.pilots

        try:
            heat_name = data['rounds'][0]['name']
        except:
            message = "Additional ZippyQ rounds not found"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return

        slot_list = []
        for heat in data['rounds'][0]['heats']:
            heat_data = self._rhapi.db.heat_add(name=heat_name, raceclass=raceclass_id)
            rh_slots = self._rhapi.db.slots_by_heat(heat_data.id)
            
            for index, mgp_pilot in enumerate(heat['entries']):
                try:
                    db_pilot_id = self.pilot_search(db_pilots, mgp_pilot)              
                except:
                    continue
                else:
                    slot_list.append({'slot_id':rh_slots[index].id, 'pilot':db_pilot_id})  
        
        self._rhapi.db.slots_alter_fast(slot_list)
        self._rhapi.ui.broadcast_pilots()
        self._rhapi.ui.broadcast_heats()
        message = "ZippyQ round imported."
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))

        return heat_data

    # Manually trigger ZippyQ round configuration
    def manual_zippyq(self, args):
        selected_race = selected_race = self._rhapi.db.option('mgp_race_id')

        for rh_class in self._rhapi.db.raceclasses:
                zq_state = self._rhapi.db.raceclass_attribute_value(rh_class.id, 'zippyq_class')
                if zq_state == '1':
                    selected_class = rh_class.id
                    break
        else:
            message = "Imported ZippyQ class not found"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return
        
        self.zippyq(selected_class, selected_race, self._rhapi.db.option('zippyq_round'))

    # Automatically trigger next ZippyQ round configuration
    def auto_zippyq(self, args): 
        race_info = self._rhapi.db.race_by_id(args['race_id'])
        class_id = race_info.class_id

        if self._rhapi.db.raceclass_attribute_value(class_id, 'zippyq_class') != "1" or self._rhapi.db.option('auto_zippy') != "1":
            return

        message = "Automatically downloading next ZippyQ round..."
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))

        next_round = len(self._rhapi.db.heats_by_class(class_id)) + 1

        selected_race = selected_race = self._rhapi.db.option('mgp_race_id')
        heat_data = self.zippyq(class_id, selected_race, next_round)
        try:
            self._rhapi.race.heat = heat_data.id
        finally:
            pass

    #
    # Event Results
    #

    # Slot and Score
    def slot_score(self, race_info, selected_race, multi_round, set_round_num, eventURL = None):
        results = self._rhapi.db.race_results(race_info.id)["by_race_time"]

        # Determine round and heat from format
        if multi_round:
            for result in results:

                if self.custom_round_number < race_info.round_id:
                    self.custom_round_number = race_info.round_id
                    self.custom_heat_number = 1
                    self.round_pilots = []

                if result["pilot_id"] in self.round_pilots:
                    self.override_round_heat = True
                    self.custom_round_number += 1
                    self.custom_heat_number = 1
                    self.round_pilots = []
                    break

        # Push results
        for result in results:

            if not multi_round:
                round_num = set_round_num
                heat_num = 1
            elif self.override_round_heat:
                round_num = self.custom_round_number
                heat_num = self.custom_heat_number
            else:
                round_num = race_info.round_id
                heat_num = self.custom_heat_number

            slot_num = result["node"] + 1

            race_data = {}

            mgp_pilot_id = self._get_MGPpilotID(result["pilot_id"])
            if mgp_pilot_id:
                race_data['pilotId'] = mgp_pilot_id
            else:
                logger.warning(f'Pilot {result["pilot_id"]} does not have a MultiGP Pilot ID. Skipping...')
                continue

            race_data['score'] = result["points"]
            race_data['totalLaps'] = result["laps"]
            race_data['totalTime'] = round(result["total_time_raw"] * .001, 3)
            race_data['fastestLapTime'] = round(result["fastest_lap_raw"] * .001, 3)

            if result["consecutives_base"] == 3:
                race_data['fastest3ConsecutiveLapsTime'] = round(result["consecutives_raw"] * .001, 3)
            elif result["consecutives_base"] == 2:
                race_data['fastest2ConsecutiveLapsTime'] = round(result["consecutives_raw"] * .001, 3)
            if eventURL:
                race_data['liveTimeEventUrl'] = eventURL

            self.round_pilots.append(result["pilot_id"])

            if self.multigp.push_slot_and_score(selected_race, round_num, heat_num, slot_num, race_data):
                logger.info(f'Pushed results for {selected_race}: Round {round_num}, Heat {heat_num}, Solt {slot_num}')
            else:
                message = "Results push to MultiGP FAILED. Check the timer's internet connection."
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                return False
        else:
            self.custom_heat_number += 1
            return True

    # Automatially push results of ZippyQ heat
    def auto_slot_score(self, args):

        self.override_round_heat = False
        self.round_pilots = []
        self.custom_round_number = 1
        self.custom_heat_number = 1

        race_info = self._rhapi.db.race_by_id(args['race_id'])
        class_id = race_info.class_id

        # ZippyQ checks
        if self._rhapi.db.raceclass_attribute_value(class_id, 'zippyq_class') != "1" or self._rhapi.db.option('auto_zippy') != "1":
            return

        selected_race = self._rhapi.db.option('mgp_race_id')
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
        message = "Automatically uploading results..."
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))
        heat_info = self._rhapi.db.heat_by_id(race_info.heat_id)
        round_num = self._rhapi.db.heats_by_class(class_id).index(heat_info) + 1

        if self.slot_score(race_info, selected_race, False, round_num, eventURL=eventURL):
            message = "Results successfully pushed to MultiGP."
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))

    # Push class results
    def push_results(self, _args):

        def sort_by_id(race_info):
            return race_info.id
        
        self.override_round_heat = False
        self.round_pilots = []
        self.custom_round_number = 1
        self.custom_heat_number = 1

        selected_race = self._rhapi.db.option('mgp_race_id')
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
            selected_results = self._rhapi.db.option('results_select')
            if not selected_results:
                message = "Choose a Results Class to upload results"
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

        if gq_active:
            for rh_class in self._rhapi.db.raceclasses:
                mgp_id = self._rhapi.db.raceclass_attribute_value(rh_class.id, 'mgp_raceclass_id')
                if mgp_id == self._rhapi.db.option('mgp_race_id'):
                    selected_results = rh_class.id
                    break
            else: 
                message = "Imported Global Qualifier class not found... aborting results push"
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                return

        races = self._rhapi.db.races_by_raceclass(selected_results)
        races.sort(key=sort_by_id)

        if self._rhapi.db.raceclass_attribute_value(selected_results, 'zippyq_class') == "1":
            multi_round = False
        else:
            for race_info in races:
                if race_info.round_id > 1:
                    multi_round = True
                    break
            else:
                multi_round = False

        # Upload Results
        for index, race_info in enumerate(races):
            if not self.slot_score(race_info, selected_race, multi_round, index + 1, eventURL=eventURL):
                break

        if gq_active:
            if not self._system_verification.capture_race_results(selected_race):
                message = "Failed to process Global Qualifer race results"
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                return
        else:
            self.push_bracketed_rankings()

        message = "Results successfully pushed to MultiGP."
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))

    # Push class ranking
    def push_bracketed_rankings(self):
        selected_race = self._rhapi.db.option('mgp_race_id')
        selected_class = self._rhapi.db.option('ranks_select')
        
        if not selected_class:
            return

        results_class = self._rhapi.db.raceclass_ranking(selected_class)
        if results_class:
            results = []
            for pilot in results_class["ranking"]:
                multigp_id = int(self._rhapi.db.pilot_attribute_value(pilot['pilot_id'], 'mgp_pilot_id'))
                if multigp_id:
                    class_position = (pilot['position'])
                    result_dict = {"orderNumber" : class_position, "pilotId" : multigp_id}
                    results.append(result_dict)
                else:
                    logger.warning(f'Pilot {pilot["pilot_id"]} does not have a MultiGP Pilot ID. Skipping...')

            push_status = self.multigp.push_overall_race_results(selected_race, results)
            if push_status:
                message = "Rankings pushed to MultiGP"
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            else:
                message = "Failed to push rankings to MultiGP"
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))
    
    #
    # Global Qualifier Verification
    #
    
    # GQ race conditions
    def verify_race(self, args):

        heat_id = args['heat_id']
        heat_info = self._rhapi.db.heat_by_id(heat_id)

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

        if self._rhapi.db.raceclass_attribute_value(heat_info.class_id, 'gq_class') != "1":
            return
        
        if not self._system_verification.get_integrity_check():
            self._rhapi.race.stop()
            message = f"Your system's codebase has been modified and is not approved to run Global Qualifier races"
            self._rhapi.ui.message_alert(self._rhapi.language.__(message))
            return

        if pilot_counter < 3:
            self._rhapi.race.stop()
            message = f"GQ Rules: At least 3 pilots are required to start the race"
            self._rhapi.ui.message_alert(self._rhapi.language.__(message))
            return
        
        class_results = self._rhapi.db.raceclass_results(heat_info.class_id)

        if class_results:
            for pilot in class_results['by_race_time']:
                if pilot['pilot_id'] in heat_pilots and pilot['starts'] >= 10:
                    pilot_info = self._rhapi.db.pilot_by_id(pilot['pilot_id'])
                    message = f"GQ Rules: {pilot_info.callsign} has already completed 10 rounds. Additional rounds will not be included in GQ results."
                    self._rhapi.ui.message_notify(self._rhapi.language.__(message))

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