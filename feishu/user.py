import time
import requests
from feishu.calendar import FeishuApp

class FeishuUser(object):
    def __init__(self, app: FeishuApp):
        self._user_access_token = str()
        self._user_access_token_ts = int()
        self._user_access_token_expires = int()
        self._app = app
        self._refresh_token = str()
        self._refresh_token_ts = str()
        self._refresh_token_expires = str()
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
        self._user_access_token_expires = int(resp.get('data').get('expires_in'))
        self._user_access_token_ts = int(time.mktime(time.localtime()))
        self._refresh_token = resp.get('data').get('refresh_token')
        self._refresh_token_ts = int(time.mktime(time.localtime()))
        self._refresh_token_expires = int(resp.get('data').get('refresh_expires_in'))

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
                'user_access_token': self._user_access_token,
                'refresh_token': self._refresh_token,
                'at_expires_at': self._user_access_token_expires + self._user_access_token_ts,
                'rt_expires_at': self._refresh_token_ts + self._refresh_token_expires
            }
        return r_d

    def refreshToken(self, refresh_token: str):
        url = 'https://open.feishu.cn/open-apis/authen/v1/oidc/refresh_access_token'
        headers = {
            'Authorization': 'Bearer ' + self._app.app_access_token,
            'Content-Type': 'application/json; charset=utf-8'
        }
        payload = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }
        resp = requests.post(url=url, params=payload, headers=headers).json()
        if resp.get('code') == 0:
            new_token = {
                'code': 0,
                'data': {
                    'access_token': resp.get('data').get('access_token'),
                    'refresh_token': resp.get('data').get('refresh_token'),
                    'at_expires_at': resp.get('data').get('expires_in')+int(time.mktime(time.localtime())),
                    'rt_expires_at': resp.get('data').get('refresh_expires_in')+int(time.mktime(time.localtime())),
                }
            }
            return new_token
        return {'code': -1, 'data': None}