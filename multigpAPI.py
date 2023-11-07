import logging
import json
import requests

logger = logging.getLogger(__name__)

class multigpAPI():
    
    # https://www.multigp.com/apidocumentation/
    _apiKey = None
    _chapterId = None
    _events_keys = {}

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
            chapterName = returned_json['chapterName']
            logger.info(chapterName)
            return chapterName
        else:
            return None

    #
    # Data from MultiGP
    #

    def pull_races(self):

        url = f'https://www.multigp.com/mgp/multigpwebservice/race/listForChapter?chapterId={self._chapterId}'
        data = {
            'apiKey' : self._apiKey
        }
        json_request = json.dumps(data)
        returned_json = self._request_and_download(url, json_request)

        if returned_json['status']:
            races = []
            self._events_keys = {}

            for race in returned_json['data']:
                races.append(race['name'])
                self._events_keys[race['name']] = race['id']

            return races
        else:
            return None
    
    def pull_race_data(self, selected_race:str):

        url = f'https://www.multigp.com/mgp/multigpwebservice/race/view?id={self._events_keys[selected_race]}'
        data = {
            'apiKey' : self._apiKey
        }
        json_request = json.dumps(data)
        returned_json = self._request_and_download(url, json_request)

        if returned_json['status']:
            logger.info(f"Pulled data for {returned_json['data']['chapterName']}")
            return returned_json['data']
        else:
            return None

    def pull_additional_rounds(self, selected_race:str, round:int):
        url = f'https://www.multigp.com/mgp/multigpwebservice/race/getAdditionalRounds?id={self._events_keys[selected_race]}&startFromRound={round}'
        data = {
            'apiKey' : self._apiKey
        }
        json_request = json.dumps(data)
        returned_json = self._request_and_download(url, json_request)

        if returned_json['status']:
            return returned_json['data']
        else:
            return None

    #
    # Data to MultiGP
    #

    # Capture pilots times and scores
    def push_slot_and_score(self, selected_race:str, round:int, heat:int, slot:int, race_data:dict):

        url = f'https://www.multigp.com/mgp/multigpwebservice/race/assignslot/id/{self._events_keys[selected_race]}/cycle/{round}/heat/{heat}/slot/{slot}'
        data = {
            'data' : race_data,
            'apiKey' : self._apiKey
        }

        json_request = json.dumps(data)
        returned_json = self._request_and_download(url, json_request)

        return returned_json['status']

    # Final results from brackets
    def push_overall_race_results(self, selected_race:str, bracket_results:list):

        url = f'https://www.multigp.com/mgp/multigpwebservice/race/captureOverallRaceResult?id={self._events_keys[selected_race]}'
        data = {
            'data' : {
                'raceId' : self._events_keys[selected_race],
                'bracketResults' : bracket_results 
            },
            'apiKey' : self._apiKey
        }
        json_request = json.dumps(data)
        returned_json = self._request_and_download(url, json_request)

        return returned_json['status']
    
    def finalize_results(self, selected_race:str):

        url = f'https://www.multigp.com/mgp/multigpwebservice/race/finalize?id={self._events_keys[selected_race]}'
        data = {
            'apiKey' : self._apiKey
        }
        json_request = json.dumps(data)
        returned_json = self._request_and_download(url, json_request)

        return returned_json['status']
