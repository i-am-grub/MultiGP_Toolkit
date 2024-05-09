import logging
import json
import requests
import gevent

logger = logging.getLogger(__name__)

class multigpAPI():
    
    # https://www.multigp.com/apidocumentation/
    _apiKey = None
    _chapterId = None

    def _request_and_download(self, url, json_request):
        header = {'Content-type': 'application/json'}

        count = 0
        mex_retries = 10
        while (count < mex_retries):
            count += 1
            try:
                response = requests.post(url, headers=header, data=json_request)
            except requests.exceptions.ConnectionError:
                logger.warning(f"Trying to establish connection to MultiGP - Attempt {count}/{mex_retries}")
                if count >= mex_retries:
                    returned_json = {'status' : False}
                    return returned_json
                else:
                    gevent.sleep(5)
            else:
                break

        try:
            returned_json = json.loads(response.text)
        except AttributeError:
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
            races = {}

            for race in returned_json['data']:
                races[race['id']] = race['name']

            return races
        else:
            return None
    
    def pull_race_data(self, race_id:str):

        url = f'https://www.multigp.com/mgp/multigpwebservice/race/view?id={race_id}'
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

    def pull_additional_rounds(self, race_id:str, round:int):
        url = f'https://www.multigp.com/mgp/multigpwebservice/race/getAdditionalRounds?id={race_id}&startFromRound={round}'
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
    def push_slot_and_score(self, race_id:str, round:int, heat:int, slot:int, race_data:dict):

        url = f'https://www.multigp.com/mgp/multigpwebservice/race/assignslot/id/{race_id}/cycle/{round}/heat/{heat}/slot/{slot}'
        data = {
            'data' : race_data,
            'apiKey' : self._apiKey
        }

        json_request = json.dumps(data)
        returned_json = self._request_and_download(url, json_request)

        return returned_json['status']

    # Final results from brackets
    def push_overall_race_results(self, race_id:str, bracket_results:list):

        url = f'https://www.multigp.com/mgp/multigpwebservice/race/captureOverallRaceResult?id={race_id}'
        data = {
            'data' : {
                'raceId' : race_id,
                'bracketResults' : bracket_results 
            },
            'apiKey' : self._apiKey
        }
        json_request = json.dumps(data)
        returned_json = self._request_and_download(url, json_request)

        return returned_json['status']
