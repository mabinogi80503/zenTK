from api import APICallFailedException
from common import make_datetime


def check_when_home(api, data, nowtime):
    for party in [p for p in data.values() if p["finished_at"] is not None]:
        finished_time = make_datetime(party["finished_at"])
        if finished_time > nowtime:
            continue
        receive_reward(api, party["party_no"])


def start(api, field, party):
    try:
        api.start_conquest(field, party)
    except APICallFailedException:
        print(f"隊伍 {party} 無法出發...")


def receive_reward(api, party):
    try:
        api.receive_conquest_reward(party)
    except APICallFailedException:
        print(f"無法領取隊伍 {party} 的遠征獎勵")


def show(api):
    try:
        ret = api.go_conquest()

        party_data = ret["party"]
        data = ret["summary"]

        if data is None or len(data) == 0:
            print("目前無遠征唷！")
            return

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
            need_time = str(finished_time - now) if now <= finished_time else ("已完成")
            table.add_row([party_no, field, need_time])
        print(table)
    except APICallFailedException:
        print(f"無法進入遠征頁面")
