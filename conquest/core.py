from parsimonious.exceptions import ParseError, VisitationError
from parsimonious.grammar import Grammar
from parsimonious.nodes import NodeVisitor

from api import APICallFailedException
from common import make_datetime


class Conquest(object):
    def __init__(self, api):
        self._api = api

    def _ls(self):
        try:
            ret = self._api.go_conquest()

            party_data = ret["party"]
            data = ret["summary"]

            if data is None or len(data) == 0:
                print("目前無遠征唷！")
                return True

            def transfer_field_2_human(field):
                from math import ceil

                field = int(field)
                episode = int(ceil(field / 4))
                field = field - ((episode - 1) * 4)
                return f"{episode}-{field}"

            now = make_datetime(ret["now"])
            sorted_data = sorted(data.values(), key=lambda d: d["party_no"])

            from prettytable import PrettyTable

            table = PrettyTable()
            table.field_names = ["隊伍", "地圖", "剩餘時間"]

            for conq in sorted_data:
                party_no = conq["party_no"]
                field = transfer_field_2_human(conq["field_id"])
                finished_time = make_datetime(party_data[str(party_no)]["finished_at"])
                need_time = (
                    str(finished_time - now) if now <= finished_time else ("已完成")
                )
                table.add_row([party_no, field, need_time])
            print(table)
        except APICallFailedException:
            print(f"無法進入遠征頁面")
            return False

    def handle_ls(self, options):
        return self._ls()

    def _start(self, field, party):
        try:
            self._api.start_conquest(field, party)
        except APICallFailedException:
            print(f"隊伍 {party} 無法出發...")
            return False
        else:
            return True

    def handle_start(self, options):
        field = options.get("field", None)
        party = options.get("party", None)
        if field and party:
            return self._start(field, party)
        return False

    def _get_rewards(self, party):
        try:
            self._api.receive_conquest_reward(party)
            return True
        except APICallFailedException:
            print(f"無法領取隊伍 {party} 的遠征獎勵")
            return False

    def handle_get(self, options):
        party = options.get("party", None)
        if not party:
            return False

        return self._get_rewards(party)

    def check_when_home(self, data, nowtime):
        for party in [p for p in data.values() if p["finished_at"] is not None]:
            finished_time = make_datetime(party["finished_at"])
            if finished_time > nowtime:
                continue
            self._get_rewards(party["party_no"])
        return True

    def execute(self, method, options):
        method = getattr(self, f"handle_{method}")
        return method(options)


grammer = r"""
    root = send / ls

    integer = ~r"\d+"
    string = ~r"\w+"
    _ = ~r"\s*"

    send = _ "send" _ send_opts+
    send_opts = field / party+

    field = _ integer "-" integer _
    party = _ "-p" _ integer _

    ls = _ "ls" _
"""

grammer = Grammar(grammer)


class ConquestCmdVisitor(NodeVisitor):
    def __init__(self):
        super().__init__()
        self.method = None
        self.options = {}

    def visit_integer(self, node, children):
        return node.text

    def visit_string(self, node, children):
        return node.text

    def visit_root(self, node, children):
        return node

    def visit_field(self, node, children):
        _, episode, _, field, _ = children

        episode = int(episode)
        field = int(field)

        self.options["field"] = str((episode - 1) * 4 + field)
        return node

    def visit_party(self, node, children):
        _, _, _, party, _ = children
        self.options["party"] = party
        return node

    def visit_send(self, node, children):
        self.method = "start"
        return node

    def visit_send_opts(self, node, children):
        return node

    def visit_ls(self, node, children):
        self.method = "ls"
        return node

    def generic_visit(self, node, children):
        if not node.expr_name and children:
            if len(children) == 1:
                return children[0]
            return children
        return node


def parse(cmd):
    method = opts = None

    if cmd is None or len(cmd) == 0:
        return method, opts

    try:
        root = grammer.parse(cmd)
    except ParseError as err:
        part = cmd[err.pos : err.pos + 10]
        print(f"不支援命令：{part}")
    else:
        visitor = ConquestCmdVisitor()
        try:
            visitor.visit(root)
            method, opts = visitor.method, visitor.options
        except VisitationError as err:
            print(err)
    finally:
        return method, opts
