import re
import urllib
from abc import ABCMeta, abstractmethod

import requests


class BasicAuthenticator(object, metaclass=ABCMeta):
    @abstractmethod
    def login(self):
        raise NotImplementedError()


class LoginFailException(Exception):
    def __init__(self, reason):
        super().__init__(self)
        self.reason = reason

    def __str__(self):
        return self.reason


class DMMAuthenticator(BasicAuthenticator):
    def __init__(self, account, password):
        self.urls = {
            "login": "https://www.dmm.com/my/-/login/",
            "ajax": "https://www.dmm.com/my/-/login/ajax-get-token/",
            "auth": "https://www.dmm.com/my/-/login/auth/",
            "game": "http://pc-play.games.dmm.com/play/tohken/",
            "request": "https://osapi.dmm.com/gadgets/makeRequest",
        }

        self.patterns = {
            "dmm_token": re.compile('xhr\\.setRequestHeader\\("DMM_TOKEN", "([^"]+)"'),
            "token": re.compile('"token": "([^"]+)"'),
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
        self.dmm_token = None
        self.token = None
        self.ajax_token = None
        self.ajax_id_token = None
        self.ajax_pwd_token = None
        self.game_version = None

    def __del__(self):
        self.session.close()

    def _parse_dmm_token(self):
        resp = self._request(self.urls["login"])
        mch = self.patterns["dmm_token"].search(resp.text)
        if not mch:
            raise LoginFailException("取得 DMM token 失敗")

        self.dmm_token = mch.group(1)
        mch = self.patterns["token"].search(resp.text)
        if mch:
            self.token = mch.group(1)

        return self.dmm_token, self.token

    def _parse_ajax_token(self):
        self.headers.update(
            {
                "DMM_TOKEN": self.dmm_token,
                "X-Requested-With": "XMLHttpRequest",
                "Origin": "https://www.dmm.com",
                "Referer": self.urls["login"],
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Accept": "application/json, text/javascript, */*; q=0.01",
            }
        )

        payload = {"token": self.token}

        resp = self._request(self.urls["ajax"], method="POST", data=payload)
        if resp.status_code != requests.codes.ok:
            raise LoginFailException("取得 ajax token 失敗！")

        token = resp.json()
        self.ajax_token = token["token"]
        self.ajax_id_token = token["login_id"]
        self.ajax_pwd_token = token["password"]

        return self.ajax_token, self.ajax_id_token, self.ajax_pwd_token

    def _parse_osapi_url(self):
        del self.headers["DMM_TOKEN"]
        del self.headers["X-Requested-With"]

        self.session.cookies.update(
            {"ckcy": "1", "cklg": "ja", "check_open_login": "1"}
        )

        payload = {
            "token": self.ajax_token,
            "login_id": self.dmm_id,
            "password": self.dmm_pwd,
            self.ajax_id_token: self.dmm_id,
            self.ajax_pwd_token: self.dmm_pwd,
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
            "OAUTH_SIGNATURE_PUBLICKEY": "key_2020",
        }

        resp = self._request(self.urls["request"], method="POST", data=payload)
        text = resp.text.replace("\\", "")

        mch = re.search(r"\"url\":\"([^\"]+)\"", text)
        if not mch:
            raise LoginFailException("解析伺服器位址失敗")

        self.server_url = mch.group(1)

        loginUrl = self.server_url + "login"
        payload.update({"url": loginUrl, "postData": ""})
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
            self._parse_dmm_token()
            self._parse_ajax_token()
            self._parse_osapi_url()
            self._login_game()
            print(Fore.GREEN + "成功")

            # 登入結束！不再需要 proxy 了！
            self.proxies = None
        except LoginFailException as e:
            print(Fore.RED + "失敗")
            print(e)
            return None
        else:
            from api import TkrbApi

            return TkrbApi(
                url=self.server_url,
                user_id=self.user_id,
                cookie=self.cookie_value,
                token=self.st,
            )

    def _request(self, url, method="GET", data=None, **kwargs):
        payload = None
        if "params" in kwargs:
            payload = kwargs["params"]

        cookies = None
        if "cookies" in kwargs:
            cookies = kwargs["cookies"]

        redirect = False
        if "redirect" in kwargs:
            redirect = kwargs["redirect"]

        resp = self.session.request(
            method,
            url,
            headers=self.headers,
            params=payload,
            data=data,
            cookies=cookies,
            proxies=self.proxies,
            allow_redirects=redirect,
        )

        return resp
