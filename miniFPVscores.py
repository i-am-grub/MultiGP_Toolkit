# This file is a modified version of
# https://github.com/FPVScores/FPVScores/blob/d6bd2ab96bf44e637726e66233f6acfcbb7b5ec5/fpvscores/__init__.py

import logging
import requests
import json
import gevent
from data_export import DataExporter
from sqlalchemy import inspect
from sqlalchemy.ext.declarative import DeclarativeMeta

logger = logging.getLogger(__name__)

#
# FPVScores interface
#

def postFPVS(url, json_data):
    headers = {'Authorization' : 'rhconnect', 'Accept' : 'application/json', 'Content-Type' : 'application/json'}

    count = 0
    mex_retries = 5
    while (count < mex_retries):
        count += 1
        try:
            response = requests.post(url, headers=headers, data=json_data)
        except requests.exceptions.ConnectionError:
            logger.warning(f"Trying to establish connection to FPVScores - Attempt {count}/{mex_retries}")
            if count >= mex_retries:
                return None
            else:
                gevent.sleep(5)
        else:
            return response

def getURLfromFPVS(rhapi, uuid):

    if not uuid:
        return None

    rhapi.ui.message_notify(rhapi.__('Getting event URL from FPVScores.'))
    url = 'https://api.fpvscores.com/rh/0.0.2/?action=fpvs_get_event_url'
    json_data = json.dumps({"event_uuid": uuid})
    r = postFPVS(url, json_data)
    if r and r.status_code == 200:
        if r.text == 'no event found':
           rhapi.ui.message_notify(rhapi.__('Event URL not found. Please check the entered UUID.'))
           return None
        else:
            rhapi.ui.message_notify(rhapi.__('Event URL found.'))
            logger.info(f'FPVScores event URL: {r.text}')
            return r.text
    else:
        return None
    
def runPushMGP(rhapi):

    rhapi.ui.message_notify(rhapi.__('Uploading to FPVScores...'))
    url = 'https://api.fpvscores.com/rh/0.0.3/?action=mgp_push'
    input_data = rhapi.io.run_export('JSON_FPVScores_MGP_Upload')
    json_data =  input_data['data']
    r = postFPVS(url, json_data)
    if r and r.status_code == 200:
        data = json.loads(r.text)
        if data["status"] == "error":
            return data["message"], None
        elif data["status"] == 'success':
            return data["message"], data["event_uuid"]
        else:
            return "Failed to push to FPVScores", None

def linkedMGPOrg(rhapi):

    url = 'https://api.fpvscores.com/rh/0.0.3/?action=mgp_api_check'
    json_data = json.dumps({"mgp_api_key": rhapi.db.option('mgp_api_key')})
    r = postFPVS(url, json_data)
    if r and r.status_code == 200:
        data = json.loads(r.text)
        return data["exist"] == "true"
    else:
        return None

#
# Payload Generation
#

def register_handlers(args):
    if 'register_fn' in args:
        for exporter in discover():
            args['register_fn'](exporter)

def discover(*args, **kwargs):
    return [
        DataExporter(
            'JSON FPVScores MGP Upload',
            write_json,
            assemble_fpvscoresUpload
        )
    ]

def write_json(data):
    payload = json.dumps(data, indent='\t', cls=AlchemyEncoder)

    return {
        'data': payload,
        'encoding': 'application/json',
        'ext': 'json'
    }

def assemble_fpvscoresUpload(rhapi):
    payload = {}
    payload['import_settings'] = 'upload_FPVScores'
    payload['Pilot'] = assemble_pilots_complete(rhapi)
    payload['Heat'] = assemble_heats_complete(rhapi)
    payload['HeatNode'] = assemble_heatnodes_complete(rhapi)
    payload['RaceClass'] = assemble_classes_complete(rhapi)
    payload['GlobalSettings'] = assemble_settings_complete(rhapi)
    payload['FPVScores_results'] = rhapi.eventresults.results

    return payload

def assemble_pilots_complete(rhapi):
    payload = rhapi.db.pilots
    for pilot in payload:
        pilot.mgpid = rhapi.db.pilot_attribute_value(pilot.id, 'mgp_pilot_id')
    
    return payload

def assemble_heats_complete(rhapi):
    return rhapi.db.heats

def assemble_heatnodes_complete(rhapi):
    payload = rhapi.db.slots

    freqs = json.loads(rhapi.race.frequencyset.frequencies)

    for slot in payload:
        slot.node_frequency_band = freqs['b'][slot.node_index]
        slot.node_frequency_c = freqs['c'][slot.node_index]
        slot.node_frequency_f = freqs['f'][slot.node_index]

    return payload

def assemble_classes_complete(rhapi):
    return rhapi.db.raceclasses

def assemble_settings_complete(rhapi):
    return rhapi.db.options

class AlchemyEncoder(json.JSONEncoder):
    def default(self, obj):
        custom_vars = ['node_frequency_band','node_frequency_c','node_frequency_f', 'mgpid']
        if isinstance(obj.__class__, DeclarativeMeta):
            mapped_instance = inspect(obj)
            fields = {}
            for field in dir(obj): 
                if field in [*mapped_instance.attrs.keys(), *custom_vars]:
                    data = obj.__getattribute__(field)
                    if field != 'query' \
                        and field != 'query_class':
                        try:
                            json.dumps(data)
                            if field == 'frequencies':
                                fields[field] = json.loads(data)
                            elif field == 'enter_ats' or field == 'exit_ats':
                                fields[field] = json.loads(data)
                            else:
                                fields[field] = data
                        except TypeError:
                            fields[field] = None

            return fields

        return json.JSONEncoder.default(self, obj)