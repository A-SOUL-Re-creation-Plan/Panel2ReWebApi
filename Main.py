import json
import os
import sys

from flask import Flask, request
from flask_restful import Api, Resource
from flask_cors import CORS
import requests
from bili.bili_wbi import getWBI
from datetime import datetime

app = Flask(__name__)
CORS(app)
api = Api(app)
version = 'V0.0.1_006b9ba6'
base_URL = 'http://127.0.0.1:3007'

bili_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.1.4.514 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Origin": "https://www.bilibili.com/",
    "Pregma": "no-cache",
    "Cache-Control": "max-age=0",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-User": "?1",
    "Sec-Fetch-Dest": "document",
    # "Cookie": "",
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept-Encoding": "",
    "Connection": "keep-alive"
}

bili_cookie = {}


def importBiliCookie():
    global bili_cookie
    if os.path.exists('cookies.json'):
        with open('cookies.json', 'r') as f:
            print("Import from JSON")
            bili_cookie = json.loads(f.read())
    else:
        if os.path.exists('cookies.txt'):
            with open('cookies.txt', 'r') as f:
                print("Import from raw cookie string")
                cookie_raw = f.read()
                cookie_raw = cookie_raw.split('; ')
                for cookie in cookie_raw:
                    cookie = cookie.split('=')
                    bili_cookie[cookie[0]] = cookie[1]
        else:
            print("Cookie file not found")
            sys.exit(0)


def getBiliUserInfo(bili_uid):
    if os.path.exists('bili_user_' + bili_uid + '.json') and (
            datetime.now().timestamp() - os.stat('bili_user_' + bili_uid + '.json').st_mtime <= 60 * 60 * 24):
        data = json.load(open('bili_user_' + bili_uid + '.json', 'r'))
    else:
        params = {
            'mid': bili_uid
        }
        params = getWBI(params)
        data = requests.get('https://api.bilibili.com/x/space/wbi/acc/info', params=params,
                            headers=bili_headers, cookies=bili_cookie).json()
        with open('bili_user_' + bili_uid + '.json', 'w') as f:
            json.dump(data, f)
            f.close()
    return data


# Not Safe
# class proxyBiliImage(Resource):
#     def get(self):
#         addr = request.args.get("img")
#         if re.search("https://i[0-9].hdslb.com/(jpg|webp|avif|png|gif)*", addr):
#             temp = addr.split('/')
#             filename = temp[len(temp) - 1]
#             # print(filename)
#             if os.path.exists('cache/' + filename):
#                 if os.stat('cache/' + filename).st_size == 0:
#                     os.remove('cache/' + filename)
#             if not os.path.exists('cache'):
#                 os.mkdir('cache')
#             if not (os.path.exists('cache/' + filename)):
#                 try:
#                     data = requests.get(addr, headers=bili_headers).content
#                 except Exception as e:
#                     return e
#                 with open('cache/' + filename, 'wb') as f:
#                     f.write(data)
#                     f.close()
#             with open('cache/' + filename, 'rb') as f:
#                 res = f.read()
#                 f.close()
#             resp = Response(res, mimetype='application/octet-stream')
#             return resp
#         else:
#             return "FAILED", 500


class getBiliList(Resource):
    def get(self):
        if not os.path.exists('dynamic_config.json'):
            open('dynamic_config.json', 'w').close()
        bili_dynamic = json.loads(open('dynamic_config.json', 'r', encoding='utf-8').read())
        if request.args.get("refresh") == '1':
            # shutil.rmtree('cache')
            # for i in bili_dynamic:
            #     print("deleted" + str(i["bili_uid"]))
            #     os.remove('bili_user_' + i['bili_uid'] + '.json')
            for root, dirs, files in os.walk('.'):
                for name in files:
                    if name.startswith('bili_user_'):
                        if name.endswith('.json'):
                            print(os.path.join(root, name))
                            os.remove(os.path.join(root, name))

        for i in bili_dynamic:
            # i['avatar'] = base_URL + "/bili_img_proxy?img=" + getBiliUserInfo(i['bili_uid'])['data']['face']
            i['avatar'] = getBiliUserInfo(i['bili_uid'])['data']['face']
            # time.sleep(3)
        return bili_dynamic


class getBiliDynamic(Resource):
    def get(self):
        uid = request.args.get("uid")
        a_uid = ['547510303', '672353429', '672346917', '672328094', '672342685', '703007996', '3493085336046382']
        if uid in a_uid:
            params = {
                'host_mid': request.args.get('uid')
            }
            data = json.loads(requests.get('https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space',
                                           headers=bili_headers, params=params, cookies=bili_cookie)
                              .text)
            return data['data']['items']
        else:
            return {'errno': -1, 'data': 'ERR_NOT_A-SOUL_RELATED'}, 403

class getASWeeklySchedule(Resource):
    def get(self):
        return {
            "code": 0,
            "data": [
                {
                    'title': '嘉然单播',
                    'url': 'https://live.bilibili.com/22637261',
                    'start': '2024-06-05T19:20:00Z',
                    'end': '2024-06-05T20:40:00Z',
                    'allDay': False,
                },
                {
                    'title': '贝拉单播',
                    'url': 'https://live.bilibili.com/22632424',
                    'start': '2024-06-05T20:50:00Z',
                    'end': '2024-06-05T22:10:00Z',
                    'allDay': False,
                },
                {
                    'title': '贝拉单播',
                    'url': 'https://live.bilibili.com/22632424',
                    'start': '2024-06-06T19:20:00Z',
                    'end': '2024-06-06T20:40:00Z',
                    'allDay': False,
                },
                {
                    'title': '乃琳单播',
                    'url': 'https://live.bilibili.com/22625027',
                    'start': '2024-06-06T20:50:00Z',
                    'end': '2024-06-06T22:10:00Z',
                    'allDay': False,
                },
                {
                    'title': 'A-SOUL游戏室',
                    'url': 'https://live.bilibili.com/22625027',
                    'start': '2024-06-08T19:50:00Z',
                    'end': '2024-06-08T22:00:00Z',
                    'allDay': False,
                },
                {
                    'title': 'A-SOUL游戏室',
                    'url': 'https://live.bilibili.com/22625027',
                    'start': '2024-06-08T19:50:00Z',
                    'end': '2024-06-08T22:00:00Z',
                    'allDay': False,
                },
                {
                    'title': 'A-SOUL游戏室',
                    'url': 'https://live.bilibili.com/22625027',
                    'start': '2024-06-08T19:50:00Z',
                    'end': '2024-06-08T22:00:00Z',
                    'allDay': False,
                },
                {
                    'title': 'A-SOUL游戏室',
                    'url': 'https://live.bilibili.com/22625027',
                    'start': '2024-06-08T19:50:00Z',
                    'end': '2024-06-08T22:00:00Z',
                    'allDay': False,
                },
            ]
        }

class getVersion(Resource):
    def get(self):
        return version


api.add_resource(getBiliList, '/bili_dynamic')
api.add_resource(getVersion, '/version')
api.add_resource(getBiliDynamic, '/bili_dynamics')
api.add_resource(getASWeeklySchedule, '/weekly_schedule')


# api.add_resource(proxyBiliImage, '/bili_img_proxy')

@app.route('/')
def index():
    return 'Panel2Re is running.\nBackend version: %s' % version


if __name__ == '__main__':
    importBiliCookie()
    app.run(host='0.0.0.0', port=3007, debug=True)
