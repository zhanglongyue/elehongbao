import configparser
import datetime
import json
import re
import threading
from urllib.parse import unquote
import itchat, time
import os
import requests
import threadpool
from itchat.content import *


def initUser(configName):
    user = {}
    user['nickname'] = conf.get(configName, 'nickname')
    user['cookies'] = {}
    UserCookies = conf.get(configName, 'cookies').replace(' ', '')
    for cookie in UserCookies.split(';'):
        kv = cookie.split('=')
        user['cookies'][kv[0]] = kv[1]
        if 'snsInfo' in kv[0]:
            user['sign'] = re.findall('(?<=eleme_key%22%3A%22).+?(?=%22%2C%22)', kv[1])[0]
            user['openid'] = re.findall('(?<=openid%22%3A%22).+?(?=%22%2C%22)', kv[1])[0]
            user['unionid'] = re.findall('(?<=unionid%22%3A%22).+?(?=%22%2C%22)', kv[1])[0]
            user['weixin_avatar'] = unquote(re.findall('(?<=headimgurl%22%3A%22).+?(?=%22%2C%22)', kv[1])[0])
            requestData(user)
    return user


def requestData(user):
    user['data'] = '{"method": "phone", "group_sn":"%s", ' + '"sign": "%s", "phone": "",' \
                    '"device_id": "", "hardware_id": "", "platform": 0, "track_id": "undefined",' \
                    '"weixin_avatar": "%s","weixin_username": "%s", "unionid": "%s"}' \
                     % (user['sign'], user['weixin_avatar'], user['nickname'], user['unionid'])

# 打印红包信息
def infoPrint(response, count, lucky_num, sn):
    msg = []
    [msg.append({i['sns_username']: i['amount']}) for i in response['promotion_records']]
    print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), threading.currentThread().name,
          "监控数%d 红包%s 进度%d/%d 信息%s" % (len(hongbao), sn, count, lucky_num, str(msg)))

# 查询红包进度，默认会领取红包，该方法将使用微信小号cookie
def hognbaoQuery(lucky_num, sn):
    hongbao.add(sn)
    session = requests.session()
    while 1:
        content = session.post('https://h5.ele.me/restapi/marketing/promotion/weixin/%s' % (queryUser['openid']),
                               cookies=queryUser['cookies'], data=queryUser['data'] % (sn)).content
        content = str(content, "utf-8")
        jsons = json.loads(content)
        count = len(jsons['promotion_records'])
        if getUser['nickname'] in str(jsons):
            print("这个红包你已经抢过了")
            infoPrint(jsons, count, lucky_num, sn)
            hongbao.remove(sn)
            break
        else:
            infoPrint(jsons, count, lucky_num, sn)

            # 根据大红包进度做后续处理
            if count == lucky_num - 1:
                # 下一个是大红包！
                hongbaoGet(lucky_num, sn)
                hongbao.remove(sn)
                print("获得大红包!")
                break
            elif count >= lucky_num:
                hongbao.remove(sn)
                print("最佳红包已被领取!")
                break
            elif count < lucky_num:
                session.close()
                time.sleep(SECONDS)


# 领取红包，该方法将使用需要获得大红包的用户cookie
def hongbaoGet(lucky_num, sn):
    session = requests.session()
    getUser['nickname'] = getUser['nickname'] + str(int(time.time()))
    requestData(getUser)
    content = session.post('https://h5.ele.me/restapi/marketing/promotion/weixin/%s' % (getUser['openid']),
                           cookies=getUser['cookies'], data=getUser['data'] % (sn)).content
    content = str(content, "utf-8")
    jsons = json.loads(content)
    count = len(jsons['promotion_records'])
    infoPrint(jsons, count, lucky_num, sn)
    session.close()


def hongbaoFinder(msg):
    if "饿了么" in str(msg) and "红包" in str(msg):
        lucky_num = int(re.findall('(?<=第).+?(?=个)', str(msg))[0])
        sn = re.findall('(?<=;sn=).+?(?=&amp;)', str(msg))[0]
        if sn not in hongbao:
            requests = threadpool.makeRequests(hognbaoQuery, [([lucky_num, sn], None)])
            [pool.putRequest(req) for req in requests]
            print("收到饿了么红包 幸运位%d 红包ID %s" % (lucky_num, sn))
        else:
            print("已经在监控该红包 幸运位%d 红包ID %s" % (lucky_num, sn))


@itchat.msg_register([TEXT, MAP, CARD, NOTE, SHARING])
def text_reply(msg):
    hongbaoFinder(msg)


@itchat.msg_register([TEXT, MAP, CARD, NOTE, SHARING], isGroupChat=True)
def text_reply(msg):
    hongbaoFinder(msg)


if __name__ == '__main__':
    cur_path = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(cur_path, 'config.ini')
    conf = configparser.RawConfigParser()
    conf.read(config_path, encoding="utf8")

    # 查询间隔时间
    SECONDS = conf.getint('BaseConfig', 'seconds')
    # 默认线程池大小50
    pool = threadpool.ThreadPool(50)
    # 初始化查询红包信息的用户数据
    queryUser = initUser('queryUser')
    # 初始化领取大红包的用户数据
    getUser = initUser('getUser')

    hongbao = set([])
    itchat.auto_login(True)
    itchat.run(True)
