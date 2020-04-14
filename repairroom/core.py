from parsimonious.exceptions import ParseError, VisitationError
from parsimonious.grammar import Grammar
from parsimonious.nodes import NodeVisitor

from core.exceptions import APICallFailedException
from core.utils import make_datetime


class RepairRoom(object):
    def __init__(self, client, api):
        self._client = client
        self._api = api

    def get_info(self):
        try:
            ret = self._api.repair_room()
        except APICallFailedException:
            print("無法進入手入部屋")
            return None, None

        return ret["repair"], ret["now"]

    def handle_ls(self, options):
        repair_info, nowtime = self.get_info()
        return self.ls(repair_info, nowtime)

    def ls(self, repair_info, now):
        if len(repair_info) == 0:
            print("無手入作業")
            return True

        now = make_datetime(now)

        from prettytable import PrettyTable

        table = PrettyTable()
        table.field_names = ["手入位", "名稱", "剩餘手入時間"]

        user_data = self._client.user_data

        for data in repair_info.values():
            slot_no = data["slot_no"]
            sword_name = user_data.get_sword(data["sword_serial_id"]).name
            finished_time = make_datetime(data["finished_at"])
            need_time = str(finished_time - now) if now <= finished_time else ("已完成")
            table.add_row([slot_no, sword_name, need_time])
        print(table)
        return True

    def handle_start(self, options):
        team_id = options.get("party")
        team_pos = options.get("pos")
        room_slot = options.get("slot")

        if not team_id or not team_pos or not room_slot:
            print("參數錯誤")
            return False

        return self.start(team_id, team_pos, room_slot, 1)

    def start(self, team_id, team_pos, room_slot, use_assist=0):
        sword = self._client.teams.get(team_id, {}).get(team_pos)
        try:
            serial = sword.serial_id
            ret = self._api.repair_start(serial, room_slot, use_assist)
        except APICallFailedException:
            print("手入出了問題")
            return False

        if ret["status"] != 0:
            print("手入位不能使用或是有東西佔位子！")
            return False

        print(f"{sword.name} 正在維修...")
        return True

    def handle_get(self, options):
        slot = options.get("slot", -1)
        if slot == -1:
            print("參數錯誤")
            return False
        return self.get(slot)

    def get(self, slot):
        try:
            ret = self._api.repair_complete(slot)
        except APICallFailedException:
            print(f"完成手入 {slot} 出現了錯誤...")
            return False

        if ret["status"] != 0:
            print(f"無法完成 {slot} 位之手入！")
            return False

        for slot in ret.values():
            print(f"手入位置 {slot} 已收回！")

        return True

    def execute(self, action, options):
        if not action:
            return False

        method = getattr(self, f"handle_{action}")
        return method(options) if method else False


grammer = r"""
    root = mutable / immutable

    immutable = ls
    mutable = start / get

    integer = ~r"\d+"
    _ = ~r"\s*"

    ls = _ "ls" _
    start = _ "start" _ opts+ _
    get = _ "get" _ opts+ _
    opts = (_ "-p" _ integer _) / (_ "-m" _ integer _) / (_ "-s" _ integer _)
"""


class RepairCmdVisitor(NodeVisitor):
    def __init__(self):
        super().__init__()
        self.method = None
        self.options = {}

    def visit_root(self, node, children):
        return node

    def visit_immutable(self, node, children):
        return node

    def visit_mutable(self, node, children):
        return node.text, children

    def visit_integer(self, node, children):
        return node.text

    def visit_ls(self, node, children):
        self.method = node.expr_name
        return node

    def visit_start(self, node, children):
        self.method = node.expr_name
        return node

    def visit_get(self, node, children):
        self.method = node.expr_name
        return node

    def visit_opts(self, node, children):
        children = children[0]
        opt = children[1].text

        if opt == "-p":
            self.options["party"] = children[3]

        if opt == "-m":
            self.options["pos"] = children[3]

        if opt == "-s":
            self.options["slot"] = children[3]

        return node

    def generic_visit(self, node, children):
        if not node.expr_name and children:
            if len(children) == 1:
                return children[0]
            return children
        return node


grammer = Grammar(grammer)


def parse(cmd):
    method = opts = None

    if cmd is None or len(cmd) == 0:
        return method, opts

    try:
        root = grammer.parse(cmd)
    except ParseError as err:
        part = cmd[err.pos : err.pos + 10]
        print(f"Syntax error near '{part}'")
    else:
        visitor = RepairCmdVisitor()
        try:
            visitor.visit(root)
            method, opts = visitor.method, visitor.options
        except VisitationError as err:
            print(err)
    finally:
        return method, opts
