# This file is a stripped down version of
# https://github.com/FPVScores/FPVScores/blob/d6bd2ab96bf44e637726e66233f6acfcbb7b5ec5/fpvscores/__init__.py

import logging
import requests
import json
from data_export import DataExporter
from sqlalchemy import inspect
from sqlalchemy.ext.declarative import DeclarativeMeta

logger = logging.getLogger(__name__)

#
# FPVScores interface
#

def getURLfromFPVS(rhapi):

    if not rhapi.db.option('event_uuid'):
        return None

    rhapi.ui.message_notify(rhapi.__('Getting event URL from FPVScores.'))
    url = 'https://api.fpvscores.com/rh/0.0.2/?action=fpvs_get_event_url'
    json_data = '{"event_uuid":"' + rhapi.db.option('event_uuid') + '"}'
    headers = {'Authorization' : 'rhconnect', 'Accept' : 'application/json', 'Content-Type' : 'application/json'}
    r = requests.post(url, data=json_data, headers=headers)
    if r.status_code == 200:
        if r.text == 'no event found':
           rhapi.ui.message_notify(rhapi.__('Event URL not found. Please check the entered UUID.'))
           return None
        else:
            rhapi.ui.message_notify(rhapi.__('Event URL found.'))
            logger.info(f'FPVScores event URL: {r.text}')
            return r.text
    else:
        return None

def uploadToFPVS(rhapi):
    
    if not rhapi.db.option('event_uuid'):
        rhapi.ui.message_notify(rhapi.__('Please enter a FPVScores Event UUID'))
        return

    rhapi.ui.message_notify(rhapi.__('Event data upload to FPVScores started.'))
    input_data = rhapi.io.run_export('JSON_FPVScores_Upload')
    json_data =  input_data['data']
    url = 'https://api.fpvscores.com/rh/0.0.2/?action=rh_push'
    headers = {'Authorization' : 'rhconnect', 'Accept' : 'application/json', 'Content-Type' : 'application/json'}
    r = requests.post(url, data=json_data, headers=headers)
    if r.status_code == 200:
        if r.text == 'no import!':
            rhapi.ui.message_notify(rhapi.__('No import data found, add data (pilots, classes, heats) first.'))
        elif r.text == 'no event found':
            rhapi.ui.message_notify(rhapi.__('No event found - Check your event UUID on FPVScores.com.'))
        elif r.text == 'import succesfull':
            rhapi.ui.message_notify(rhapi.__('Uploaded data successfully.'))
        else:
            rhapi.ui.message_notify(r.text)

def runClearFPVS(rhapi):
    
    if not rhapi.db.option('event_uuid'):
        rhapi.ui.message_notify(rhapi.__('Please enter a FPVScores Event UUID'))
        return

    rhapi.ui.message_notify(rhapi.__('Clear FPVScores event data request has been send.'))
    url = 'https://api.fpvscores.com/rh/0.0.2/?action=rh_clear'
    json_data = '{"event_uuid":"' + rhapi.db.option('event_uuid') + '"}'
    headers = {'Authorization' : 'rhconnect', 'Accept' : 'application/json', 'Content-Type' : 'application/json'}
    r = requests.post(url, data=json_data, headers=headers)
    if r.status_code == 200:
        if r.text == 'no event found':
            rhapi.ui.message_notify(rhapi.__('No event found. Check your event UUID on FPVScores.com.'))
        elif r.text == 'Data Cleared':
            rhapi.ui.message_notify(rhapi.__('Event data is cleared on FPVScores.com.'))
        else:
            rhapi.ui.message_notify(r.text)

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
            'JSON FPVScores Upload',
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
    
        try:
            pilot.fpvsuuid = rhapi.db.pilot_attribute_value(pilot.id, 'fpvs_uuid')
        except:
            pilot.fpvsuuid = None  
    
        try:
            pilot.country = rhapi.db.pilot_attribute_value(pilot.id, 'country')
        except:
            pilot.country = None
    
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
        custom_vars = ['fpvsuuid','country','node_frequency_band','node_frequency_c','node_frequency_f']
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