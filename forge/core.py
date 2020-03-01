from parsimonious.exceptions import ParseError, VisitationError
from parsimonious.grammar import Grammar
from parsimonious.nodes import NodeVisitor

from api import APICallFailedException
from common import make_datetime


class ForgeRoom(object):
    def __init__(self, api):
        self._api = api

    def _get_info(self):
        try:
            ret = self._api.forge_room()
        except APICallFailedException:
            print("無法進入鍛刀區")
            return None, None

        return ret["forge"], ret["now"]

    def _ls(self, forgelist, now):
        from database import static_lib

        now = make_datetime(now)

        from prettytable import PrettyTable

        table = PrettyTable()
        table.field_names = ["鍛刀位", "名稱", "剩餘鍛造時間"]

        for data in forgelist.values():
            slot_no = data["slot_no"]
            sword_name = static_lib.get_sword(data["sword_id"]).name
            finished_time = make_datetime(data["finished_at"])
            need_time = str(finished_time - now) if now <= finished_time else ("已完成")

            table.add_row([slot_no, sword_name, need_time])
        print(table)

    def handle_ls(self, options):
        forge_list, nowtime = self._get_info()
        if forge_list is None or len(forge_list) == 0:
            print("無鍛刀作業")
            return True
        self._ls(forge_list, nowtime)
        return True

    def _build(self, slot_no, steel, charcoal, coolant, files, use_assist=0):
        try:
            ret = self._api.forge_start(
                slot_no, steel, charcoal, coolant, files, use_assist
            )
        except APICallFailedException:
            print("鍛刀爐出了一些問題...")
            return False

        if ret["status"] != 0:
            print("刀爐不能使用或是有東西佔位子！")
            return False

        if use_assist:
            from database import static_lib

            name = static_lib.get_sword(ret["sword_id"]).name
            print(f"獲得刀劍：{name}")
        else:
            print(f"開始在第 {slot_no} 格刀爐上凌虐刀匠！")

        return True

    def handle_build(self, options):
        slot = options.get("slot", 1)
        steel = options.get("steel", None)
        charcoal = options.get("charcoal", None)
        coolant = options.get("coolant", None)
        files = options.get("files", None)
        quick = options.get("quick", 0)

        if not steel or not charcoal or not coolant or not files:
            print("未指定鍛造需要的素材量！")
            return False
        return self._build(slot, steel, charcoal, coolant, files, quick)

    def _get(self, slot):
        try:
            ret = self._api.forge_complete(slot)
        except APICallFailedException:
            print("快速完成鍛刀出現了錯誤...")
            return False

        if ret["status"] != 0:
            print(f"無法領取在 {slot} 鍛位之刀劍！")
            return False

        from database import static_lib

        name = static_lib.get_sword(ret["sword_id"]).name
        print(f"獲得刀劍：{name}")
        return True

    def handle_get(self, options):
        slot = options.get("slot", 1)
        return self._get(slot)

    def execute(self, action, options):
        if not action:
            return False

        method = getattr(self, f"handle_{action}")
        return method(options) if method else False


grammer = r"""
    root = mutable / immutable

    immutable = ls
    mutable = get / build

    integer = ~r"\d+"
    string = ~r"\w+"
    _ = ~r"\s*"

    ls = _ "ls" _

    get = _ "get" _ integer _
    build = _ "build" _ build_opts+ _
    build_opts = (_ "-m" _ integer _ integer _ integer _ integer _) / (_ "-s" _ integer _) / (_ "-u" _)
"""


class ForgeCmdVisitor(NodeVisitor):
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

    def visit_string(self, node, children):
        return node.text

    def visit_ls(self, node, children):
        self.method = "ls"
        return node.text

    def visit_get(self, node, children):
        self.method = "get"
        self.options["slot"] = children[3]
        return node

    def visit_build(self, node, children):
        self.method = "build"
        return node

    def visit_build_opts(self, node, children):
        children = children[0]
        opt = children[1].text

        if opt == "-m":
            _, steel, _, charcoal, _, coolant, _, files, *_ = children[2:]
            self.options.update(
                {
                    "steel": steel,
                    "charcoal": charcoal,
                    "coolant": coolant,
                    "files": files,
                }
            )

        if opt == "-s":
            self.options["slot"] = children[3]

        if opt == "-u":
            self.options["quick"] = 1

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
        visitor = ForgeCmdVisitor()
        try:
            visitor.visit(root)
            method, opts = visitor.method, visitor.options
        except VisitationError as err:
            print(err)
    finally:
        return method, opts
