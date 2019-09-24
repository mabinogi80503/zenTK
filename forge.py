from api import APICallFailedException
from common import make_datetime


def show(forge, now):
    from database import static_lib

    now = make_datetime(now)

    from prettytable import PrettyTable

    table = PrettyTable()
    table.field_names = ["鍛刀位", "名稱", "剩餘鍛造時間"]

    for data in forge.values():
        slot_no = data["slot_no"]
        sword_name = static_lib.get_sword(data["sword_id"]).name
        finished_time = make_datetime(data["finished_at"])
        need_time = str(finished_time - now) if now <= finished_time else ("已完成")

        table.add_row([slot_no, sword_name, need_time])
    print(table)


def in_room(api):
    try:
        ret = api.forge_room()
    except APICallFailedException:
        print("無法進入鍛刀區")
        return None

    forge = ret["forge"]
    now = ret["now"]

    if forge is None or len(forge) == 0:
        print("沒有任何鍛刀作業！")
        return None

    show(forge, now)


def build(api, slot_no, steel, charcoal, coolant, files, use_assist=0):
    try:
        ret = api.forge_start(slot_no, steel, charcoal, coolant, files, use_assist)
    except APICallFailedException:
        print("鍛刀爐出了一些問題...")
        return

    if ret["status"] != 0:
        print("刀爐不能使用或是有東西佔位子！")
        return None

    if use_assist:
        from database import static_lib

        name = static_lib.get_sword(ret["sword_id"]).name
        print(f"獲得刀劍：{name}")
        return name

    print(f"開始在第 {slot_no} 格刀爐上凌虐刀匠！")


def complete(api, slot):
    try:
        ret = api.forge_complete(slot)
    except APICallFailedException:
        print("快速完成鍛刀出現了錯誤...")
        return None

    if ret["status"] != 0:
        print(f"無法領取在 {slot} 鍛位之刀劍！")
        return None

    from database import static_lib

    name = static_lib.get_sword(ret["sword_id"]).name
    print(f"獲得刀劍：{name}")
