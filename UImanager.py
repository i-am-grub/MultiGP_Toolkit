import json
from RHUI import UIField, UIFieldType, UIFieldSelectOption

class UImanager():

    _rhapi = None

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

            if self._rhapi.db.option('zippyq_event') == '1':
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

    #
    # Panels
    #

    def create_race_import_menu(self):
        self._rhapi.ui.register_panel('multigp_race_import', f'MultiGP Race Import - {self._chapter_name}', '', order=0)
        self.mgp_race_selector()
        self._rhapi.ui.register_quickbutton('multigp_race_import', 'refresh_events', 'Refresh MultiGP Races', self.mgp_race_selector, args = {'refreshed':True})
        self._rhapi.ui.register_quickbutton('multigp_race_import', 'import_class', 'Import Race', self.import_class)

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

        zippyq_round_text = self._rhapi.language.__('ZippyQ round number')
        zippyq_round = UIField('zippyq_round', zippyq_round_text, desc="Round to be imported by [Import ZippyQ Round]", field_type = UIFieldType.BASIC_INT, value = 1)
        self._rhapi.fields.register_option(zippyq_round, 'zippyq_controls')

        self._rhapi.ui.register_quickbutton('zippyq_controls', 'zippyq_import', 'Import ZippyQ Round', self.manual_zippyq)

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

        self.results_class_selector()

        push_fpvs_text = self._rhapi.language.__('Upload to FPVScores on Results Push')
        push_fpvs = UIField('push_fpvs', push_fpvs_text, desc="FPVScores Event UUID is optional when your MGP Chapter is linked to an FPVScores Organization", field_type = UIFieldType.CHECKBOX)
        self._rhapi.fields.register_option(push_fpvs, 'results_controls')

        if not self.FPVscores_installed:
            fpv_scores_text = self._rhapi.language.__('FPVScores Event UUID')
            fpv_scores = UIField('event_uuid', fpv_scores_text, desc="Provided by FPVScores", value='', field_type = UIFieldType.TEXT)
            self._rhapi.fields.register_option(fpv_scores, 'results_controls')

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
    def mgp_race_selector(self, args = None):
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

        rank_descript = "Optional: Class holding the rankings to be pushed to MultiGP as the Overall Results. Active if the class is using a ranking method"
        ranking_selector = UIField('ranks_select', 'Rankings Class', desc=rank_descript, field_type = UIFieldType.SELECT, options = class_list)
        self._rhapi.fields.register_option(ranking_selector, 'results_controls')

        if args:
            self._rhapi.ui.broadcast_ui('format')

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