import json
import os
import sys
import time
import hashlib
import uuid
import re
import sqlite3

from flask import Flask, request, redirect, Response, g
from flask_restful import Api, Resource
from flask_cors import CORS
from flask_httpauth import HTTPTokenAuth
import requests
from datetime import datetime, timedelta
from loguru import logger

from bili.bili_api import BiliApis
from as_config import *
from feishu.feishuapp import FeishuAuth
from feishu.calendar import FeishuCalendar
from feishu.user import FeishuUser
from utils import ColorConverter

app = Flask(__name__)
CORS(app)
api = Api(app)
auth = HTTPTokenAuth(header="Panel2Re-Authorization",scheme="")
version = 'V0.1.0'

class Panel2ReProgram(object):
    def __init__(self):
        # 2024.9.14 f**k Feishu Enterprise Plan
        # initialize Feishu and to do some testes
        # try:
        #     if os.path.exists('lark_bot.json'):
        #         with open('lark_bot.json', 'r') as f:
        #             bot_conf = json.load(f)
        #             app_id = bot_conf.get('app_id')
        #             app_secret = bot_conf.get('app_secret')
        #             self.huatuo_base = bot_conf.get('HuaTuoMLService')
        #             calendar = bot_conf.get('lark_calendarID')
        #             self.feishu_callback = bot_conf.get('lark_userCallbackURI')
        #             # FeishuAuth and FeishuCalendar
        #             self.feishu_auth = FeishuAuth(app_id, app_secret)
        #             self.feishu_calendar = FeishuCalendar(self.feishu_auth, calendar)
        #             logger.info(f"飞书AppInfo实例化完成.{self.feishu_auth.app_access_token}")
        #     else:
        #         raise FileNotFoundError()
        # except Exception as e:
        #     logger.warning(f"飞书企业自建应用凭据读取失败.{e}")
        #     raise FileNotFoundError()
        # initialize bili
        self.bili_cookie = dict()
        self.related_user_id = list()
        if os.path.exists('biliup.json'):
            '''
            格式: biliup-app / biliup-rs 导出的用户凭据
            '''
            with open('biliup.json', 'r') as f:
                biliup_json = json.loads(f.read())
                for i in biliup_json.get('cookie_info').get('cookies'):
                    self.bili_cookie[i.get('name')] = i.get('value')
                logger.info('从biliup-rs数据文件导入cookie')
        elif os.path.exists('user_data.json'):
            '''
            格式:
                {
                    "UID": {
                        "SESSDATA": "",
                        "bili_jct": "",
                        "DedeUserID": "",
                        "DedeUserID__ckMd5": "",
                        "sid": ""
                    }
                }
            '''
            with open('user_data.json', 'r') as f:
                self.bili_cookie = json.loads(f.read())
                self.bili_cookie = self.bili_cookie[list(self.bili_cookie.keys())[0]]
                logger.info("从JSON文件导入cookies")
        elif os.path.exists('cookies.txt'):
            '''
            格式样例: 哔哩哔哩主站浏览器控制台使用 `document.cookie` 查看
            '''
            with open('cookies.txt', 'r') as f:
                logger.info("从原始raw字符串导入cookies")
                cookie_raw = f.read()
                cookie_raw = cookie_raw.split('; ')
                for cookie in cookie_raw:
                    cookie = cookie.split('=')
                    self.bili_cookie[cookie[0]] = cookie[1]
        else:
            logger.error("找不到符合的Cookies文件。")
            sys.exit(0)
        logger.info('当前导入的用户UID:'+str(self.bili_cookie.get('DedeUserID')))
        # 加载受信成员ID
        with open('dynamic_config.json', 'r', encoding='utf-8') as f:
            bili_dynamic = json.loads(f.read())
            for item in bili_dynamic:
                self.related_user_id.append(item.get('bili_uid'))
        self.bili = BiliApis(cookies=self.bili_cookie)
        conn = sqlite3.connect('user.db')
        conn_cursor = conn.cursor()
        conn_cursor.execute("PRAGMA FOREIGN_KEYS=ON")
        conn_cursor.execute("CREATE TABLE IF NOT EXISTS user_auth(u_id INT PRIMARY KEY UNIQUE NOT NULL,u_name VARCHAR(70) NOT NULL,u_pwd VARCHAR(70) NOT NULL)")
        conn_cursor.execute("CREATE TABLE IF NOT EXISTS token(u_token VARCHAR(70) PRIMARY KEY UNIQUE,u_id INT,expire_at VARCHAR(20) NOT NULL)")
        conn_cursor.execute("CREATE TABLE IF NOT EXISTS user_info(u_id INT PRIMARY KEY UNIQUE NOT NULL,u_username VARCHAR(35) NOT NULL,u_avatar VARCHAR(220))")
        conn.commit()
        conn.close()

    def getBiliUserInfo(self, bili_uid):
        """
        获取用户信息，缓存在本地
        :param bili_uid: UID
        :return: 从bili获取的原JSON
        """
        if bili_uid not in self.related_user_id:
            raise NotImplementedError('ERR_NOT_A-SOUL_RELATED')
        # 缓存在本地，24小时刷新时限
        if os.path.exists('./cache/bili_user_' + bili_uid + '.json') and (
                datetime.now().timestamp() - os.stat(
            './cache/bili_user_' + bili_uid + '.json').st_mtime <= 60 * 60 * 24):
            data = json.load(open('./cache/bili_user_' + bili_uid + '.json', 'r'))
        else:
            data = program.bili.get_user_info(bili_uid)
            with open('./cache/bili_user_' + bili_uid + '.json', 'w') as f:
                json.dump(data, f)
                f.close()
        return data

@auth.verify_token
def verify_token(token):
    conn = sqlite3.connect('user.db')
    data = conn.cursor().execute("SELECT u_token,expire_at FROM token WHERE u_token='"+token+"'").fetchall()
    conn.cursor().execute("DELETE FROM token WHERE expire_at <= '"+ str(time.time()*1000) +"'")
    conn.commit()
    conn.close()
    if len(data) > 0:
        if int(data[0][1])/1000 > time.time():
            return token
        return False
    return False

@auth.error_handler
def auth_error(status):
    return {
        'code': 403,
        'msg': 'AUTH_FAILED'
    }, 403

class GetBiliList(Resource):
    @auth.login_required
    def get(self):
        """
        获取/刷新 dynamic_config中的用户的信息
        目前作用仅为刷新头像
        dynamic_config : 用于设置目标用户
        :return: 包含头像的信息
        """
        if not os.path.exists('dynamic_config.json'):
            open('dynamic_config.json', 'w').close()
        bili_dynamic = json.loads(open('dynamic_config.json', 'r', encoding='utf-8').read())
        for i in bili_dynamic:
            info = program.getBiliUserInfo(i['bili_uid'])
            i['avatar'] = info.get('data').get('card').get('face')
        return bili_dynamic


class GetBiliDynamic(Resource):
    @auth.login_required
    def get(self):
        """
        获取动态信息
        request-param uid: 要获取的用户的UID
        request-param offset: 动态页数（偏置）
        """
        uid = request.args.get("uid")
        offset = ""
        if request.args.get("offset"):
            offset = request.args.get("offset")
        # 仅接受以下几个用户
        if uid in program.related_user_id:
            return program.bili.get_dynamic_list(uid, offset)
        else:
            return {
                'errno': -1,
                'data': 'ERR_NOT_A-SOUL_RELATED'
            }, 403


class GetPubArchiveList(Resource):
    @auth.login_required
    def get(self):
        pn = int(request.args.get('pn'))
        ps = int(request.args.get('ps'))
        status = request.args.get('status')
        return program.bili.get_member_video_list(page=pn, size=ps, target_type=status)


class GetFeishuOrgCalendarList(Resource):
    def get(self):
        """
        飞书机器人关联组织公共日历事件列表获取
        request-config lark_bot.json:飞书自建机器人的app_id与app_secret键值
        """
        lark_cal = list()
        now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        first_day = str(int((now - timedelta(days=now.weekday())).timestamp()))
        end_day = str(int((now + timedelta(days=7 - now.weekday())).timestamp()))
        feishu_resp = program.feishu_calendar.get_event_list(start_timestamp=first_day,
                                                             end_timestamp=end_day,
                                                             user_access_token=str(auth.get_auth()).strip()
                                                             )
        # 提取API元数据并返回
        # 好狠的写法，我不改了（
        for i in feishu_resp:
            a = lark_cal_color.get(ColorConverter.int32ToHex(i.get('color'))) if lark_cal_color.get(ColorConverter.int32ToHex(i.get('color'))) else 'asoul'
            s = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(int(i.get('start_time').get('timestamp'))))
            e = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(int(i.get('end_time').get('timestamp'))))
            lark_cal_item = {
                'color': as_color.get(a),
                'live_title': i.get('description').replace('\n', ''),
                'title': i.get('summary'),
                'start': s,
                'end': e,
                'url': 'https://live.bilibili.com/' + as_liveroom.get(a),
                'live_owner': as_e2c.get(a),
                'live_owner_room': as_liveroom.get(a),
                'live_owner_space': as_space.get(a),
                'live_owner_full': as_e2bn.get(a)
            }
            if "双播" in i.get('summary') or '&' in i.get('summary'):
                name1, name2 = i.get('summary')[0:2], i.get('summary')[3:5]
                if name1 == as_e2c.get(a):
                    partner = as_c2e.get(name2)
                else:
                    partner = as_c2e.get(name1)
                lark_cal_item['partner'] = {
                    'partner_short': as_e2c.get(partner),
                    'partner_full': as_e2bn.get(partner),
                    'partner_space': as_space.get(partner),
                    'partner_liveroom': as_liveroom.get(partner)
                }
            lark_cal.append(lark_cal_item)
        return {
            'code': 200,
            'data': lark_cal
        }, 200


class GetPubArchiveDetail(Resource):
    @auth.login_required
    def get(self):
        bvid = request.args.get('bvid')
        return program.bili.get_member_info(bvid=bvid)


class GetVersion(Resource):
    def get(self):
        return version


class GetPubArchiveFailMsg(Resource):
    @auth.login_required
    def get(self):
        msg = 'PERMISSION_FAILED'
        try:
            msg = program.bili.get_rejection_reason(bvid=request.args.get('bvid'))
        except:
            return {
                'code': 400,
                'msg': '获取失败'
            }, 403
        return {
            'code': 200,
            'msg': program.bili.get_rejection_reason(bvid=request.args.get('bvid'))
        }


class GetFeishuUserAuthURI(Resource):
    def get(self):
        x_f_f = request.headers.get('X-Forwarded-For')
        if x_f_f is not None:
            if x_f_f == '127.0.0.1':
                return_uri = 'http://localhost:1213/api/lark_user_callback'
            else:
                return_uri = program.feishu_callback
        else:
            return_uri = 'http://localhost:1211/api/lark_user_callback'
        uri = f'https://open.feishu.cn/open-apis/authen/v1/authorize?app_id={program.feishu_auth.app_id}&scope=auth:user.id:read calendar:calendar&redirect_uri={return_uri}'
        return {
            'u_auth_uri': uri
        }


class GetFeishuLoginCallback(Resource):
    def get(self):
        if request.args.get('error'):
            return redirect('/', code=302)
        code = request.args.get('code') if request.args.get('code') else ''
        data = '<script>location.replace("/#/user/lark_sso_callback?code=' + code + '")</script>'
        resp = Response(data)
        resp.headers['Content-Type'] = 'text/html;charset=utf-8'
        return resp


class GetFeishuUserInfo(Resource):
    def get(self):
        if request.args.get('error') == 'access_denied':
            return {
                'code': 403,
                'data': 'LARK_ACCESS_DENIED',
            }
        code = request.args.get('code')
        u = FeishuUser(app=program.feishu_auth)
        u.codeResolve(code)
        return {
            'code': 0,
            'data': u.getUserInfo()
        }


class GetHuaTuoMLUploadImg(Resource):
    @auth.login_required
    def get(self):
        return {
            "code": 405,
            "msg": 'METHOD_NOT_ALLOWED'
        }, 405

    @auth.login_required
    def post(self):
        file = request.files['file']
        ct = file.content_type
        if 'image' not in ct:
            return {
                'code': 418,
                'msg': "NOT_TEA_INSIDE"
            }, 418
        md5_hash = hashlib.md5()
        chunk_size = 4096
        while chunk := file.read(chunk_size):
            md5_hash.update(chunk)
        file.seek(0)  # 读取完毕之后必须将文件指针复位否则写入为空
        if not os.path.exists('uploads'):
            os.mkdir('uploads')
        filename = 'uploads/img_' + md5_hash.hexdigest()[0:8] + '.png'
        file.save(filename)
        payload = {
            "path": os.path.abspath(filename),
            "calendar": program.feishu_calendar.calendar_id,
            "token": str(auth.get_auth()).strip()
        }
        html_return = requests.post(program.huatuo_base + '/create', params=payload)
        return {
            'code': html_return.status_code,
            'data': html_return.json()
        }, html_return.status_code


class GetHuaTuoMLLinkImg(Resource):
    @auth.login_required
    def get(self):
        return {
            "msg": 'METHOD_NOT_ALLOWED'
        }, 405

    @auth.login_required
    def post(self):
        data = json.loads(request.data)
        href = data.get('href').split('?')[0]
        if re.search("https*://[a-z][0-9].hdslb.com/bfs/new_dyn/([0-9)|[a-z])*\\.(jpg|gif|png)", href):
            if requests.get(href).status_code == 200:
                payload = {
                    "path": href,
                    "calendar": program.feishu_calendar.calendar_id,
                    "token": str(auth.get_auth()).strip()
                }
                html_return = requests.post(program.huatuo_base + '/create', params=payload)
                return {
                    'code': html_return.status_code,
                    'data': html_return.json()
                }, html_return.status_code
            else:
                return {
                    'code': 404,
                    'msg': 'DOWNLOAD_FAILED'
                }, 404
        return {
            'code': -1,
            'msg': 'IMG_LINK_DISMATCH'
        }, 500


class GetLarkUATRefreshResult(Resource):
    @auth.login_required
    def get(self):
        r_t = request.headers.get('Panel2Re-RefreshAuthorization')
        if not r_t:
            return {
                'code': 404,
                'msg': 'MISSING_ARGS'
            }, 404
        u = FeishuUser(app=program.feishu_auth)
        data = u.refreshToken(r_t)
        code = 500
        if(data.get('code')==0):
            code = 200
        return data,code


class GetHuaTuoMLStatus(Resource):
    @auth.login_required
    def get(self):
        uuid = request.args.get('uuid')
        if not uuid:
            return {
                'code': 404,
                'msg': 'MISSING_ARGS'
            }, 404
        return requests.get(program.huatuo_base + '/status', params={'uuid': uuid}).json()


class GetHuaTuoMLOutput(Resource):
    @auth.login_required
    def get(self):
        if not request.args.get('uuid'):
            return {
                'code': 404,
                'msg': 'MISSING_ARGS'
            }
        r = requests.get(program.huatuo_base + '/output', params={'uuid': request.args.get('uuid')}, stream=True).json()
        return {
            'code': 0,
            'data': r.get('fileContents')
        }


class GetBiliQRCode(Resource):
    @auth.login_required
    def get(self):
        return program.bili.get_new_qrcode()


class GetBiliQRStatus(Resource):
    @auth.login_required
    def get(self):
        return program.bili.check_qrcode(request.args.get('key'))
    
class LegacyLoginApi(Resource):
    def get(self):
        return {
            'code': 405,
            'msg': 'METHOD_NOT_ALLOWED'
        },405
    def post(self):
        post_data = request.json.get('data')
        if post_data.get('diana_subscribed') == False or post_data.get('diana_subscribed') == None:
            return {
                'code': 307,
                'msg': 'SUBSCRIBE_DIANA_FIRST'
            },500
        
        conn = sqlite3.connect('user.db')
        c = conn.cursor()
        data = c.execute("SELECT * FROM user_auth WHERE u_name = '" + post_data.get('id') + "' AND u_pwd = '"+ hashlib.sha256(bytes(str(post_data.get('pwd')),'utf-8')).hexdigest() +"'").fetchall()
        if len(data) == 0:
            return {
                'code': 403,
                'msg': 'DISMATCHING_USERNAME_PWD'
            },403
        else:
            data_ui = c.execute("SELECT u_id,u_username,u_avatar FROM user_info WHERE u_id = 1").fetchall()[0]
            new_token = "2Re-" + hashlib.sha256(bytes(str(uuid.uuid4()),'utf-8')).hexdigest()[0:15]
            new_expire = int(time.time() + 604800) * 1000
            c.execute("INSERT INTO token (u_token,u_id,expire_at) VALUES ('"+new_token+"','"+str(data_ui[0])+"','"+str(new_expire)+"')")
            conn.commit()
            return {
                'code': 0,
                'data': {
                    'user_info': {
                        "id": data_ui[0],
                        "username": data_ui[1],
                        "avatar": data_ui[2],
                    },
                    'token': new_token,
                    'expire_at': new_expire
                }
            },200

class LegacyLogoutApi(Resource):
    @auth.login_required
    def delete(self):
        token = auth.current_user()
        conn = sqlite3.connect('user.db')
        conn.cursor().execute("DELETE FROM token WHERE u_token = '"+token+"'")
        conn.close()
        return {'code':0,'msg':'BACK_TO_UNiVERSE'}

class LegacyRegisterApi(Resource):  # only for single user "admin"
    def get(self):
        conn = sqlite3.connect('user.db')
        conn_cursor = conn.cursor()
        u_count = conn_cursor.execute('SELECT u_id from user_info').fetchall()
        conn_cursor.close()
        if len(u_count)>=1 and os.path.exists('user.db'):
            return {
                "code": -1,
                "msg": 'REGISTER_DISABLED'
            }, 403
        else:
            return {
                "code": 1,
                "msg": "REGISTER_OPEN"
            }, 200
    
    def post(self):
        conn = sqlite3.connect('user.db')
        conn_cursor = conn.cursor()
        u_count = conn_cursor.execute('SELECT u_id from user_info').fetchall()
        if len(u_count)>=1:
            conn_cursor.close()
            return {
                "code": -1,
                "msg": 'REGISTER_DISABLED'
            }, 403
        else:
            conn = sqlite3.connect('user.db')
            conn_cursor = conn.cursor()
            post_data = request.json.get('data')
            if post_data.get('diana_subscribed') == False or post_data.get('diana_subscribed') == None:
                return {
                    'code': 307,
                    'msg': 'SUBSCRIBE_DIANA_FIRST'
                },500
            elif post_data.get('pwd') != post_data.get('pwd_again'):
                return {
                    'code': 403,
                    'msg': "DIFFERENT_TWO_PWDS"
                }
            conn_cursor.execute("PRAGMA FOREIGN_KEYS=ON")
            if len(conn_cursor.execute("SELECT * FROM user_auth where u_id = 1").fetchall()) == 0:
                conn_cursor.execute("INSERT INTO user_auth (u_id,u_name,u_pwd) VALUES (1,'admin','" + hashlib.sha256(bytes(post_data.get('pwd'),'utf-8')).hexdigest() +"');")
            conn_cursor.execute("INSERT INTO user_info (u_id,u_username,u_avatar) VALUES (1,'Panel2Re','https://s1-imfile.feishucdn.com/static-resource/v1/v2_2b167f57-26ad-45f1-8231-90a0b331f2ag~')")
            conn.commit()
            conn.close()
            return {
                "code": 0,
                "msg": "REGISTER_SUCCESS"
            }, 200
        
api.add_resource(GetBiliList, '/bili_dynamic')
api.add_resource(GetVersion, '/version')
api.add_resource(GetBiliDynamic, '/bili_dynamics')
# api.add_resource(GetASWeeklySchedule, '/weekly_schedule')
api.add_resource(GetPubArchiveList, '/bili_archives')
api.add_resource(GetPubArchiveDetail, '/bili_archives_detail')
api.add_resource(GetPubArchiveFailMsg, '/bili_xcode_msg')
api.add_resource(GetFeishuOrgCalendarList, '/lark_calendar_list')
# api.add_resource(GetFeishuUserAuthURI, '/lark_auth_uri')
# api.add_resource(GetFeishuUserInfo, '/lark_identity')
# api.add_resource(GetFeishuLoginCallback, '/lark_user_callback')
# api.add_resource(GetHuaTuoMLUploadImg, '/lark_calendar_parse/img')
# api.add_resource(GetHuaTuoMLLinkImg, '/lark_calendar_parse/link')
# api.add_resource(GetHuaTuoMLStatus, '/lark_calendar_parse/status')
# api.add_resource(GetHuaTuoMLOutput, '/lark_calendar_parse/output')
# api.add_resource(GetLarkUATRefreshResult, '/lark_refresh_uat')
api.add_resource(GetBiliQRCode, '/bili_qrcode')
api.add_resource(GetBiliQRStatus, '/bili_qrpool')
api.add_resource(LegacyLoginApi,'/user/login_legacy')
api.add_resource(LegacyLogoutApi,'/user/logout_legacy')
api.add_resource(LegacyRegisterApi,'/user/register_legacy')


# api.add_resource(proxyBiliImage, '/bili_img_proxy')

@app.route('/')
def index():
    return 'Panel2Re is running.\n%s<br/>It works, but why?' % version


if __name__ == '__main__':
    program = Panel2ReProgram()
    if os.environ.get('FOR_ELECTRON_API'):
        app.run(host='127.0.0.1', port=3007, debug=False)
    else:
        app.run(host='0.0.0.0', port=3007, debug=True)
