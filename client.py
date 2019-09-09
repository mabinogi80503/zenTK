from colorama import Fore
from parsimonious.grammar import Grammar
from parsimonious.exceptions import ParseError, VisitationError
from parsimonious.nodes import NodeVisitor

from api import APICallFailedException
from database import UserLibrary
from datatype import EventInfo, Resources, SwordTeam, TsukiEventInfo
from login import DMMAuthenticator
from preferences import preferences_mgr

app_config = preferences_mgr.get("system")
battle_config = preferences_mgr.get("battle")
buildin_command = ["ls", "battle", "event", "forge", "swap", "sakura"]


class ClientCreateFailException(Exception):
    pass


class TkrbClient(object):
    def __init__(self, api):
        self.api = api
        self.user_data = UserLibrary(self.api)
        self.resources = Resources(api)
        self.event_info = TsukiEventInfo(api)
        self.teams = {
            "1": SwordTeam(self.api,
                           self.user_data,
                           "1"),
            "2": SwordTeam(self.api,
                           self.user_data,
                           "2"),
            "3": SwordTeam(self.api,
                           self.user_data,
                           "3"),
            "4": SwordTeam(self.api,
                           self.user_data,
                           "4")
        }
        self.handler = {
            "ls": self._handle_list,
            "battle": self._handle_battle,
            "event": self._handle_event,
            "sakura": self._handle_sakura,
        }
        self.init_first()

    @classmethod
    def create(cls, account, password):
        api = DMMAuthenticator(account, password).login()
        if not api:
            raise ClientCreateFailException()

        return cls(api)

    def init_first(self):
        try:
            self.api.start()
            self.home()
            self.api.party_list()
            print(Fore.GREEN + "初始化成功")

            self.resources.show()
        except APICallFailedException as e:
            print(Fore.RED + "初始化失敗")
            print(e)

    def home(self):
        # ret = self.api.home()
        self.api.home()

        # num_missions = ret.get("mission")
        # if num_missions:
        #     print("有 " + Fore.YELLOW + f"{num_missions}" + Fore.RESET + " 個任務尚未領取！")

        # print("內番檢查中...", end="")
        # duty = ret.get("dutty")
        # if duty and isinstance(duty, dict):
        #     from common import get_datime_diff_from_now
        #     if get_datime_diff_from_now(duty.get("finished_at")).total_seconds() < 0:
        #         if not self.api.complete_duty()["status"]:
        #             print(Fore.YELLOW + "完成！")
        #     else:
        #         print(Fore.YELLOW + "仍舊努力中～")
        # else:
        #     print(Fore.YELLOW + "無內番！")

    # 檢查隊伍狀況，可行就回傳 team ref，否則就回傳 None
    def _check_team_status(self, team_id):
        team_ref = self.teams[str(team_id)]
        if not team_ref.available():
            return None

        # 確保最疲勞的刀劍男士被換成隊長
        team_ref.make_min_fatigue_be_captain()
        return team_ref

    # 完成戰鬥前的檢驗，如果可行就回傳 team ref，否則 None
    def _check_before_battle(self, team_id, event=False):
        self.api.party_list()

        # 若是活動，先檢查手形
        if event:
            self.api.sally()
            if not self.event_info.have_event:
                return None

            # if self.event_info.rest_passcard == 0:
            #     try:
            #         self.recover_the_passcard(self.event_info.event_id, self.event_info.rest_passcard_max)
            #     except APICallFailedException as api_failed_error:
            #         print(api_failed_error)
            #         return None

        team_ref = self._check_team_status(team_id)
        return team_ref

    def team_sakura(self, episode, field, team_id):
        for idx in range(1, 7):
            self.sakura(episode, field, team_id, idx)

    def sakura(self, episode, field, team_id, mem_idx):
        if int(team_id) < 0 or int(team_id) > 4:
            return

        if int(mem_idx) < 1 or int(mem_idx) > 6:
            return

        team_ref = self.teams[str(team_id)]
        if not team_ref.available:
            print("該隊沒空ㄏㄏ")
            return

        mem_serial = team_ref.swords[str(mem_idx)]
        if not mem_serial:
            print("沒有這位QQ")
            return

        team_record = team_ref.swords.copy()
        team_ref.clear()

        team_ref.set_sword(1, mem_serial)
        if team_ref.captain_serial_id == mem_serial:
            print("設置隊長成功")
        else:
            print("這不該是隊長QQ")
        count = 0

        while int(team_ref.sword_refs[0].fatigue) < 80 and count < 5:
            count = count + 1
            self.battle(team_id, episode, field, sakura=True)
        for idx in range(1, 7):
            team_ref.set_sword(idx, team_record[str(idx)])

    def battle(self, team_id, episode, field, sakura=False):
        team_ref = self._check_before_battle(team_id)
        if not team_ref:
            return
        from battle import CommonBattleExecutor
        executor = CommonBattleExecutor(self.api, team_ref, episode, field, sakura)
        executor.play()
        self.home()

    def event_battle(self, team_id, field=1):
        team_ref = self._check_before_battle(team_id, event=True)
        if not team_ref:
            return

        # 開始戰鬥
        # from battle import HitakaraBattleExecutor
        # executor = HitakaraBattleExecutor(self.api, team_ref, self.event_info.event_id, field)
        # executor.play()
        from battle import TsukiExecutor
        executor = TsukiExecutor(self.api,
                                 team_ref,
                                 self.event_info.event_id,
                                 self.event_info.field_id,
                                 self.event_info.layer_field)
        executor.play()
        self.home()

    def recover_the_passcard(self, event_id, num):
        ret = self.api.recover_event_cost(event_id, num)
        if not ret["status"]:
            print("補充手形 " + Fore.CYAN + f"{num}" + Fore.RESET + "個成功！")
        else:
            print(Fore.RED + "補充手形失敗！")

    def list_team(self, list_all=False, team_id=None):
        self.api.party_list()

        if list_all:
            for team in self.teams.values():
                team.show()
        else:
            if team_id:
                team = self.teams[team_id]
                team.show()

    def swap_teams(self, team1, team2):
        try:
            self.api.swap_team(team1, team2)
        except APICallFailedException:
            print(Fore.RED + f"交換 {team1} 與 {team2} 發生錯誤！")

    def list_equipments(self):
        pass

    def forge_build(self, slot_no, steel, charcoal, coolant, files, use_assist=False):
        ret = self.api.forge_start(slot_no, steel, charcoal, coolant, files, use_assist)

        if not ret["status"]:
            print(f"開始在第 " + Fore.YELLOW + f"{slot_no}" + Fore.RESET + " 格刀爐上凌虐刀匠！")
        else:
            print(Fore.RED + "刀爐不能使用或是有東西佔位子！")

    def execute(self, command, options):
        if command == "exit":
            from sys import exit
            exit(0)

        try:
            print("execute!")
            self.handler[command](options)
        except KeyError as err:
            print("Fuck !" + str(err))

    def _handle_list(self, options):
        team = options.get("-p", "*")

        if team == "*":
            self.list_team(list_all=True)
        else:
            self.list_team(team_id=team)

    def _handle_battle(self, options):
        times = int(options["-t"])
        team_id = int(options["-p"])
        episode = int(options["episode"])
        field = int(options["field"])
        interval = int(battle_config.get("battle_interval"))

        from time import sleep
        for count in range(times):
            self.battle(team_id, episode, field)

            if interval > 0.0 and count < times - 1:
                print(f"等待 {interval} 秒...")
                sleep(interval)

    def _handle_event(self, options):
        times = int(options["-t"])
        team_id = int(options["-p"])
        interval = int(battle_config.get("battle_interval"))

        from time import sleep
        for count in range(times):
            self.event_battle(team_id)

            if interval > 0.0 and count < times - 1:
                print(f"等待 {interval} 秒...")
                sleep(interval)

    def _handle_sakura(self, options):
        team_id = int(options["-p"])
        episode = int(options["episode"])
        field = int(options["field"])
        mem_id = options.get("-m", None)

        if mem_id:
            self.sakura(episode, field, team_id, mem_id)
        else:
            self.team_sakura(episode, field, team_id)

    def _handle_forge_cmd(self, args):
        if len(args) == 0:
            print(Fore.RED + "命令錯誤！")

        subcmd = args[0]
        if subcmd == "build":
            if len(args[1:]) != 5:
                print(Fore.RED + "命令錯誤！")
            else:
                self.forge_build(int(args[1]), int(args[2]), int(args[3]), int(args[4]), int(args[5]))

    def _handle_swap_cmd(self, args):
        subcmd = args[0]
        if subcmd == "s":
            team = args[1]
            index = args[2]
            serial = args[3]

            self.teams[team].set_sword(index, serial)
        elif subcmd == "t":
            team1 = args[1]
            team2 = args[2]
            self.swap_teams(team1, team2)
        elif subcmd == "c":
            team = args[1]
            self.teams[team].clear()


grammer = r"""
    command = mutable / immutable

    immutable = exit / ls / _
    mutable = battle / event / sakura

    field = _ ~r"(\d+)-(\d+)" _
    value_opts = _ value_opts_name _ value_opts_value _
    value_opts_name = "-m" / "-p" / "-t"
    value_opts_value = ~r"\w+"

    battle_opts = field / value_opts+

    battle = _ "battle" _ battle_opts+
    event = _ "event" _ value_opts+
    sakura = _ "sakura" _ battle_opts*

    ls = (_ "ls" _ "-p" _ ~r"\d+" _) / (_ "ls" _)

    exit = _ "exit" _
    _ = ~r"\s*"
"""

grammer = Grammar(grammer)


class TkrbExecutor(NodeVisitor):
    def __init__(self):
        super().__init__()
        self.method = None
        self.options = {"-t": 1, "-p": 1, "episode": 1, "field": 1}

    def visit_command(self, node, children):
        print(self.method)
        print(self.options)
        return node

    def visit_immutable(self, node, children):
        return node

    def visit_mutable(self, node, children):
        return node.text, children

    def visit_field(self, node, children):
        data = children[1]

        episdoe, field = data.text.split("-")
        self.options["episode"] = episdoe
        self.options["field"] = field

        return node

    def visit_value_opts(self, node, children):
        _, name, _, value, _ = children
        self.options[name] = value
        return node

    def visit_value_opts_name(self, node, children):
        return node.text

    def visit_value_opts_value(self, node, children):
        return node.text

    def visit_battle_opts(self, node, children):
        if len(children) == 1:
            return children[0]
        return children

    def visit_battle(self, node, children):
        _, _, _, *opts = children
        self.method = node.expr_name
        return node

    def visit_event(self, node, children):
        _, _, _, *opts = children
        self.method = node.expr_name
        return node

    def visit_sakura(self, node, children):
        _, _, _, *opts = children
        self.method = node.expr_name
        return node

    def visit_ls(self, node, children):
        children = children[0]
        self.method = node.expr_name

        if len(children) == 3:
            self.options["-p"] = "*"
            print(f"印出所有隊伍")
            return node

        kind = children[3].text
        team = children[5].text

        if kind == "-p":
            self.options[kind] = team
            print(f"印出第 {team} 隊")

        return node

    def visit_exit(self, node, children):
        self.method = node.expr_name
        return node

    def generic_visit(self, node, children):
        if not node.expr_name and children:
            if len(children) == 1:
                return children[0]
            return children
        return node


def execute(client, command):
    try:
        root = grammer.parse(command)
    except ParseError as err:
        part = command[err.pos:err.pos + 10]
        print(f"Syntax error near '{part}'")
    else:
        visitor = TkrbExecutor()
        try:
            visitor.visit(root)
            client.execute(visitor.method, visitor.options)
        except VisitationError as err:
            print(err)
