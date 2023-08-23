# https://www.multigp.com/apidocumentation/

import logging
import json
import requests

logger = logging.getLogger(__name__)

class multigpAPI():

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
    _zippyqIterator = None
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
            self._zippyqIterator = returned_json['data']['zippyqIterator']

        return returned_json['status']
    
    def get_scoringformat(self):
        return self._scoringFormat
    
    def get_zippyqIterator(self):
        return self._zippyqIterator
    
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

    # Notify pilots their heat is about to start
    def start_heat(self, selected_race:str, round:int, heat:int):

        url = 'https://www.multigp.com/mgp/multigpwebservice/race/startHeat?id=1' + self._events_keys[selected_race]
        data = {
            'data' : {
                'cycle ' : round,
                'heat ' : heat
            },
            'sessionId' : self._sessionID,
            'apiKey' : self._apiKey
        }
        json_request = json.dumps(data)
        returned_json = self._request_and_download(url, json_request)

        return returned_json['status']

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
            'sessionId' : self._sessionID,
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
    
    # Global Qualifier results
    def push_regional_race_results(self, selected_race:str, results:list):

        url = 'https://www.multigp.com/mgp/multigpwebservice/race/captureOverallRaceResult?id=' + self._events_keys[selected_race]
        data = {
            'data' : {
                'raceId' : self._events_keys[selected_race],
                'results' : results,
                    # [
                        # {
                        # orderNumber : Number,
                        # pilotId : Number,
                        # totalLaps : Number,
                        # totalTime : Double,
                        # tiebreaker : String,
                        # roundResults:
                            # [
                                # {
                                # roundNumber : Number, between 1 and 10
                                # isUsed : Boolean,
                                # totalLaps : Number,
                                # totalTime : Double
                                # }
                            # ]
                        # }
                    # ]
            },
            'sessionId' : self._sessionID,
            'apiKey' : self._apiKey
        }
        json_request = json.dumps(data)
        returned_json = self._request_and_download(url, json_request)

        return returned_json['status']
    
    def finalize_results(self, selected_race:str):

        url = 'https://www.multigp.com/mgp/multigpwebservice/race/finalize?id=' + self._events_keys[selected_race]
        data = {
            'sessionId' : self._sessionID,
            'apiKey' : self._apiKey
        }
        json_request = json.dumps(data)
        returned_json = self._request_and_download(url, json_request)

        return returned_json['status']