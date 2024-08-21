import json
import os
import sys
import time
import hashlib
import re

from flask import Flask, request, redirect, Response
from flask_restful import Api, Resource
from flask_cors import CORS
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
version = 'V0.0.1_9d237d40'


class Panel2ReProgram(object):
    def __init__(self):
        # initialize Feishu and to do some testes
        try:
            if os.path.exists('lark_bot.json'):
                with open('lark_bot.json', 'r') as f:
                    bot_conf = json.load(f)
                    app_id = bot_conf.get('app_id')
                    app_secret = bot_conf.get('app_secret')
                    self.huatuo_base = bot_conf.get('HuaTuoMLService')
                    calendar = bot_conf.get('lark_calendarID')
                    self.feishu_callback = bot_conf.get('lark_userCallbackURI')
                    # FeishuAuth and FeishuCalendar
                    self.feishu_auth = FeishuAuth(app_id, app_secret)
                    self.feishu_calendar = FeishuCalendar(self.feishu_auth, calendar)
                    logger.info(f"飞书AppInfo实例化完成.{self.feishu_auth.app_access_token}")
            else:
                raise FileNotFoundError()
        except Exception as e:
            logger.warning(f"飞书企业自建应用凭据读取失败.{e}")
            raise FileNotFoundError()
        # initialize bili
        self.bili_cookie = dict()
        self.related_user_id = list()
        if os.path.exists('user_data.json'):
            with open('user_data.json', 'r') as f:
                self.bili_cookie = json.loads(f.read())
                self.bili_cookie = self.bili_cookie[list(self.bili_cookie.keys())[0]]
                logger.info("从JSON文件导入cookies")
        elif os.path.exists('cookies.txt'):
            with open('cookies.txt', 'r') as f:
                logger.info("从原始raw字符串导入cookies")
                cookie_raw = f.read()
                cookie_raw = cookie_raw.split('; ')
                for cookie in cookie_raw:
                    cookie = cookie.split('=')
                    self.bili_cookie[cookie[0]] = cookie[1]
        else:
            logger.error("找不到符合的Cookies文件")
            sys.exit(0)
        # 加载受信成员ID
        with open('dynamic_config.json', 'r', encoding='utf-8') as f:
            bili_dynamic = json.loads(f.read())
            for item in bili_dynamic:
                self.related_user_id.append(item.get('bili_uid'))
        self.bili = BiliApis(cookies=self.bili_cookie)

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


class GetBiliList(Resource):
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
            i['avatar'] = program.getBiliUserInfo(i['bili_uid'])['data']['face']
        return bili_dynamic


class GetBiliDynamic(Resource):
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
        if not request.headers.get('Panel2Re-Authorization'):
            return {
                'code': 403,
                'msg': 'NOT_AUTHORIZED'
            }, 403
        lark_cal = list()
        now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        first_day = str(int((now - timedelta(days=now.weekday())).timestamp()))
        end_day = str(int((now + timedelta(days=7 - now.weekday())).timestamp()))
        feishu_resp = program.feishu_calendar.get_event_list(start_timestamp=first_day,
                                                             end_timestamp=end_day,
                                                             user_access_token=request.headers.get(
                                                                 'Panel2Re-Authorization'
                                                             ))
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
    def get(self):
        bvid = request.args.get('bvid')
        return program.bili.get_member_info(bvid=bvid)


class GetVersion(Resource):
    def get(self):
        return version


class GetPubArchiveFailMsg(Resource):
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
                return_uri = 'http://127.0.0.1:1213/api/lark_user_callback'
            else:
                return_uri = program.feishu_callback
        else:
            return_uri = 'http://127.0.0.1:1211/api/lark_user_callback'
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
    def get(self):
        return {
            "code": 405,
            "msg": 'METHOD_NOT_ALLOWED'
        }, 405

    def post(self):
        if not request.headers.get('Panel2Re-Authorization'):
            return {
                'code': 403,
                'msg': "ACCESS_DENIED"
            }, 403
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
            "token": request.headers.get('Panel2Re-Authorization')
        }
        html_return = requests.post(program.huatuo_base + '/create', params=payload)
        return {
            'code': html_return.status_code,
            'data': html_return.json()
        }, html_return.status_code


class GetHuaTuoMLLinkImg(Resource):
    def get(self):
        return {
            "msg": 'METHOD_NOT_ALLOWED'
        }, 405

    def post(self):
        if not request.headers.get('Panel2Re-Authorization'):
            return {
                'code': 403,
                'msg': "ACCESS_DENIED"
            }, 403
        data = json.loads(request.data)
        href = data.get('href').split('?')[0]
        if re.search("https*://[a-z][0-9].hdslb.com/bfs/new_dyn/([0-9)|[a-z])*\\.(jpg|gif|png)", href):
            if requests.get(href).status_code == 200:
                payload = {
                    "path": href,
                    "calendar": program.feishu_calendar.calendar_id,
                    "token": request.headers.get('Panel2Re-Authorization')
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
    def get(self):
        uuid = request.args.get('uuid')
        if not uuid:
            return {
                'code': 404,
                'msg': 'MISSING_ARGS'
            }, 404
        return requests.get(program.huatuo_base + '/status', params={'uuid': uuid}).json()


class GetHuaTuoMLOutput(Resource):
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
    def get(self):
        return program.bili.get_new_qrcode()


class GetBiliQRStatus(Resource):
    def get(self):
        return program.bili.check_qrcode(request.args.get('key'))


api.add_resource(GetBiliList, '/bili_dynamic')
api.add_resource(GetVersion, '/version')
api.add_resource(GetBiliDynamic, '/bili_dynamics')
# api.add_resource(GetASWeeklySchedule, '/weekly_schedule')
api.add_resource(GetPubArchiveList, '/bili_archives')
api.add_resource(GetPubArchiveDetail, '/bili_archives_detail')
api.add_resource(GetPubArchiveFailMsg, '/bili_xcode_msg')
api.add_resource(GetFeishuOrgCalendarList, '/lark_calendar_list')
api.add_resource(GetFeishuUserAuthURI, '/lark_auth_uri')
api.add_resource(GetFeishuUserInfo, '/lark_identity')
api.add_resource(GetFeishuLoginCallback, '/lark_user_callback')
api.add_resource(GetHuaTuoMLUploadImg, '/lark_calendar_parse/img')
api.add_resource(GetHuaTuoMLLinkImg, '/lark_calendar_parse/link')
api.add_resource(GetHuaTuoMLStatus, '/lark_calendar_parse/status')
api.add_resource(GetHuaTuoMLOutput, '/lark_calendar_parse/output')
api.add_resource(GetLarkUATRefreshResult, '/lark_refresh_uat')
api.add_resource(GetBiliQRCode, '/bili_qrcode')
api.add_resource(GetBiliQRStatus, '/bili_qrpool')


# api.add_resource(proxyBiliImage, '/bili_img_proxy')

@app.route('/')
def index():
    return 'Panel2Re is running.\n%s<br/>It works, but why?' % version


if __name__ == '__main__':
    program = Panel2ReProgram()
    app.run(host='0.0.0.0', port=3007, debug=True)
