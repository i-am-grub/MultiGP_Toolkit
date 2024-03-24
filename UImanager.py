import json
from RHUI import UIField, UIFieldType, UIFieldSelectOption

class UImanager():

    def __init__(self):
        self.create_race_import_menu()
        self.create_pilot_import_menu()
        self.create_zippyq_controls()
        self.create_results_export_menu()
        self.create_gq_export_menu()
        self.create_zippyq_return()

    def update_panels(self, args = None):

        if not self._rhapi.db.option('mgp_api_key'):
            return

        if self._rhapi.db.option('mgp_race_id') != '':
            self.show_race_import_menu(False)
            self.show_pilot_import_menu()

            if self._rhapi.db.option('zippyq_races') > 0:
                self.show_zippyq_controls()
                self.show_zippyq_return()

            if self._rhapi.db.option('global_qualifer_event') == '1':
                self.show_gq_export_menu()
            else:
                self.show_results_export_menu()

        else:
            self.show_race_import_menu()
            self.show_pilot_import_menu(False)
            self.show_zippyq_controls(False)
            self.show_zippyq_return(False)
            self.show_results_export_menu(False)
            self.show_gq_export_menu(False)

        self._rhapi.ui.broadcast_ui('format')
        self._rhapi.ui.broadcast_ui('marshal')
        self._rhapi.ui.broadcast_ui('run')

    #
    # Panels
    #

    def create_race_import_menu(self):
        self._rhapi.ui.register_panel('multigp_race_import', f'MultiGP Race Import - {self._chapter_name}', '', order=0)
        self.mgp_event_selector()

        auto_logo = UIField('auto_logo', "Download Logo", desc="Download and set chapter logo from MultiGP on [Import Event]", field_type = UIFieldType.CHECKBOX)
        self._rhapi.fields.register_option(auto_logo, 'multigp_race_import')

        self._rhapi.ui.register_quickbutton('multigp_race_import', 'refresh_events', 'Refresh MultiGP Events', self.mgp_event_selector, args = {'refreshed':True})
        self._rhapi.ui.register_quickbutton('multigp_race_import', 'import_mgp_event', 'Import Event', self.setup_event)

    def show_race_import_menu(self, show = True):
        if show:
            self._rhapi.ui.register_panel('multigp_race_import', f'MultiGP Race Import - {self._chapter_name}', 'format', order=0)
        else:
            self._rhapi.ui.register_panel('multigp_race_import', f'MultiGP Race Import - {self._chapter_name}', '', order=0)

    def create_pilot_import_menu(self):
        self._rhapi.ui.register_panel('multigp_pilot_import', f'MultiGP Pilot Import', '', order=0)
        self._rhapi.ui.register_quickbutton('multigp_pilot_import', 'import_pilots', 'Import Pilots', self.import_pilots)

    def show_pilot_import_menu(self, show = True):
        if show:
            self._rhapi.ui.register_panel('multigp_pilot_import', f'MultiGP Pilot Import', 'format', order=0)
        else:
            self._rhapi.ui.register_panel('multigp_pilot_import', f'MultiGP Pilot Import', '', order=0)

    def create_zippyq_controls(self):
        self._rhapi.ui.register_panel('zippyq_controls', f'ZippyQ Controls', '', order=0)
        
        auto_zippy_text = self._rhapi.language.__('Use Automatic ZippyQ Import')
        auto_zippy = UIField('auto_zippy', auto_zippy_text, desc="Automatically downloads and sets the next ZippyQ round on race finish.", field_type = UIFieldType.CHECKBOX)
        self._rhapi.fields.register_option(auto_zippy, 'zippyq_controls')

        active_import_text = self._rhapi.language.__('Active Race on Import')
        active_import = UIField('active_import', active_import_text, desc="Automatically set the downloaded round as the active race on import", field_type = UIFieldType.CHECKBOX)
        self._rhapi.fields.register_option(active_import, 'zippyq_controls')

        self.zq_class_selector()

        self._rhapi.ui.register_quickbutton('zippyq_controls', 'zippyq_import', 'Import Next ZippyQ Round', self.manual_zippyq)

    def show_zippyq_controls(self, show = True):
        if show:
            self._rhapi.ui.register_panel('zippyq_controls', f'ZippyQ Controls', 'format', order=0)
        else:
            self._rhapi.ui.register_panel('zippyq_controls', f'ZippyQ Controls', '', order=0)

    def create_zippyq_return(self):
        self._rhapi.ui.register_panel('zippyq_return', f'ZippyQ Pack Return', '', order=0)
        self.zq_race_selector()
        self.zq_pilot_selector()

        self._rhapi.ui.register_quickbutton('zippyq_return', 'return_pack', 'Return Pack', self.return_pack)

    def show_zippyq_return(self, show = True):
        if show:
            self._rhapi.ui.register_panel('zippyq_return', f'ZippyQ Pack Return', 'marshal', order=0)
        else:
            self._rhapi.ui.register_panel('zippyq_return', f'ZippyQ Pack Return', '', order=0)

    def create_results_export_menu(self):
        self._rhapi.ui.register_panel('results_controls', f'MultiGP Results Controls', '', order=0)

        push_fpvs_text = self._rhapi.language.__('Upload to FPVScores on Results Push')
        push_fpvs = UIField('push_fpvs', push_fpvs_text, desc="FPVScores Event UUID is optional when your MGP Chapter is linked to an FPVScores Organization", field_type = UIFieldType.CHECKBOX)
        self._rhapi.fields.register_option(push_fpvs, 'results_controls')

        if not self.FPVscores_installed:
            fpv_scores_text = self._rhapi.language.__('FPVScores Event UUID')
            fpv_scores = UIField('event_uuid', fpv_scores_text, desc="Provided by FPVScores", value='', field_type = UIFieldType.TEXT)
            self._rhapi.fields.register_option(fpv_scores, 'results_controls')

        self.results_class_selector()

        self._rhapi.ui.register_quickbutton('results_controls', 'push_results', 'Push Event Results', self.push_results)

    def show_results_export_menu(self, show = True):
        if show:
            self._rhapi.ui.register_panel('results_controls', f'MultiGP Results Controls', 'format', order=0)
        else:
            self._rhapi.ui.register_panel('results_controls', f'MultiGP Results Controls', '', order=0)

    def create_gq_export_menu(self):
        self._rhapi.ui.register_panel('gqresults_controls', f'MultiGP Results Controls', '', order=0)
        self._rhapi.ui.register_quickbutton('gqresults_controls', 'push_gqresults', 'Push Event Results', self.push_results)

    def show_gq_export_menu(self, show = True):
        if show:
            self._rhapi.ui.register_panel('gqresults_controls', f'MultiGP Results Controls', 'format', order=0)
        else:
            self._rhapi.ui.register_panel('gqresults_controls', f'MultiGP Results Controls', '', order=0)

    #
    # Selectors
    #

    # Race selector
    def mgp_event_selector(self, args = None):
        self._mgp_races = self.multigp.pull_races()
        race_list = [UIFieldSelectOption(value = None, label = "")]
        for id, name in self._mgp_races.items():
            race_selection = UIFieldSelectOption(value = id, label = f"({id}) {name}")
            race_list.append(race_selection)

        race_selector = UIField('sel_mgp_race_id', 'MultiGP Event', desc="Event Selection", field_type = UIFieldType.SELECT, options = race_list)
        self._rhapi.fields.register_option(race_selector, 'multigp_race_import')

        if args:
            self._rhapi.ui.broadcast_ui('format')

    # Setup RH Class selector
    def results_class_selector(self, args = None):
        result_class_list = [UIFieldSelectOption(value = "", label = "")]
        rank_class_list = [UIFieldSelectOption(value = "", label = "Let MultiGP Calculate Overall Results")]
        
        for event_class in self._rhapi.db.raceclasses:
            race_class = UIFieldSelectOption(value = event_class.id, label = event_class.name)
            result_class_list.append(race_class)
            rank_class_list.append(race_class)
        
        event_races = json.loads(self._rhapi.db.option('mgp_event_races'))
        
        for index, race in enumerate(event_races):
            results_selector = UIField(f'results_select_{index}', f'Race Data: ({race["mgpid"]}) {race["name"]}', desc="Class holding the race data to be pushed to MultiGP", 
                                    field_type = UIFieldType.SELECT, options = result_class_list)
            self._rhapi.fields.register_option(results_selector, 'results_controls')

            ranking_selector = UIField(f'ranks_select_{index}', f'Overall Results: ({race["mgpid"]}) {race["name"]}', desc="Class holding the Overall Results to be pushed to MultiGP.",
                                       field_type = UIFieldType.SELECT, options = rank_class_list)
            self._rhapi.fields.register_option(ranking_selector, 'results_controls')

        if args:
            self._rhapi.ui.broadcast_ui('format')

    def clear_multi_class_selector(self):

        multi_event = json.loads(self._rhapi.db.option('mgp_event_races'))
        
        for index, event in enumerate(multi_event):
            results_selector = UIField(f'results_select_{index}', '', field_type = UIFieldType.SELECT, options = [])
            self._rhapi.fields.register_option(results_selector, '')

            ranking_selector = UIField(f'ranks_select_{index}', '', field_type = UIFieldType.SELECT, options = [])
            self._rhapi.fields.register_option(ranking_selector, '')

    def zq_race_selector(self, args = None):
        race_list = [UIFieldSelectOption(value = None, label = "")]

        for race in self._rhapi.db.races:
            heat_info = self._rhapi.db.heat_by_id(race.heat_id)
            race_info = UIFieldSelectOption(value = race.id, label = heat_info.name)
            race_list.append(race_info)

        race_selector = UIField('zq_race_select', 'Race Result',field_type = UIFieldType.SELECT, options = race_list)
        self._rhapi.db.option_set('zq_race_select', '')
        self._rhapi.fields.register_option(race_selector, 'zippyq_return')

    def zq_pilot_selector(self, args = None):
        
        if args is not None and args['option'] != 'zq_race_select':
            return
        
        pilot_list = [UIFieldSelectOption(value = None, label = "")]
        race_id = self._rhapi.db.option('zq_race_select')

        if race_id:
            for pilot in json.loads(self._rhapi.db.race_attribute_value(race_id, 'race_pilots')):
                pilot_info = self._rhapi.db.pilot_by_id(pilot)
                pilot_option = UIFieldSelectOption(value = pilot_info.id, label = pilot_info.callsign)
                pilot_list.append(pilot_option)

        race_selector = UIField('zq_pilot_select', 'Pilot', desc = "Prevents the upload of race data for selected Pilot in selected Race. NOTE: Local data is NOT deleted in this process", 
                                field_type = UIFieldType.SELECT, options = pilot_list)
        self._rhapi.fields.register_option(race_selector, 'zippyq_return')

        if args is not None and args['option'] == 'zq_race_select':
            self._rhapi.ui.broadcast_ui('marshal')

    def zq_class_selector(self, args = None):
        result_class_list = []
        zq_count = self._rhapi.db.option('zippyq_races')

        if zq_count > 1:
            for rh_class in self._rhapi.db.raceclasses:
                zq_state = self._rhapi.db.raceclass_attribute_value(rh_class.id, 'zippyq_class')
                if zq_state == '1':
                    result_class_list.append(UIFieldSelectOption(value = rh_class.id, label = rh_class.name))

            zq_class_select = UIField('zq_class_select', 'ZippyQ Class', desc = "Select class to use with [Import Next ZippyQ Round]", 
                                field_type = UIFieldType.SELECT, options = result_class_list)
            self._rhapi.fields.register_option(zq_class_select, 'zippyq_controls')

        elif zq_count == 1:
            zq_class_select = UIField('zq_class_select', '', field_type = UIFieldType.BASIC_INT)
            self._rhapi.fields.register_option(zq_class_select, '')

            for rh_class in self._rhapi.db.raceclasses:
                zq_state = self._rhapi.db.raceclass_attribute_value(rh_class.id, 'zippyq_class')
                if zq_state == '1':
                    self._rhapi.db.option_set('zq_class_select', rh_class.id)
                    break
            else:
                self._rhapi.db.option_set('zq_class_select', 0)

    #
    # Plcaholders
    #
            
    _rhapi = None
    _chapter_name = None
    multigp = None
            
    def setup_event(self, _args = None):
        pass

    def import_pilots(self, _args = None):
        pass

    def manual_zippyq(self, _args = None):
        pass

    def push_results(self, _args = None):
        pass

    def return_pack(self, _args = None):
        pass