import logging
import json
import requests
import RHUtils
from RHUI import UIField, UIFieldType, UIFieldSelectOption

logger = logging.getLogger(__name__)

def initialize(**kwargs):

    if 'rhapi' in kwargs:
        rhapi = kwargs['rhapi']

        ui = uiManager(rhapi)

        multigp_id = UIField(name = 'multigp_id', label = 'MultiGP Pilot ID', field_type = UIFieldType.BASIC_INT)
        rhapi.fields.register_pilot_attribute(multigp_id)

        rhapi.ui.register_panel('multigp', 'MultiGP', 'format', order=0)

        api_setting = UIField(name = 'apiKey', label = 'Chapter API Key', field_type = UIFieldType.TEXT)
        rhapi.fields.register_option(api_setting, 'multigp')

        rhapi.ui.register_quickbutton('multigp', 'submit_apikey', 'Verify Key', lambda: setup_chapter(rhapi, ui))

        
def setup_chapter(rhapi, uiManager):
    multigp.set_apiKey(rhapi.db.option('apiKey'))
    chapter_name = multigp.fetch_chapter()
    if chapter_name:
        rhapi.ui.message_notify(chapter_name + " successfully verified. Please refresh the page.")
        uiManager.setup_ui()

    else:
        rhapi.ui.message_notify("Check API Key or Internet Connection")


def import_pilots(rhapi):

    selected_race = rhapi.db.option('race_select')

    logger.info(selected_race)

    multigp.fetch_race_data(selected_race)
    
    # Eventually implment a check to see if pilots are already in database
    for pilot in multigp.get_pilots():

        pilot_name = pilot['firstName'] + " " + pilot['lastName']
        rhapi.db.pilot_add(name = pilot_name, callsign = pilot['userName'])

        # Add in MultiGP PilotID
        #rhapi.db.pilot_attribute_value(pilot_name, 'multigp_id', pilot['pilotId'])

    rhapi.ui.message_notify("Pilots imported. Please refresh the page.")

# Can't implemenmt until a solution for not searching by RH pilot id is known
def push_results(rhapi):
    pass

# Makes sure each option can't be registered more than once.
class uiManager():

    rhapi = None
    _races_set = False
    _pilot_import_set = False
    _race_class_set = False
    _push_results_set = False

    def __init__(self, rhapi):
        self.rhapi = rhapi

    def setup_races(self):
        if self._races_set is False:
            multigp.fetch_races()

            race_list = []

            for race_label in multigp.get_races():
                race = UIFieldSelectOption(value = race_label, label = race_label)
                race_list.append(race)

            race_selector = UIField('race_select', 'Select Race', field_type = UIFieldType.SELECT, options = race_list)

            self.rhapi.fields.register_option(race_selector, 'multigp')

            self._races_set = True

    def setup_pilot_import(self):
        if self._pilot_import_set is False:
            self.rhapi.ui.register_quickbutton('multigp', 'import_pilots', 'Import Pilots', lambda: import_pilots(self.rhapi))
            self._pilot_import_set = True

    def setup_race_class(self):

        if self._race_class_set is False:
                
            class_list = []

            for race_class in self.rhapi.db.raceclasses():
                classs = UIFieldSelectOption(value = race_class, label = race_class)
                class_list.append(classs)

        class_selector = UIField('class_select', 'Select Class with Final Results', field_type = UIFieldType.SELECT, options = class_list)

        self.rhapi.fields.register_option(class_selector, 'multigp')

        self._race_class_set = True
    
    def setup_push_results(self):
        if self._push_results_set is False:
            self.rhapi.ui.register_quickbutton('multigp', 'push_results', 'Push Results', lambda: push_results(self.rhapi))
            self._push_results_set = True

    def setup_ui(self):
        self.setup_races()
        self.setup_pilot_import()
        self.setup_race_class()
        #self.setup_push_results()

# MultiGP Handler
class multigpAPI():

    _apiKey = None
    _chapterId = None
    _chapterName = None
    _avaliable_events = []
    _events_keys = {}
    _event_name = None
    _event_description = None
    _event_pilots = []

    def set_apiKey(self, apiKey):
        self._apiKey = apiKey

    def _request_and_download(self, url, json_request):
        header = {'Content-type': 'application/json'}
        response = requests.post(url, headers=header, data=json_request, timeout=1.5)

        try:
            returned_json = json.loads(response.text)
        except:
            returned_json = {'status' : False}
        finally:
            return returned_json

    def fetch_chapter(self):
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
            return self._chapterName
        
        else:
            logger.info("Check API Key or Internet Connection")
            return None


    def fetch_races(self):

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

            return returned_json['data']
        
        else:
            logger.info("Check API Key or Internet Connection")
            return None
        
    def get_races(self):
        return self._avaliable_events
    
    def fetch_race_data(self, selected_race:str):

        url = 'https://www.multigp.com/mgp/multigpwebservice/race/viewSimple?id=' + self._events_keys[selected_race]
        data = {
            'apiKey' : self._apiKey
        }
        json_request = json.dumps(data)
        returned_json = self._request_and_download(url, json_request)

        if returned_json['status']:
            self._event_name = returned_json['data']['name']
            self._event_description = returned_json['data']['description']
            self._event_pilots = returned_json['data']['entries']
            return returned_json['data']
        
        else:
            logger.info("Check API Key or Internet Connection")
            return None
    
    def get_pilots(self):
        return self._event_pilots

    def push_final_results(self, selected_race:str, rankings):

        url = 'https://www.multigp.com/mgp/multigpwebservice/race/captureOverallRaceResult?id=' + self._events_keys[selected_race]
        data = {
            'data' : {
                'raceId' : self._events_keys[selected_race],
                'bracketResults' : rankings,
            },
            'apiKey' : self._apiKey
        }
        json_request = json.dumps(data)
        returned_json = self._request_and_download(url, json_request)

        if returned_json['status']:
            logger.info(returned_json['statusDescription'])
        else:
            logger.info("Check API Key or Internet Connection")
            return None

multigp = multigpAPI()