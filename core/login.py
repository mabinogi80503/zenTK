import re
import sys
import urllib

import requests
from requestium import Keys, Session

from .base import BasicAuthenticator
from .exceptions import LoginFailException


if sys.platform == "win32":
    webdriver_pos = "./chromedriver.exe"
else:
    webdriver_pos = "./chromedriver"


class DMMAuthenticator(BasicAuthenticator):
    def __init__(self, account, password):
        self.urls = {
            "login": "https://accounts.dmm.com/service/login/password",
            "get-token": "https://accounts.dmm.com/service/api/get-token",
            "auth": "https://accounts.dmm.com/service/login/password/authenticate",
            "game": "http://pc-play.games.dmm.com/play/tohken/",
            "request": "https://osapi.dmm.com/gadgets/makeRequest",
        }

        self.patterns = {
            "csrf-token": re.compile(r"<meta name=\"csrf-token\" content=\"(\w+)\" />"),
            "http-dmm-token": re.compile(
                r"<meta name=\"csrf-http-dmm-token\" content=\"(\w+)\" />"
            ),
        }

        self.session = requests.session()
        self.cookies = None
        self.proxies = None
        self.headers = {
            "Accept-Encoding": "gzip, deflate, br",
            "Host": "www.dmm.com",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/72.0.3626.109 Safari/537.36",
            "Upgrade-Insecure-Requests": "1",
        }

        self.dmm_id = account
        self.dmm_pwd = password
        self.game_version = None

    def __del__(self):
        self.session.close()

    def _parse_dmm_token(self):
        resp = self._request(self.urls["login"])
        mch = self.patterns["csrf-token"].search(resp.text)

        if not mch:
            raise LoginFailException("取得 DMM csrf-token 失敗")

        csrf_token = mch.group(1)

        mch = self.patterns["http-dmm-token"].search(resp.text)

        if not mch:
            raise LoginFailException("取得 DMM http token 失敗")

        http_dmm_token = mch.group(1)

        return csrf_token, http_dmm_token

    def _parse_get_token(self, csrf_token, http_token):
        self.headers.update(
            {
                "http-dmm-token": http_token,
                "X-Requested-With": "XMLHttpRequest",
                "Origin": "https://accounts.dmm.com",
                "Referer": self.urls["login"],
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Accept": "application/json, text/javascript, */*; q=0.01",
            }
        )

        payload = {"token": csrf_token}

        resp = self._request(self.urls["get-token"], method="POST", data=payload)
        if resp.status_code != requests.codes.ok:
            raise LoginFailException("DMM get token 失敗！")

        token = resp.json()

        code = token["header"]["result_code"]
        if code != "0":
            raise LoginFailException(f"DMM get token: {code}")

        next_token = token["body"]["token"]
        hash_id = token["body"]["login_id"]
        hash_pwd = token["body"]["password"]

        return next_token, hash_id, hash_pwd

    def _parse_authenticate(self, token):
        del self.headers["http-dmm-token"]
        del self.headers["X-Requested-With"]

        self.session.cookies.update(
            {"ckcy": "1", "cklg": "ja", "check_open_login": "1"}
        )

        payload = {
            "token": token,
            "login_id": self.dmm_id,
            "password": self.dmm_pwd,
            "idKey": self.dmm_id,
            "pwKey": self.dmm_pwd,
            "path": "",
            "prompt": "",
        }

        self._request(self.urls["auth"], method="POST", data=payload)

    def _login_game(self):
        self.session.cookies.set("ckcy", None)
        self.session.cookies.set("ckcy", "1")

        self.headers.update({"Host": "pc-play.games.dmm.com"})

        resp = self._request(self.urls["game"], data=None)

        del self.headers["Host"]

        mch = re.search(r"URL\s*: \"(.*)\"", resp.text)
        if not mch:
            raise LoginFailException("無法解析 URL")
        url = urllib.parse.unquote(mch.group(1))  # 還原 url encode
        url = re.search("[^#]+", url)[0]

        mch = re.search(r"ST\s*: \"(.*)\"", resp.text)
        if not mch:
            raise LoginFailException("無法解析 ST")
        st = urllib.parse.unquote(mch.group(1))

        mch = re.search(r"http://www\.touken-ranbu\.jp/gadget\?v=(\d+)", url)
        if not mch:
            raise LoginFailException("無法取得遊戲版本")
        game_version = mch.group(1)

        self.headers.update({"Host": "osapi.dmm.com"})
        resp = self._request(url)

        self._login_world(st, game_version)

    def _login_world(self, st, game_version):

        del self.headers["Host"]
        del self.headers["Upgrade-Insecure-Requests"]
        del self.headers["Origin"]

        payload = {
            "url": "https://www.touken-ranbu.jp/login/",
            "httpMethod": "POST",
            "headers": "Content-Type=application/x-www-form-urlencoded",
            "postData": "device=1&game_type=2",
            "authz": "signed",
            "st": st,
            "contentType": "JSON",
            "numEntries": "3",
            "getSummaries": "false",
            "signOwner": "true",
            "signViewer": "true",
            "gadget": f"http://www.touken-ranbu.jp/gadget?v={game_version}",
            "container": "dmm",
            "bypassSpecCache": "",
            "getFullHeaders": "false",
            "xmr": "http://osapi.dmm.com",
            "oauthState": "",
            "OAUTH_SIGNATURE_PUBLICKEY": "key_2022",
        }

        resp = self._request(self.urls["request"], method="POST", data=payload)
        text = resp.text.replace("\\", "")

        mch = re.search(r"\"status\":(\d+)", text)
        if mch:
            status = int(mch.group(1))
            if status == 97:
                raise LoginFailException("伺服器可能在維修中！")

        mch = re.search(r"\"url\":\"([^\"]+)\"", text)
        if not mch:
            raise LoginFailException("解析伺服器位址失敗")

        self.server_url = mch.group(1)

        loginUrl = self.server_url + "login?uid="
        payload.update({"url": loginUrl, "postData": "lang_id=1"})
        resp = self._request(self.urls["request"], method="POST", data=payload)

        text = resp.text.replace("\\", "")
        import json

        h1 = json.loads(resp.text[27:])

        if h1[loginUrl]["rc"] != 200:
            raise LoginFailException("登入遊戲失敗！")

        h2 = json.loads(h1[loginUrl]["body"])

        self.user_id = h2["user_id"]
        self.cookie_value = h2["cookie_value"]
        self.st = h2["t"]

        return self.user_id, self.cookie_value, self.st

    def login(self):
        print("登入刀劍亂舞中...", end="")

        from colorama import Fore

        try:
            csrf_token, http_token = self._parse_dmm_token()
            token, id_hash, pwd_hash = self._parse_get_token(csrf_token, http_token)
            self._parse_authenticate(token)
            self._login_game()
            print(Fore.GREEN + "成功")
        except LoginFailException as e:
            print(Fore.RED + "失敗")
            print(e)
            return None
        else:
            from .api import TkrbApi

            return TkrbApi(
                url=self.server_url,
                user_id=self.user_id,
                cookie=self.cookie_value,
                token=self.st,
            )


class DMMAuthenticator_v2(BasicAuthenticator):
    def __init__(self, account, password):
        self.urls = {
            "login": "https://accounts.dmm.com/service/login/password",
            "game": "http://pc-play.games.dmm.com/play/tohken/",
            "request": "https://osapi.dmm.com/gadgets/makeRequest",
        }
        self.session = Session(
            webdriver_path=webdriver_pos,
            browser="chrome",
            default_timeout=10,
            webdriver_options={"arguments": ["headless"]},
        )
        self.headers = {
            "Accept-Encoding": "gzip, deflate, br",
            "Host": "www.dmm.com",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/72.0.3626.109 Safari/537.36",
            "Upgrade-Insecure-Requests": "1",
        }
        self.dmm_id = account
        self.dmm_pwd = password
        self.game_version = None

    def login(self):
        print("登入刀劍亂舞中...", end="")

        from colorama import Fore

        try:
            self._login_to_dmm()
            self._login_game()
            print(Fore.GREEN + "成功")
        except Exception:
            print(Fore.RED + "失敗")
        else:
            from .api import TkrbApi

            return TkrbApi(
                url=self.server_url,
                user_id=self.user_id,
                cookie=self.cookie_value,
                token=self.st,
            )

    def _login_to_dmm(self):
        self.session = Session(
            webdriver_path="./chromedriver.exe",
            browser="chrome",
            default_timeout=10,
            webdriver_options={"arguments": ["headless"]},
        )
        self.webdriver = self.session.driver
        self.webdriver.get(self.urls.get("login"))
        self.session.transfer_driver_cookies_to_session()

        account_t = self.webdriver.ensure_element_by_id("login_id")
        pwd_t = self.webdriver.ensure_element_by_id("password")

        account_t.send_keys(self.dmm_id)
        pwd_t.send_keys(self.dmm_pwd)
        pwd_t.send_keys(Keys.ENTER)
        self.session.transfer_driver_cookies_to_session()

        # Wait for backing to dmm.com
        self.webdriver.ensure_element_by_id("tracking_area", timeout=10)
        self.session.transfer_driver_cookies_to_session()

    def _login_game(self):
        self.session.cookies.set("ckcy", "1")

        self.headers.update({"Host": "pc-play.games.dmm.com"})

        resp = self.session.get(
            self.urls["game"], headers=self.headers, allow_redirects=True
        )

        del self.headers["Host"]

        mch = re.search(r"URL\s*: \"(.*)\"", resp.text)
        if not mch:
            raise LoginFailException("無法解析 URL")
        url = urllib.parse.unquote(mch.group(1))  # 還原 url encode
        url = re.search("[^#]+", url)[0]
        if url.startswith("//"):
            url = "http:" + url

        mch = re.search(r"ST\s*: \"(.*)\"", resp.text)
        if not mch:
            raise LoginFailException("無法解析 ST")
        st = urllib.parse.unquote(mch.group(1))

        mch = re.search(r"http://www\.touken-ranbu\.jp/gadget\?v=(\d+)", url)
        if not mch:
            raise LoginFailException("無法取得遊戲版本")
        game_version = mch.group(1)

        self.headers.update({"Host": "osapi.dmm.com"})
        resp = self.session.get(url, headers=self.headers)
        self._login_world(st, game_version)

    def _login_world(self, st, game_version):
        del self.headers["Upgrade-Insecure-Requests"]

        self.headers.update({"Origin": "http://osapi.dmm.com"})

        payload = {
            "url": "https://www.touken-ranbu.jp/login/",
            "httpMethod": "POST",
            "headers": "Content-Type=application/x-www-form-urlencoded",
            "postData": "device=1&game_type=2",
            "authz": "signed",
            "st": st,
            "contentType": "JSON",
            "numEntries": "3",
            "getSummaries": "false",
            "signOwner": "true",
            "signViewer": "true",
            "gadget": f"http://www.touken-ranbu.jp/gadget?v={game_version}",
            "container": "dmm",
            "bypassSpecCache": "",
            "getFullHeaders": "false",
            "xmr": "http://osapi.dmm.com",
            "oauthState": "",
            "OAUTH_SIGNATURE_PUBLICKEY": "key_2022",
        }

        resp = self.session.post(
            self.urls["request"], headers=self.headers, data=payload
        )
        text = resp.text.replace("\\", "")

        mch = re.search(r"\"status\":(\d+)", text)
        if mch:
            status = int(mch.group(1))
            if status == 97:
                raise LoginFailException("伺服器可能在維修中！")

        mch = re.search(r"\"url\":\"([^\"]+)\"", text)
        if not mch:
            raise LoginFailException("解析伺服器位址失敗")

        self.server_url = mch.group(1)

        loginUrl = self.server_url + "login?uid="
        payload.update({"url": loginUrl, "postData": "lang_id=1"})
        resp = self.session.post(
            self.urls["request"], headers=self.headers, data=payload
        )

        text = resp.text.replace("\\", "")
        import json

        h1 = json.loads(resp.text[27:])

        if h1[loginUrl]["rc"] != 200:
            raise LoginFailException("登入遊戲失敗！")

        h2 = json.loads(h1[loginUrl]["body"])

        self.user_id = h2["user_id"]
        self.cookie_value = h2["cookie_value"]
        self.st = h2["t"]
        return self.user_id, self.cookie_value, self.st
