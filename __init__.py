import logging
import json
import requests
import RHUtils

logger = logging.getLogger(__name__)

def initialize(**kwargs):

    manager = multigpAPI(kwargs['RHAPI'])

    if 'RHAPI' in kwargs:
        kwargs['RHAPI'].register_ui_panel("multigp", "MultiGP", "format")
        kwargs['RHAPI'].register_general_setting("apiKey", "MultiGP API Key", "multigp")
        kwargs['RHAPI'].register_quickbutton("multigp", "get_race", "Find Races", manager.get_races)

class multigpAPI():

    _apiKey = None
    _chapterId = None
    _chapterName = None
    _avaliable_events = []
    _event_keys = {}

    def __init__(self, RHAPI):
        self._RHAPI = RHAPI

    def _set_apiKey(self):
        self._apiKey = self._RHAPI.get_setting("apiKey")
        logger.info("API key set to {}".format(self._apiKey))

    def _request_and_download(self, url, json_request):
        header = {'Content-type': 'application/json'}
        response = requests.post(url, headers=header, data=json_request, timeout=1.5)

        returned_json = json.loads(response.text)

        if returned_json["status"]:
            logger.info("Server request was sucessful")
        else:
            logger.error("Server request failed")
            logger.debug("Server status code: {}".format(response.status_code))
        
        return returned_json

    def _get_chapter(self):
        url = 'https://www.multigp.com/mgp/multigpwebservice/chapter/findChapterFromApiKey'
        data = {
            "apiKey" : self._apiKey
        }
        json_request = json.dumps(data)
        returned_data = self._request_and_download(url, json_request)

        self._chapterId = returned_data["chapterId"]
        self._chapterName = returned_data["chapterName"]

        logger.debug("Chapter ID was found to be {}".format(self._chapterId))
        logger.debug("Chapter Name was found to be {}".format(self._chapterName))


    def get_races(self):    
        self._set_apiKey()
        self._get_chapter()

        url = 'https://www.multigp.com/mgp/multigpwebservice/race/listForChapter?chapterId=' + self._chapterId
        data = {
            "apiKey" : self._apiKey
        }
        json_request = json.dumps(data)
        returned_data = self._request_and_download(url, json_request)["data"]

        self._avaliable_events = []
        self._event_keys = {}

        for race in returned_data:
            self._avaliable_events.append(race["name"])
            self._event_keys[race["name"]] = race["id"]