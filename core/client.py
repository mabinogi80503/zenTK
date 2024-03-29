from datetime import datetime, timedelta

from colorama import Fore
from parsimonious.exceptions import ParseError, VisitationError
from parsimonious.grammar import Grammar
from parsimonious.nodes import NodeVisitor

import conquest
import forge
import repairroom

from .api import APICallFailedException
from .database import UserLibrary
from .datatype import Resources, SwordTeam
from .login import DMMAuthenticator_v2
from .preferences import preferences_mgr
from .utils import make_datetime

app_config = preferences_mgr.get("system")
battle_config = preferences_mgr.get("battle")


class TkrbClient(object):
    def __init__(self, api):
        self.api = api
        self.user_data = UserLibrary(self.api)
        self.resources = Resources(api)
        self.teams = {
            "1": SwordTeam(self.api, self.user_data, "1"),
            "2": SwordTeam(self.api, self.user_data, "2"),
            "3": SwordTeam(self.api, self.user_data, "3"),
            "4": SwordTeam(self.api, self.user_data, "4"),
        }
        self.forgeroom = forge.ForgeRoom(api)
        self.conquest = conquest.Conquest(api)
        self.repair_room = repairroom.RepairRoom(self, api)
        self.init_first()

    @classmethod
    def create(cls, account, password):
        api = DMMAuthenticator_v2(account, password).login()
        if not api:
            return None

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
        ret = self.api.home()

        now_time = make_datetime(ret["now"])
        self.conquest.check_when_home(ret["party"], now_time)
        self._check_duty(ret["duty"])

    def _check_duty(self, data):
        if data is None or len(data) == 0:
            if app_config.get("debug"):
                print("無內番！")
            return

        jet_lag = timedelta(hours=1)

        # JP to TW
        finished_time = make_datetime(data["finished_at"]) - jet_lag
        now = datetime.now()

        if now >= finished_time:
            try:
                self.api.complete_duty()
            except APICallFailedException:
                print(Fore.RED + "內番看起來有一些錯誤？時間誤判嗎？" + Fore.RESET)
                return

    def handle_conquest(self, options):
        subcmd = options.get("subcmd", "")
        method, options = conquest.parse(subcmd)
        return self.conquest.execute(method, options) if method else False

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
            return None

        import battle

        executor = battle.request("common", self.api, team_ref, episode, field, sakura)
        status = executor.play()
        self.home()
        return status

    def event_battle(self, team_id, *args, **kwargs):
        team_ref = self._check_before_battle(team_id, event=True)
        if not team_ref:
            return None

        import battle

        executor = battle.request("armament", self.api, team_ref, *args, **kwargs)
        executor.play()
        self.home()

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

    def execute(self, command, options):
        if command is None:
            return

        method = getattr(self, f"handle_" + command)
        if method is None:
            print(f"Command {command} is not found!")
            return None
        method(options)

    def handle_exit(self, options):
        from sys import exit

        exit(0)

    def handle_clear(self, options):
        from os import system

        system("cls")  # windows / osx
        system("clear")  # linux

    def handle_ls(self, options):
        team = options.get("-p", "*")

        if team == "*":
            self.list_team(list_all=True)
        else:
            self.list_team(team_id=team)

    def handle_battle(self, options):
        times = int(options["-t"])
        team_id = int(options["-p"])
        episode = int(options["episode"])
        field = int(options["field"])
        interval = int(battle_config.get("battle_interval"))
        team_bad_waittime = int(battle_config.get("bad_status_interval"))

        from time import sleep
        from battle.base import BattleResult

        for count in range(times):
            status = self.battle(team_id, episode, field)

            if status is None:
                return None

            if status == BattleResult.BE_DEFEATED:
                print(status.value)
                return None

            if status == BattleResult.TEAM_STATUS_BAD:
                print(status.value)
                print(f"等待{team_bad_waittime}秒後恢復...")
                sleep(team_bad_waittime)
                continue

            if interval > 0.0 and count < times - 1:
                print(f"等待 {interval} 秒...")
                sleep(interval)

    def handle_event(self, options):
        times = int(options["-t"])
        team_id = int(options["-p"])
        layer = options.get("-l", None)
        interval = int(battle_config.get("battle_interval"))

        from time import sleep

        for count in range(times):
            self.event_battle(team_id, layer=layer)

            if interval > 0.0 and count < times - 1:
                print(f"等待 {interval} 秒...")
                sleep(interval)

    def handle_sakura(self, options):
        team_id = int(options["-p"])
        episode = int(options["episode"])
        field = int(options["field"])
        mem_id = options.get("-m", None)

        if mem_id:
            self.sakura(episode, field, team_id, mem_id)
        else:
            self.team_sakura(episode, field, team_id)

    def handle_forge(self, options):
        subcmd = options.get("subcmd", "")
        method, opts = forge.parse(subcmd)

        return self.forgeroom.execute(method, opts)

    def handle_repair(self, options):
        subcmd = options.get("subcmd", "")
        method, opts = repairroom.parse(subcmd)
        return self.repair_room.execute(method, opts)

    def handle_swap(self, options):
        action = options.get("action", None)

        if not action:
            return

        if action == "clear":
            idx = options.get("party")
            self.teams[idx].clear()
            return

        if action == "member":
            # TODO: need serial id to support this QQ
            # team_id = options.get("t1")
            # idx = options.get("target_idx")
            # self.teams[team_id].set_sword(idx, serial)
            return

        if action == "team":
            team1 = int(options.get("t1"))
            team2 = int(options.get("t2"))
            self.swap_teams(team1, team2)
            return

    def handle_play(self, options):
        file = options.get("filename", None)
        with open(file, "r") as f:
            content = f.readlines()
        for command in content:
            print(command.strip())
            execute(self, command.strip())

    def handle_sleep(self, options):
        sleep_interval = int(options.get("sleeptime", 0))
        from time import sleep

        sleep(sleep_interval)


grammer = r"""
    command = mutable / immutable

    immutable = exit / clear / ls / sleep / _
    mutable = battle / event / sakura / forge / swap / conquest / play / repair

    string = ~r"\w+"
    integer = ~r"\d+"
    subcmd = ~r"[- a-zA-Z0-9]*"

    field = _ integer "-" integer _
    value_opts = _ value_opts_name _ string _
    value_opts_name = "-m" / "-p" / "-t" / "-l"

    battle_opts = field / value_opts+

    battle = _ "battle" _ battle_opts+
    event = _ "event" _ value_opts+
    sakura = _ "sakura" _ battle_opts*
    forge = _ "forge" _ subcmd _
    repair = _ "repair" _ subcmd _

    swap = _ "swap" _ swap_opts+ _
    swap_opts = (_ "-p" _ swap_team_opts _) / (_ "-m" _ integer _) / (_ "-c" _ integer _)
    swap_team_opts = _ integer _ (":" _ integer _)*

    conquest = _ "conquest" _ subcmd _

    ls = (_ "ls" _ "-p" _ integer _) / (_ "ls" _)
    clear = _ "clear" _
    exit = _ "exit" _
    _ = ~r"\s*"

    play_opts = ~r"[\w\-\.@#]+"
    play = _ "play" _ play_opts _

    sleep = _ "sleep" _ integer _

"""

grammer = Grammar(grammer)


class TkrbExecutor(NodeVisitor):
    def __init__(self):
        super().__init__()
        self.method = None
        self.options = {"-t": 1, "-p": 1, "episode": 1, "field": 1}

    def visit_command(self, node, children):
        return node

    def visit_immutable(self, node, children):
        return node

    def visit_mutable(self, node, children):
        return node.text, children

    def visit_string(self, node, children):
        return node.text

    def visit_integer(self, node, children):
        return node.text

    def visit_subcmd(self, node, children):
        self.options["subcmd"] = node.text
        return node.text

    def visit_field(self, node, children):
        _, episode, _, field, _ = children
        self.options["episode"] = episode
        self.options["field"] = field
        return node

    def visit_value_opts(self, node, children):
        _, name, _, value, _ = children
        self.options[name] = value
        return node

    def visit_value_opts_name(self, node, children):
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

    def visit_forge(self, node, children):
        self.method = "forge"
        return node

    def visit_swap(self, node, children):
        self.method = "swap"
        return node

    def visit_swap_opts(self, node, children):
        children = children[0]
        kind = children[1].text

        cur_action = self.options.get("action", None)

        if kind == "-m":
            if not self.options.get("action", None):
                self.options["action"] = "member"
                self.options["target_idx"] = children[3]
            return node

        if kind == "-p":
            if cur_action != "member":
                self.options["action"] = "team"
            return node

        if kind == "-c":
            self.options["action"] = "clear"
            self.options["party"] = children[3]
            return node

        return node

    def visit_swap_team_opts(self, node, children):
        t1 = children[1]
        self.options["t1"] = t1

        if len(children) > 3:
            children = children[3]
            t2 = children[2]
            self.options["t2"] = t2

        return node

    def visit_conquest(self, node, children):
        self.method = node.expr_name
        return node

    def visit_repair(self, node, children):
        self.method = "repair"
        return node

    def visit_ls(self, node, children):
        children = children[0]
        self.method = node.expr_name

        if len(children) == 3:
            self.options["-p"] = "*"
            return node

        kind = children[3].text
        team = children[5]

        if kind == "-p":
            self.options[kind] = team

        return node

    def visit_exit(self, node, children):
        self.method = node.expr_name
        return node

    def visit_clear(self, node, children):
        self.method = node.expr_name
        return node

    def visit_play(self, node, children):
        self.method = "play"
        return node

    def visit_play_opts(self, node, children):
        self.options["filename"] = node.text
        return node.text

    def visit_sleep(self, node, children):
        self.method = "sleep"
        self.options["sleeptime"] = children[3]
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
        part = command[err.pos : err.pos + 10]
        print(f"Syntax error near '{part}'")
    else:
        visitor = TkrbExecutor()
        try:
            visitor.visit(root)
            client.execute(visitor.method, visitor.options)
        except VisitationError as err:
            print(err)
