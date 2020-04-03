from colorama import Fore

DECRYPTION_KEY = "9ij8pNKv7qVJnpj4".encode("utf-8")


def decrypte_battle_msg(data, iv):
    hex_iv = bytes.fromhex(iv)
    hex_data = bytes.fromhex(data)

    from Crypto.Cipher import AES

    cryptor = AES.new(DECRYPTION_KEY, AES.MODE_CBC, iv=hex_iv)
    decrypted: str = cryptor.decrypt(hex_data).decode("utf-8")

    import json

    d_json = json.loads(decrypted[: decrypted.rfind("}") + 1])

    s = (
        str(d_json)
        .replace("True", "true")
        .replace("False", "false")
        .replace("None", "null")
        .replace("'", '"')
    )
    with open("decrypted_battle.json", mode="w", encoding="UTF-8") as f:
        f.write(s)

    return d_json


CONTEND_FORMATION = [None, "6", "1", "2", "3", "4", "5"]


def get_favorable_formation(enemy_formation):
    """
    計算對應的有利陣型
    """
    from random import randint

    if not enemy_formation:
        return CONTEND_FORMATION[randint(1, 6)]

    enemy_formation = int(enemy_formation)
    return (
        CONTEND_FORMATION[enemy_formation]
        if enemy_formation != 0
        else str(randint(1, 6))
    )


def get_formation_name(formation):
    return ["不明", "魚鱗", "鶴翼", "橫隊", "方", "雁行", "逆行"][formation] + "陣"


def get_resource_type_name(type):
    type = int(type)
    names = ["", "活動物品", "木炭", "玉鋼", "冷卻材", "砥石"]
    return names[type] if type < len(names) else "不明"


def get_resource_id_name(resource_id):
    resource_id = str(resource_id)
    names = {
        "0": "小判",
        "1": "依賴札",
        "2": "木炭",
        "3": "玉鋼",
        "4": "冷卻材",
        "5": "砥石",
        "37": "月兔糰子",
    }
    return names[resource_id] if resource_id in names.keys() else "不明"


def check_new_sword(data):
    """
    檢查戰鬥結束時，是否有獲取新的刀劍男士
    """
    if not data:
        return
    get_sword_id = data.get("get_sword_id", None)
    if not get_sword_id:
        return

    from core.database import sword_data

    sword_data = sword_data.get(get_sword_id)
    if sword_data:
        print("獲得新刀劍：" + Fore.YELLOW + f"{sword_data.get(get_sword_id).name}")
    else:
        print("獲得一把沒有在資料庫內的刀！請聯絡專案作者更新資料庫！")


def get_alive_member_count(swordref):
    return len(
        [
            battleable
            for battleable in [sword.battleable for sword in swordref if sword]
            if battleable
        ]
    )


def add_passcards(api, event_id, n: int):
    if n <= 0 or n > 3:
        return False

    ret = api.recover_event_cost(event_id, n)
    if not ret["status"]:
        print(f"補充手形 {n} 個！")
        return True
    else:
        print("補充手形失敗！")
        return False


def check_passcards(info):
    if not info:
        raise ValueError("活動資訊不存在")

    return info.check_passcard()


def check_and_get_sally_data(api):
    from core.exceptions import APICallFailedException

    try:
        data = api.sally()
    except APICallFailedException:
        print(Fore.RED + "存取 sally 失敗！")
        return None
    else:
        return data
