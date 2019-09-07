from colorama import Fore

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

    def execute(self, command):
        command = command.strip()
        if command == "exit" or command == "q":
            from sys import exit
            exit(0)

        try:
            for cmd in buildin_command:
                if command.startswith(cmd):
                    self._handle_buildin_command(command)
        except APICallFailedException:
            pass

    def _handle_buildin_command(self, command):
        command = command.split()

        if command[0] == "ls":
            self._handle_list_cmd(command[1:])
        elif command[0] == "battle":
            self._handle_battle_cmd(command[1:])
        elif command[0] == "forge":
            self._handle_forge_cmd(command[1:])
        elif command[0] == "swap":
            self._handle_swap_cmd(command[1:])
        elif command[0] == "sakura":
            self._handle_sakura_cmd(command[1:])

    def _handle_list_cmd(self, args):
        if len(args) == 0 or args[0] == "--all" or args[0] == "-a":
            self.list_team(list_all=True)
        elif args[0].startswith("t"):
            team_id = args[0][1:]
            self.list_team(team_id=team_id)

    def _handle_battle_cmd(self, args):
        import re
        times = 1
        team_id = "1"
        episode = field = None
        event = False

        i = 0
        while i < len(args):
            if args[i] == "--time" or args[i] == "-t":
                i += 1
                times = int(args[i])
            elif args[i] == "--party" or args[i] == "-p":
                i += 1
                team_id = args[i]
            elif args[i] == "event":
                event = True

            if not event:
                match = re.match(r"(\d+)-(\d+)", args[i])
                if match:
                    episode = int(match.group(1))
                    field = int(match.group(2))
            i += 1

        from time import sleep

        interval = int(battle_config.get("battle_interval"))

        if event:
            for count in range(times):
                self.event_battle(team_id)

                if interval > 0.0 and count < times - 1:
                    print(f"等待 {interval} 秒...")
                    sleep(interval)
            return

        if team_id and episode and field:
            for count in range(times):
                self.battle(team_id, episode, field)

                if interval > 0.0 and count < times - 1:
                    print(f"等待 {interval} 秒...")
                    sleep(interval)
        else:
            print(Fore.RED + "命令錯誤！")

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

    def _handle_sakura_cmd(self, args):
        import re
        mem_id = None
        team_id = "1"
        episode = field = 1
        event = False

        i = 0
        while i < len(args):
            if args[i] == "--mem" or args[i] == "-m":
                i += 1
                mem_id = args[i]
            elif args[i] == "--party" or args[i] == "-p":
                i += 1
                team_id = args[i]

            if not event:
                match = re.match(r"(\d+)-(\d+)", args[i])
                if match:
                    episode = int(match.group(1))
                    field = int(match.group(2))
            i += 1

        if team_id and episode and field:
            if mem_id:
                self.sakura(episode, field, team_id, mem_id)
            else:
                self.team_sakura(episode, field, team_id)

        else:
            print(Fore.RED + "命令錯誤！")
