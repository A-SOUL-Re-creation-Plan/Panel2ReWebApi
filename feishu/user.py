import time
import requests
from feishu.calendar import TenantAccessToken


class User(object):
    def __init__(self, app: TenantAccessToken):
        self._user_access_token = str()
        self._user_access_token_ts = int()
        self._user_access_token_expires = int()
        self._app = app
        self._tenant_key = str('10f3306f78451758')

    def codeResolve(self, code: str):
        url = 'https://open.feishu.cn/open-apis/authen/v1/oidc/access_token'
        payload = {
            'grant_type': 'authorization_code',
            'code': code
        }
        headers = {
            "Authorization": "Bearer " + self._app.tenant_access_token,
            "Content-Type": "application/json; charset=utf-8"
        }
        resp = requests.post(url=url, params=payload, headers=headers).json()
        self._user_access_token = resp.get('data').get('access_token')
        self._user_access_token_expires = resp.get('data').get('expires_in')
        self._user_access_token_ts = time.mktime(time.localtime())


    def getUserInfo(self):
        url = 'https://open.feishu.cn/open-apis/authen/v1/user_info'
        headers = {
            "Authorization": "Bearer " + self._user_access_token
        }
        resp = requests.get(url=url, headers=headers).json()
        r_d = dict()
        if resp.get('code') == 0:
            data = resp.get('data')
            r_d = {
                'name': data.get('name'),
                'avatar': data.get('avatar_url'),
                'open_id': data.get('open_id'),
            }
        return r_d
