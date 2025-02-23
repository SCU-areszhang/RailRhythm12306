# Rail Rhythm 中国铁路时刻表查询工具
# wj_0575 2025.1
import copy
import os.path
import re
import time

import requests
import json
import threading

from datetime import datetime
current_date = datetime.now()
auto_date = current_date.strftime("%Y-%m-%d")
auto_date_1 = auto_date.replace("-","")
# 这是默认时间参数
# 12306一个系统居然有两种表示日期的方法

train_list = {} # reference from train_no to detailed information
lock_train_list = threading.Lock()

no_list = {} # reference from train code to train_no
lock_no_list = threading.Lock()

task_callback = {"success": 0, "failed": 0, "data":[]}
lock_task_callback = threading.Lock() # 记录多线程爬取的状态

headers = {
    "Accept":"*/*",
    "Connection":"keep-alive",
    "Origin":"https://kyfw.12306.cn",
    "Referer":"https://kyfw.12306.cn/",
    "Sec-Fetch-Dest":"empty",
    "Sec-Fetch-Mode":"cors",
    "Sec-Fetch-Site":"same-site",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0"
}

def time_interval(time_start, time_end):
    """计算时间间隔的函数，输入的两个时间必须是hh:mm格式，时间单位为分，可以处理跨午夜的情况"""
    start_hour = int(time_start[0:2])
    start_minute = int(time_start[3:5])
    end_hour = int(time_end[0:2])
    end_minute = int(time_end[3:5])
    start_total = start_hour * 60 + start_minute
    end_total = end_hour * 60 + end_minute
    if end_total >= start_total:
        interval = end_total - start_total
    else:
        interval = 24 * 60 - start_total + end_total
    return interval

def line_cut():
    print("------------------------------------------------------------")

def count_code():
    """用来统计车次数量的函数，无返回值"""
    line_cut()
    print("Train sum:\t", len(no_list), '\t(', len(train_list), ')')
    cnt_code = {'G prefix': 0, 'D prefix': 0, 'C prefix': 0, 'Z prefix': 0, 'T prefix': 0,
                'K prefix': 0, 'S prefix': 0, 'Y prefix': 0, 'Pure number': 0, }
    cnt_train = {'G prefix': 0, 'D prefix': 0, 'C prefix': 0, 'Z prefix': 0, 'T prefix': 0,
                 'K prefix': 0, 'S prefix': 0, 'Y prefix': 0, 'Pure number': 0, }
    check = {'G prefix': 3600, 'D prefix': 2000, 'C prefix': 2000, 'Z prefix': 160, 'T prefix': 100,
                 'K prefix': 800, 'S prefix': 700, 'Y prefix': 1, 'Pure number': 200, }
    for train in no_list:
        if train[0].isdigit():
            cnt_code['Pure number'] += 1
        else:
            cnt_code[train[0] + ' prefix'] += 1
    for train in train_list:
        if train_list[train][0]["station_train_code"][0].isdigit():
            cnt_train['Pure number'] += 1
        else:
            cnt_train[train_list[train][0]["station_train_code"][0] + ' prefix'] += 1
    for prefix in cnt_code:
        if cnt_train[prefix] > check[prefix]:
            print("   ", prefix + "\t", cnt_code[prefix], '\t(', cnt_train[prefix], ')')
        else:
            print(" ? ", prefix + "\t", cnt_code[prefix], '\t(', str(cnt_train[prefix]) , ')')
    line_cut()

def print_train(x):
    """这个函数用于输出一个车次的信息
    参数x为一个字典"""
    code = x[0]["station_train_code"]
    callback = {}
    line_cut()
    print(code,end=' ')
    for i in x:
        if i["station_train_code"] != code:
            print("/", i["station_train_code"], end='')
            break
    print(" ",x[0]["train_class_name"], "\t", x[0]["start_station_name"], "-",
          x[0]["end_station_name"])
    d = "0"
    for i in x:
        print(i["station_no"]+" "+i["station_name"].ljust(5,' ')+'\t',
              i["arrive_time"].ljust(7,' '),end='')
        if "is_start" in i:
            print(i["start_time"].ljust(5,' '),end='')
        elif i == x[-1]:
            print("----        ",end='')
        else:
            print(i["start_time"].ljust(5,' ')+str(i["stop_time"]).rjust(4,' ')+'\'',end='  ')
        callback[i["station_no"]] = "Station "+i["station_name"]
        if i["arrive_day_diff"] != d:
            d = i["arrive_day_diff"]
            print("Day",int(d)+1,end="  ")
        if i["station_train_code"] != code:
            code = i["station_train_code"]
            print("switch to",code,end="  ")
        print("",end="\n")
    for i in x:
        for j in x:
            if i == j:
                continue
            callback[i["station_no"] + "-" + j["station_no"]] = i["station_name"] + "-" + j["station_name"]
    line_cut()
    return callback

def search_station(x, t1='00:00', t2='24:00', sort_order = "", prefix = "GDCKTZSYP"):
    """这个函数用来查找车站的时刻表
    在sort_order中，如果包含up/dn，说明需要显示上/下行车次
    如果包含st/ed/ps，说明需要显示始发/终到/过路车次"""
    line_cut()
    sort_order.lower()
    tail = []
    if "up" in sort_order:
        tail.extend(list("24680"))
    if "dn" in sort_order:
        tail.extend(list("13579"))
    if len(tail) == 0:
        tail = list("1234567890")
    st = "st" in sort_order
    ed = "ed" in sort_order
    ps = "ps" in sort_order
    if st == False and ed == False and ps == False:
        st = ed = ps = True
    table = {}
    cnt = 0
    visible = 0
    for i in train_list:
        for j in train_list[i]:
            if j["station_name"] == x and j["start_time"] >= t1 and j["start_time"] <= t2:
                table[j["start_time"]+str(cnt)] = {
                    "code": j["station_train_code"],
                    "start_time": j["start_time"],
                    "arrive_time": j["arrive_time"],
                    "stop_time": j["stop_time"],
                    "st": train_list[i][0]["start_station_name"],
                    "ed": train_list[i][0]["end_station_name"],
                    "class": train_list[i][0]["train_class_name"]
                }
                cnt += 1
    if cnt == 0:
        print("Unable to find station \"" + x + "\" please check input or load data first")
        line_cut()
        return {}
    print(x, '\t', t1, '-', t2, "\t", cnt, "results")
    callback = {}
    for i in sorted(table.keys()):
        if (table[i]["code"][-1:] in tail) == False:
            continue
        if (("P" in prefix and table[i]["code"][0].isdigit or table[i]["code"][0] in prefix) == False):
            continue
        if table[i]["st"] == x:
            if st == False:
                continue
            status = 'ST '
        elif table[i]["ed"] == x:
            if ed == False:
                continue
            status = 'ED '
        else:
            if ps == False:
                continue
            status = str(table[i]["stop_time"]).rjust(2,' ')+"\'"
        visible += 1
        print(str(visible).ljust(4,' '), table[i]["code"].ljust(7,' '),
              table[i]["arrive_time"].ljust(7,' '), end=' ')
        callback[str(visible)] = "."+table[i]["code"]
        if(status == 'ED '):
            print("----        ", table[i]["st"], '-', table[i]["ed"], table[i]["class"], status)
        elif status == 'ST ':
            print(table[i]["start_time"].ljust(7, ' '), "    ", table[i]["st"], '-',
                  table[i]["ed"], table[i]["class"], status)
        else:
            print(table[i]["start_time"].ljust(5,' '), str(table[i]["stop_time"]).rjust(4,' ')+'\' ',
                  table[i]["st"],'-',table[i]["ed"],table[i]["class"])
    print(x, '\t', cnt, "results,", visible, "visible:",end=' ')
    if st:
        print("ST", end=' ')
    if ed:
        print("ED", end=' ')
    if ps:
        print("PS", end=' ')
    if "2" in tail:
        print("UP", end=' ')
    if "1" in tail:
        print("DN", end=' ')
    print(" ")
    line_cut()
    return callback

def search_link(st, ed, sort_order = "st", prefix = "GDCKTZSYP"):
    """起止站搜索，st，ed是两个列表，表示起止站，sort_order表示结果的排序方式，分为st，ed，v。
    prefix表示车次前缀的筛选范围"""
    line_cut()
    callback = {}
    if len(set(st) & set(ed)) > 0:
        print("The set of starting and ending stations include same element")
        return {}
    table = {}
    list_st = {}
    list_ed = {}
    cnt = 0
    visible = 0
    index = {}
    for i in train_list:
        st_flag = False
        ed_flag = False
        for j in train_list[i]:
            if j["station_name"] in st:
                st_flag = True
            if j["station_name"] in ed:
                ed_flag = True
        if not st_flag or not ed_flag:
            continue
        for st_station in st[::-1]:
            for j in train_list[i]:
                if j["station_name"] == st_station:
                    list_st[i] = j
        for ed_station in ed[::-1]:
            for j in train_list[i]:
                if j["station_name"] == ed_station:
                    list_ed[i] = j
    for i in list_st:
        if i in list_ed and int(list_st[i]["station_no"]) < int(list_ed[i]["station_no"]):
            cnt += 1
            t1 = list_ed[i]["running_time"]
            t2 = list_st[i]["running_time"]
            delta_t = int(t1[0:2]) * 60 + int(t1[3:5]) - int(t2[0:2]) * 60 - int(t2[3:5]) - list_st[i]["stop_time"]
            code = list_st[i]["station_train_code"]
            info = train_list[no_list[code]][0]
            table[code] = {
                "code": code,
                "time": str(delta_t // 60) + ":" + str(delta_t % 60 // 10) + str(delta_t % 60 % 10),
                "start_time": list_st[i]["start_time"],
                "arrive_time": list_ed[i]["arrive_time"],
                "st": list_st[i]["station_name"],
                "ed": list_ed[i]["station_name"],
                "start_station": info["start_station_name"],
                "end_station": info["end_station_name"],
                "class": info["train_class_name"]
            }
            if "v" in sort_order:
                index[delta_t * 10000 + cnt] = code
            elif "ed" in sort_order:
                index[list_ed[i]["arrive_time"] + str(cnt)] = code
            else:
                index[list_st[i]["start_time"] + str(cnt)] = code
    for i in st:
        if st[-1] != i:
            print(i + '/', end='')
        else:
            print(i, end=' ')
    print("->", end=' ')
    for j in ed:
        if ed[-1] != j:
            print(j + '/', end='')
        else:
            print(j, end='   ')
    print(cnt, "results")
    for i in sorted(index):
        t = table[index[i]]
        code = t["code"]
        if "P" in prefix and code[0].isdigit or code[0] in prefix:
            visible += 1
            callback[str(visible)] = "." + code
            print(str(visible).ljust(3,' '), t["code"].ljust(6, ' '),
                  t["st"].ljust(5,' ') + "\t" + t["start_time"].ljust(5,' ') + "\t  ",
                  t["ed"].ljust(5,' ') + "\t" + t["arrive_time"].ljust(5,' ') + "\t<", t["time"],">\t",
                  t["start_station"], '-', t["end_station"], t["class"])
    for i in st:
        if st[-1] != i:
            print(i + '/', end='')
        else:
            print(i, end=' ')
    print("->", end=' ')
    for j in ed:
        if ed[-1] != j:
            print(j + '/', end='')
        else:
            print(j, end='   ')
    print(cnt, "results,", visible, "visible")
    line_cut()
    return callback


url_train_no = "https://search.12306.cn/search/v1/train/search"
url_train_info = "https://kyfw.12306.cn/otn/queryTrainInfo/query"


def get_train_no(x, date=auto_date_1):
    """这个函数用于匹配和查找车次信息，
    即train_no编号，可以查一个也可以查多个，
    由于12306一次返回最多200条匹配车次的train_no编号，
    所以当输入的车次号数字部分不少于两位的时候，
    此函数返回的字典中将包含所有匹配车次的train_no编号"""
    params_train_no = {"keyword": x, "date": date}
    resp = requests.get(url=url_train_no, params=params_train_no, headers=headers)
    if resp.status_code == 200:
        js = resp.json()
        resp.close()
        if not js["data"]:
            return "empty"
        return js["data"]
    else:
        return "error"


def get_train_info(x, date=auto_date):
    params_train_info = {"leftTicketDTO.train_no": x, "leftTicketDTO.train_date": date, "rand_code": ""}
    resp = requests.get(url=url_train_info, params=params_train_info, headers=headers)
    if resp.status_code == 200:
        data = resp.json()["data"]["data"]
        resp.close()
        if data is None:
            return "error"
        for station in data:
            if "is_start" in station:
                station["stop_time"] = 0
            else:
                station["stop_time"] = time_interval(station["arrive_time"], station["start_time"])
        lock_train_list.acquire()
        try:
            train_list[x] = data
        finally:
            lock_train_list.release()

try_times = 5
def get_all_target_info(key, mode):
    """这个函数控制get_train_no和get_train_info两个函数
    把目标字段的所有车次号查出train_no并且根据train_no加载时刻表数据"""
    cnt = 0
    if mode == 0:
        time.sleep(1)
    while True:
        cnt += 1
        if cnt == try_times:
            lock_task_callback.acquire()
            try:
                task_callback["failed"] += 1
                task_callback["data"].append(key)
            finally:
                lock_task_callback.release()
            return
        resp = get_train_no(key)
        if resp == "empty":
            task_callback["success"] += 1
            return
        if not resp == "error":
            break
        if mode == 0:
            time.sleep(1)
    if mode == 2:
        for train in resp:
            code = train["station_train_code"]
            if not code in no_list:
                no = train["train_no"]
                no_list[code] = no
        task_callback["success"] += 1
        return
    threads = []
    for train in resp:
        code = train["station_train_code"]
        if not code in no_list:
            no = train["train_no"]
            lock_no_list.acquire()
            try:
                no_list[code] = no
            finally:
                lock_no_list.release()
            if not no in train_list:
                thread = threading.Thread(target=get_train_info, args=(no, auto_date))
                thread.start()
                threads.append(thread)
    for thread in threads:
        thread.join()
    lock_task_callback.acquire()
    try:
        task_callback["success"] += 1
    finally:
        lock_task_callback.release()
    return

def print_threads_data(finished, total, mode=0):
    """把输出导入状态的函数放到一起，这样代码简洁多了"""
    print(str(finished).rjust(3, ' ') + " / " +
          str(total).ljust(6, ' ') + str(task_callback["success"]) + " success, " +
          str(task_callback["failed"]) + " failed", end='')
    if task_callback["failed"] > 0:
        print(":", end=" ")
        if mode == 0:
            lock_task_callback.acquire()
        if len(task_callback["data"]) <= 5:
            for fail in task_callback["data"][::-1]:
                print(fail, end=" ")
            print("")
        else:
            print(task_callback["data"][-1], task_callback["data"][-2], task_callback["data"][-3],
                  task_callback["data"][-4], task_callback["data"][-5], "...")
        if mode == 0:
            lock_task_callback.release()
    else:
        print("")

def get_all_info(keys, mode=0):
    """这个函数负责开启各个车次号查询字段的多线程
    得到的结果载入no_list和train_list
    keys是一个列表，包括需要查询的车次号字段，并且经过了预处理
    mode==2表示不使用多线程，mode==1表示使用一级多线程，mode==0表示使用二级多线程，即默认模式"""
    task_callback["success"] = 0
    task_callback["failed"] = 0
    task_callback["data"] = []
    total = len(keys)
    if mode != 0:
        # 单线程
        for cnt, key in enumerate(keys):
            get_all_target_info(key, mode=mode)
            print_threads_data(finished=cnt+1, total=total, mode=mode)
        return
    else:
        # 分线程
        threads = []
        for key in keys:
            thread = threading.Thread(target=get_all_target_info, args=(key, mode))
            thread.start()
            threads.append(thread)
        while any(thread.is_alive() for thread in threads):
            active_thread_count = sum(thread.is_alive() for thread in threads)
            print_threads_data(finished=total - active_thread_count, total=total, mode=mode)
            time.sleep(1)
        print_threads_data(finished=total, total=total, mode=mode)
        for thread in threads:
            thread.join()
        return



s = ""
callback = {} # 跳转数据
trace = {} # 回溯数据
trace_code = 0
trace_max = 0
city_station = {"\u5317\u4eac": ["\u5317\u4eac", "\u5317\u4eac\u5357", "\u5317\u4eac\u897f", "\u5317\u4eac\u5317", "\u5317\u4eac\u4e30\u53f0", "\u5317\u4eac\u671d\u9633", "\u6e05\u6cb3"], "\u4e0a\u6d77": ["\u4e0a\u6d77", "\u4e0a\u6d77\u8679\u6865", "\u4e0a\u6d77\u5357", "\u4e0a\u6d77\u897f", "\u4e0a\u6d77\u677e\u6c5f"], "\u5929\u6d25": ["\u5929\u6d25", "\u5929\u6d25\u897f", "\u5929\u6d25\u5357", "\u5929\u6d25\u5317", "\u5317\u8fb0"], "\u676d\u5dde": ["\u676d\u5dde", "\u676d\u5dde\u4e1c", "\u676d\u5dde\u897f", "\u676d\u5dde\u5357"], "\u5b81\u6ce2": ["\u5b81\u6ce2", "\u5e84\u6865"], "\u6e29\u5dde": ["\u6e29\u5dde", "\u6e29\u5dde\u5357", "\u6e29\u5dde\u5317"], "\u7ecd\u5174": ["\u7ecd\u5174", "\u7ecd\u5174\u5317"], "\u6e56\u5dde": ["\u6e56\u5dde", "\u6e56\u5dde\u4e1c"], "\u5609\u5174": ["\u5609\u5174", "\u5609\u5174\u5357"], "\u91d1\u534e": ["\u91d1\u534e", "\u91d1\u534e\u5357"], "\u8862\u5dde": ["\u8862\u5dde"], "\u53f0\u5dde": ["\u53f0\u5dde", "\u53f0\u5dde\u897f"], "\u4e3d\u6c34": ["\u4e3d\u6c34"], "\u5357\u4eac": ["\u5357\u4eac", "\u5357\u4eac\u5357"], "\u82cf\u5dde": ["\u82cf\u5dde", "\u82cf\u5dde\u5317", "\u82cf\u5dde\u5357", "\u82cf\u5dde\u56ed\u533a", "\u82cf\u5dde\u65b0\u533a"], "\u65e0\u9521": ["\u65e0\u9521", "\u65e0\u9521\u4e1c", "\u65e0\u9521\u65b0\u533a", "\u60e0\u5c71"], "\u5e38\u5dde": ["\u5e38\u5dde", "\u5e38\u5dde\u5317", "\u6b66\u8fdb", "\u621a\u5885\u5830"], "\u9547\u6c5f": ["\u9547\u6c5f", "\u9547\u6c5f\u5357", "\u5927\u6e2f\u5357"], "\u5f90\u5dde": ["\u5f90\u5dde", "\u5f90\u5dde\u4e1c"], "\u8fde\u4e91\u6e2f": ["\u8fde\u4e91\u6e2f"], "\u5357\u901a": ["\u5357\u901a", "\u5357\u901a\u897f"], "\u76d0\u57ce": ["\u76d0\u57ce"], "\u6dee\u5b89": ["\u6dee\u5b89", "\u6dee\u5b89\u4e1c"], "\u626c\u5dde": ["\u626c\u5dde", "\u626c\u5dde\u4e1c"], "\u6cf0\u5dde": ["\u6cf0\u5dde"], "\u5bbf\u8fc1": ["\u5bbf\u8fc1"], "\u5408\u80a5": ["\u5408\u80a5", "\u5408\u80a5\u5357", "\u5408\u80a5\u5317\u57ce"], "\u829c\u6e56": ["\u829c\u6e56", "\u829c\u6e56\u5357", "\u829c\u6e56\u5317"], "\u9a6c\u978d\u5c71": ["\u9a6c\u978d\u5c71", "\u9a6c\u978d\u5c71\u4e1c"], "\u94dc\u9675": ["\u94dc\u9675", "\u94dc\u9675\u5317"], "\u6c60\u5dde": ["\u6c60\u5dde"], "\u5b89\u5e86": ["\u5b89\u5e86", "\u5b89\u5e86\u897f"], "\u9ec4\u5c71": ["\u9ec4\u5c71", "\u9ec4\u5c71\u5317"], "\u5ba3\u57ce": ["\u5ba3\u57ce"], "\u516d\u5b89": ["\u516d\u5b89"], "\u6dee\u5357": ["\u6dee\u5357", "\u6dee\u5357\u4e1c", "\u6dee\u5357\u5357"], "\u868c\u57e0": ["\u868c\u57e0", "\u868c\u57e0\u5357"], "\u5bbf\u5dde": ["\u5bbf\u5dde", "\u5bbf\u5dde\u4e1c"], "\u6dee\u5317": ["\u6dee\u5317", "\u6dee\u5317\u5317"], "\u6ec1\u5dde": ["\u6ec1\u5dde", "\u6ec1\u5dde\u5317"], "\u4eb3\u5dde": ["\u4eb3\u5dde", "\u4eb3\u5dde\u5357"], "\u961c\u9633": ["\u961c\u9633", "\u961c\u9633\u897f"], "\u6d4e\u5357": ["\u6d4e\u5357", "\u6d4e\u5357\u897f", "\u6d4e\u5357\u4e1c", "\u5927\u660e\u6e56"], "\u9752\u5c9b": ["\u9752\u5c9b", "\u9752\u5c9b\u5317", "\u7ea2\u5c9b", "\u9752\u5c9b\u897f"], "\u6c88\u9633": ["\u6c88\u9633", "\u6c88\u9633\u5317", "\u6c88\u9633\u5357"], "\u957f\u6625": ["\u957f\u6625", "\u957f\u6625\u897f"], "\u54c8\u5c14\u6ee8": ["\u54c8\u5c14\u6ee8", "\u54c8\u5c14\u6ee8\u897f", "\u54c8\u5c14\u6ee8\u4e1c", "\u54c8\u5c14\u6ee8\u5317", "\u9999\u574a"], "\u547c\u548c\u6d69\u7279": ["\u547c\u548c\u6d69\u7279", "\u547c\u548c\u6d69\u7279\u4e1c"], "\u77f3\u5bb6\u5e84": ["\u77f3\u5bb6\u5e84", "\u77f3\u5bb6\u5e84\u4e1c", "\u77f3\u5bb6\u5e84\u5317"], "\u592a\u539f": ["\u592a\u539f", "\u592a\u539f\u5357"], "\u897f\u5b89": ["\u897f\u5b89", "\u897f\u5b89\u5317", "\u897f\u5b89\u4e1c", "\u5f15\u9547"], "\u5170\u5dde": ["\u5170\u5dde", "\u5170\u5dde\u897f"], "\u897f\u5b81": ["\u897f\u5b81"], "\u4e4c\u9c81\u6728\u9f50": ["\u4e4c\u9c81\u6728\u9f50", "\u4e4c\u9c81\u6728\u9f50\u5357"], "\u62c9\u8428": ["\u62c9\u8428"], "\u90d1\u5dde": ["\u90d1\u5dde", "\u90d1\u5dde\u4e1c", "\u5357\u9633\u5be8"], "\u6b66\u6c49": ["\u6b66\u6c49", "\u6c49\u53e3", "\u6b66\u660c", "\u6b66\u6c49\u4e1c"], "\u957f\u6c99": ["\u957f\u6c99", "\u957f\u6c99\u5357", "\u957f\u6c99\u897f"], "\u5e7f\u5dde": ["\u5e7f\u5dde", "\u5e7f\u5dde\u5357", "\u5e7f\u5dde\u4e1c", "\u5e7f\u5dde\u767d\u4e91", "\u65b0\u5858", "\u65b0\u5858\u5357", "\u756a\u79ba"], "\u6df1\u5733": ["\u6df1\u5733", "\u6df1\u5733\u5317", "\u6df1\u5733\u4e1c", "\u798f\u7530", "\u6df1\u5733\u673a\u573a", "\u6df1\u5733\u576a\u5c71"], "\u798f\u5dde": ["\u798f\u5dde", "\u798f\u5dde\u5357"], "\u53a6\u95e8": ["\u53a6\u95e8", "\u53a6\u95e8\u5317"], "\u5357\u660c": ["\u5357\u660c", "\u5357\u660c\u897f", "\u5357\u660c\u4e1c"], "\u5357\u5b81": ["\u5357\u5b81", "\u5357\u5b81\u4e1c"], "\u6606\u660e": ["\u6606\u660e", "\u6606\u660e\u5357"], "\u6210\u90fd": ["\u6210\u90fd", "\u6210\u90fd\u4e1c", "\u6210\u90fd\u897f", "\u6210\u90fd\u5357", "\u7280\u6d66"], "\u91cd\u5e86": ["\u91cd\u5e86", "\u91cd\u5e86\u5317", "\u91cd\u5e86\u897f", "\u91cd\u5e86\u4e1c", "\u6c99\u576a\u575d"], "\u8d35\u9633": ["\u8d35\u9633", "\u8d35\u9633\u5317", "\u8d35\u9633\u4e1c"], "\u5927\u8fde": ["\u5927\u8fde", "\u5927\u8fde\u5317"], "\u94f6\u5ddd": ["\u94f6\u5ddd", "\u94f6\u5ddd\u4e1c"], "\u6d77\u53e3": ["\u6d77\u53e3", "\u6d77\u53e3\u4e1c"], "\u4e0a\u865e": ["\u4e0a\u865e", "\u7ecd\u5174\u4e1c", "\u4e0a\u865e\u5357"], "\u5d4a\u5dde": ["\u5d4a\u5dde\u65b0\u660c", "\u5d4a\u5dde\u5317"], "\u65b0\u660c": ["\u5d4a\u5dde\u65b0\u660c", "\u65b0\u660c\u5317"], "\u5bcc\u9633": ["\u5bcc\u9633", "\u5bcc\u9633\u897f"], "\u6850\u5e90": ["\u6850\u5e90", "\u6850\u5e90\u4e1c"], "\u5fb7\u6e05": ["\u5fb7\u6e05", "\u5fb7\u6e05\u897f"], "\u957f\u5174": ["\u957f\u5174", "\u957f\u5174\u5357"], "\u6d77\u5b81": ["\u6d77\u5b81", "\u6d77\u5b81\u897f"], "\u5609\u5584": ["\u5609\u5584", "\u5609\u5584\u5357"], "\u4f59\u59da": ["\u4f59\u59da", "\u4f59\u59da\u5317"], "\u5929\u53f0": ["\u5929\u53f0\u5c71"], "\u4e34\u6d77": ["\u4e34\u6d77", "\u4e34\u6d77\u5357"], "\u4ed9\u5c45": ["\u4ed9\u5c45", "\u4ed9\u5c45\u5357"], "\u4e50\u6e05": ["\u4e50\u6e05", "\u4e50\u6e05\u4e1c"], "\u6c38\u5eb7": ["\u6c38\u5eb7\u5357"], "\u6b66\u4e49": ["\u6b66\u4e49", "\u6b66\u4e49\u5317"], "\u4e5d\u6c5f": ["\u4e5d\u6c5f", "\u5e90\u5c71"], "\u629a\u5dde": ["\u629a\u5dde", "\u629a\u5dde\u4e1c"], "\u5b9c\u6625": ["\u5b9c\u6625"], "\u5409\u5b89": ["\u5409\u5b89", "\u5409\u5b89\u897f"], "\u8d63\u5dde": ["\u8d63\u5dde", "\u8d63\u5dde\u897f"], "\u65b0\u4f59": ["\u65b0\u4f59", "\u65b0\u4f59\u5317"], "\u840d\u4e61": ["\u840d\u4e61", "\u840d\u4e61\u5317"], "\u9e70\u6f6d": ["\u9e70\u6f6d", "\u9e70\u6f6d\u5317"], "\u666f\u5fb7\u9547": ["\u666f\u5fb7\u9547", "\u666f\u5fb7\u9547\u5317"], "\u4f5b\u5c71": ["\u4f5b\u5c71\u897f"], "\u4e1c\u839e": ["\u4e1c\u839e", "\u864e\u95e8", "\u4e1c\u839e\u897f", "\u4e1c\u839e\u4e1c", "\u4e1c\u839e\u5357"], "\u9999\u6e2f": ["\u9999\u6e2f\u897f\u4e5d\u9f99"], "\u6fb3\u95e8": ["\u73e0\u6d77", "\u6a2a\u7434"], "\u73e0\u6d77": ["\u73e0\u6d77"], "\u60e0\u5dde": ["\u60e0\u5dde", "\u60e0\u5dde\u5317", "\u60e0\u5dde\u5357", "\u4ef2\u607a", "\u5c0f\u91d1\u53e3"], "\u6c55\u5c3e": ["\u6c55\u5c3e"], "\u6c55\u5934": ["\u6c55\u5934", "\u6c55\u5934\u5357"], "\u6f6e\u5dde": ["\u6f6e\u5dde", "\u6f6e\u6c55"], "\u63ed\u9633": ["\u63ed\u9633", "\u63ed\u9633\u5357", "\u63ed\u9633\u673a\u573a"], "\u6885\u5dde": ["\u6885\u5dde", "\u6885\u5dde\u897f"], "\u6cb3\u6e90": ["\u6cb3\u6e90", "\u6cb3\u6e90\u4e1c"], "\u6e05\u8fdc": ["\u6e05\u8fdc", "\u6e05\u57ce", "\u98de\u971e", "\u6d32\u5fc3", "\u6e90\u6f6d"], "\u6c5f\u95e8": ["\u6c5f\u95e8", "\u6c5f\u95e8\u4e1c", "\u65b0\u4f1a"], "\u4e2d\u5c71": ["\u4e2d\u5c71", "\u4e2d\u5c71\u5317"], "\u8087\u5e86": ["\u8087\u5e86", "\u8087\u5e86\u4e1c", "\u9f0e\u6e56", "\u9f0e\u6e56\u4e1c"], "\u9633\u6c5f": ["\u9633\u6c5f"], "\u8302\u540d": ["\u8302\u540d", "\u8302\u540d\u897f"], "\u6e5b\u6c5f": ["\u6e5b\u6c5f", "\u6e5b\u6c5f\u897f", "\u6e5b\u6c5f\u5317"], "\u4e91\u6d6e": ["\u4e91\u6d6e\u4e1c"], "\u5609\u5b9a": ["\u5357\u7fd4\u5317", "\u5b89\u4ead\u5317", "\u5b89\u4ead\u897f"], "\u6606\u5c71": ["\u6606\u5c71", "\u6606\u5c71\u5357", "\u9633\u6f84\u6e56"], "\u592a\u4ed3": ["\u592a\u4ed3", "\u592a\u4ed3\u5357"], "\u6d4b\u8bd5\u57ce\u5e021": ["\u5317\u4eac\u5357", "\u4e0a\u6d77\u8679\u6865", "\u5e7f\u5dde\u5357", "\u6df1\u5733\u5317", "\u5357\u4eac\u5357", "\u676d\u5dde\u4e1c", "\u6b66\u6c49", "\u90d1\u5dde\u4e1c", "\u957f\u6c99\u5357", "\u5929\u6d25\u897f", "\u6210\u90fd\u4e1c", "\u91cd\u5e86\u897f", "\u897f\u5b89\u5317", "\u6606\u660e\u5357", "\u6c88\u9633\u5317", "\u957f\u6625\u897f", "\u54c8\u5c14\u6ee8\u897f", "\u5357\u660c\u897f", "\u8d35\u9633\u5317", "\u5357\u5b81\u4e1c", "\u5170\u5dde\u897f", "\u4e4c\u9c81\u6728\u9f50", "\u77f3\u5bb6\u5e84", "\u592a\u539f\u5357", "\u6d4e\u5357\u4e1c", "\u9752\u5c9b\u5317", "\u5927\u8fde\u5317", "\u547c\u548c\u6d69\u7279\u4e1c", "\u94f6\u5ddd", "\u5408\u80a5\u5357", "\u6d77\u53e3\u4e1c"], "\u6d4b\u8bd5\u57ce\u5e022": ["\u5317\u4eac", "\u5929\u6d25", "\u77f3\u5bb6\u5e84\u5317", "\u592a\u539f", "\u90d1\u5dde", "\u6d4e\u5357", "\u547c\u548c\u6d69\u7279", "\u6c88\u9633", "\u957f\u6625", "\u54c8\u5c14\u6ee8", "\u5357\u4eac", "\u4e0a\u6d77", "\u5408\u80a5", "\u676d\u5dde\u5357", "\u798f\u5dde", "\u5357\u660c", "\u5e7f\u5dde", "\u6df1\u5733", "\u5357\u5b81", "\u6210\u90fd\u5357", "\u6606\u660e", "\u8d35\u9633", "\u91cd\u5e86\u5317", "\u6b66\u660c", "\u957f\u6c99", "\u897f\u5b89", "\u5170\u5dde", "\u897f\u5b81", "\u62c9\u8428", "\u4e4c\u9c81\u6728\u9f50\u5357"], "\u90f4\u5dde": ["\u90f4\u5dde", "\u90f4\u5dde\u897f"], "\u8861\u9633": ["\u8861\u9633", "\u8861\u9633\u4e1c"], "\u682a\u6d32": ["\u682a\u6d32", "\u682a\u6d32\u897f", "\u682a\u6d32\u5357"], "\u6e58\u6f6d": ["\u6e58\u6f6d", "\u6e58\u6f6d\u5317"], "\u5a04\u5e95": ["\u5a04\u5e95", "\u5a04\u5e95\u5357"], "\u6000\u5316": ["\u6000\u5316", "\u6000\u5316\u5357"], "\u5cb3\u9633": ["\u5cb3\u9633", "\u5cb3\u9633\u4e1c"], "\u76ca\u9633": ["\u76ca\u9633", "\u76ca\u9633\u5357"], "\u5e38\u5fb7": ["\u5e38\u5fb7"], "\u5f20\u5bb6\u754c": ["\u5f20\u5bb6\u754c", "\u5f20\u5bb6\u754c\u897f"], "\u6e58\u897f": ["\u5409\u9996", "\u5409\u9996\u4e1c"], "\u5409\u9996": ["\u5409\u9996", "\u5409\u9996\u4e1c"], "\u6cf0\u5b89": ["\u6cf0\u5b89", "\u6cf0\u5c71"], "\u67a3\u5e84": ["\u67a3\u5e84", "\u67a3\u5e84\u897f"], "\u4e34\u6c82": ["\u4e34\u6c82", "\u4e34\u6c82\u5317", "\u4e34\u6c82\u4e1c"], "\u65e5\u7167": ["\u65e5\u7167", "\u65e5\u7167\u897f"], "\u5a01\u6d77": ["\u5a01\u6d77", "\u5a01\u6d77\u5317"], "\u70df\u53f0": ["\u70df\u53f0", "\u70df\u53f0\u5357", "\u829d\u7f58"], "\u6f4d\u574a": ["\u6f4d\u574a\u5317"], "\u6dc4\u535a": ["\u6dc4\u535a", "\u6dc4\u535a\u5317"], "\u5fb7\u5dde": ["\u5fb7\u5dde", "\u5fb7\u5dde\u4e1c"], "\u804a\u57ce": ["\u804a\u57ce", "\u804a\u57ce\u897f"], "\u6d4e\u5b81": ["\u6d4e\u5b81", "\u6d4e\u5b81\u5317"], "\u4fdd\u5b9a": ["\u4fdd\u5b9a", "\u4fdd\u5b9a\u4e1c"], "\u90a2\u53f0": ["\u90a2\u53f0", "\u90a2\u53f0\u4e1c"], "\u90af\u90f8": ["\u90af\u90f8", "\u90af\u90f8\u4e1c"], "\u8861\u6c34": ["\u8861\u6c34", "\u8861\u6c34\u5317"], "\u6ca7\u5dde": ["\u6ca7\u5dde", "\u6ca7\u5dde\u897f"], "\u5eca\u574a": ["\u5eca\u574a", "\u5eca\u574a\u5317", "\u5e7f\u9633"], "\u5510\u5c71": ["\u5510\u5c71", "\u5510\u5c71\u5317", "\u5510\u5c71\u897f"], "\u79e6\u7687\u5c9b": ["\u79e6\u7687\u5c9b"], "\u627f\u5fb7": ["\u627f\u5fb7", "\u627f\u5fb7\u5357"], "\u5f20\u5bb6\u53e3": ["\u5f20\u5bb6\u53e3"], "\u65b0\u4e61": ["\u65b0\u4e61", "\u65b0\u4e61\u4e1c"], "\u6d1b\u9633": ["\u6d1b\u9633", "\u6d1b\u9633\u4e1c", "\u6d1b\u9633\u9f99\u95e8", "\u5173\u6797"], "\u4e09\u95e8\u5ce1": ["\u4e09\u95e8\u5ce1", "\u4e09\u95e8\u5ce1\u5357"], "\u5357\u9633": ["\u5357\u9633", "\u5357\u9633\u4e1c"], "\u5e73\u9876\u5c71": ["\u5e73\u9876\u5c71", "\u5e73\u9876\u5c71\u897f"], "\u4fe1\u9633": ["\u4fe1\u9633", "\u4fe1\u9633\u4e1c"], "\u8bb8\u660c": ["\u8bb8\u660c", "\u8bb8\u660c\u4e1c", "\u8bb8\u660c\u5317"], "\u6f2f\u6cb3": ["\u6f2f\u6cb3", "\u6f2f\u6cb3\u4e1c"], "\u9a7b\u9a6c\u5e97": ["\u9a7b\u9a6c\u5e97", "\u9a7b\u9a6c\u5e97\u897f"], "\u5468\u53e3": ["\u5468\u53e3", "\u5468\u53e3\u4e1c"], "\u5f00\u5c01": ["\u5f00\u5c01", "\u5f00\u5c01\u5317", "\u5b8b\u57ce\u8def"], "\u5546\u4e18": ["\u5546\u4e18", "\u5546\u4e18\u5357", "\u5546\u4e18\u4e1c"], "\u9e64\u58c1": ["\u9e64\u58c1", "\u9e64\u58c1\u4e1c"], "\u5b89\u9633": ["\u5b89\u9633", "\u5b89\u9633\u4e1c"], "\u6fee\u9633": ["\u6fee\u9633", "\u6fee\u9633\u4e1c"], "\u660c\u5e73": ["\u660c\u5e73", "\u660c\u5e73\u5317"], "\u6000\u67d4": ["\u6000\u67d4", "\u6000\u67d4\u5357", "\u6000\u67d4\u5317", "\u96c1\u6816\u6e56"], "\u5bc6\u4e91": ["\u5bc6\u4e91\u5317", "\u5bc6\u4e91"], "\u5927\u5174": ["\u5317\u4eac\u5927\u5174", "\u5927\u5174\u673a\u573a"], "\u9ec4\u5188": ["\u9ec4\u5188", "\u9ec4\u5188\u897f", "\u9ec4\u5188\u4e1c"], "\u9102\u5dde": ["\u9102\u5dde", "\u9102\u5dde\u4e1c"], "\u9ec4\u77f3": ["\u9ec4\u77f3\u5317", "\u9ec4\u77f3\u4e1c"], "\u54b8\u5b81": ["\u54b8\u5b81", "\u54b8\u5b81\u5317", "\u54b8\u5b81\u5357", "\u54b8\u5b81\u4e1c"], "\u5b5d\u611f": ["\u5b5d\u611f", "\u5b5d\u611f\u4e1c", "\u69d0\u836b"], "\u968f\u5dde": ["\u968f\u5dde", "\u968f\u5dde\u5357"], "\u8944\u9633": ["\u8944\u9633", "\u8944\u9633\u4e1c"], "\u8346\u95e8": ["\u8346\u95e8", "\u8346\u95e8\u897f"], "\u5b9c\u660c": ["\u5b9c\u660c", "\u5b9c\u660c\u4e1c"], "\u4e07\u5dde": ["\u4e07\u5dde", "\u4e07\u5dde\u5317"], "\u9ed4\u6c5f": ["\u9ed4\u6c5f"], "\u5341\u5830": ["\u5341\u5830", "\u5341\u5830\u4e1c"], "\u7709\u5c71": ["\u7709\u5c71", "\u7709\u5c71\u4e1c"], "\u4e50\u5c71": ["\u4e50\u5c71"], "\u8d44\u9633": ["\u8d44\u9633", "\u8d44\u9633\u5317", "\u8d44\u9633\u897f"], "\u5185\u6c5f": ["\u5185\u6c5f", "\u5185\u6c5f\u5317", "\u5185\u6c5f\u4e1c"], "\u81ea\u8d21": ["\u81ea\u8d21", "\u81ea\u8d21\u5317"], "\u6cf8\u5dde": ["\u6cf8\u5dde", "\u6cf8\u5dde\u4e1c"], "\u5b9c\u5bbe": ["\u5b9c\u5bbe", "\u5b9c\u5bbe\u897f", "\u5b9c\u5bbe\u4e1c"], "\u897f\u660c": ["\u897f\u660c", "\u897f\u660c\u897f"], "\u51c9\u5c71": ["\u897f\u660c", "\u897f\u660c\u897f"], "\u5fb7\u9633": ["\u5fb7\u9633"], "\u7ef5\u9633": ["\u7ef5\u9633"], "\u5357\u5145": ["\u5357\u5145", "\u5357\u5145\u5317"], "\u5df4\u4e2d": ["\u5df4\u4e2d", "\u5df4\u4e2d\u4e1c", "\u5df4\u4e2d\u897f"], "\u5b89\u987a": ["\u5b89\u987a", "\u5b89\u987a\u897f"], "\u516d\u76d8\u6c34": ["\u516d\u76d8\u6c34", "\u516d\u76d8\u6c34\u4e1c"], "\u90fd\u5300": ["\u90fd\u5300", "\u90fd\u5300\u4e1c"], "\u9ed4\u5357": ["\u90fd\u5300", "\u90fd\u5300\u4e1c"], "\u51ef\u91cc": ["\u51ef\u91cc", "\u51ef\u91cc\u5357"], "\u9ed4\u4e1c\u5357": ["\u51ef\u91cc", "\u51ef\u91cc\u5357"], "\u9ed4\u897f\u5357": ["\u5174\u4e49"], "\u94a6\u5dde": ["\u94a6\u5dde", "\u94a6\u5dde\u4e1c"], "\u9632\u57ce\u6e2f": ["\u9632\u57ce\u6e2f\u5317"], "\u5317\u6d77": ["\u5317\u6d77"], "\u5d07\u5de6": ["\u5d07\u5de6", "\u5d07\u5de6\u5357"], "\u6797": [], "\u7389\u6797": ["\u7389\u6797", "\u7389\u6797\u5317"], "\u68a7\u5dde": ["\u68a7\u5dde", "\u68a7\u5dde\u5357"], "\u6765\u5bbe": ["\u6765\u5bbe", "\u6765\u5bbe\u5317"], "\u67f3\u5dde": ["\u67f3\u5dde"], "\u6842\u6797": ["\u6842\u6797", "\u6842\u6797\u5317", "\u6842\u6797\u897f"], "\u6cb3\u6c60": ["\u5b9c\u5dde"], "\u66f2\u9756": ["\u66f2\u9756", "\u66f2\u9756\u5317"], "\u7ea2\u6cb3": ["\u8499\u81ea", "\u7ea2\u6cb3"], "\u8499\u81ea": ["\u8499\u81ea", "\u7ea2\u6cb3"], "\u666f\u6d2a": ["\u897f\u53cc\u7248\u7eb3"], "\u5927\u7406": ["\u5927\u7406", "\u5927\u7406\u5317"], "\u6500\u679d\u82b1": ["\u6500\u679d\u82b1", "\u6500\u679d\u82b1\u5357"], "\u5546\u6d1b": ["\u5546\u6d1b", "\u5546\u6d1b\u5317"], "\u6e2d\u5357": ["\u6e2d\u5357", "\u6e2d\u5357\u5317", "\u6e2d\u5357\u897f"], "\u94dc\u5ddd": ["\u94dc\u5ddd", "\u94dc\u5ddd\u4e1c", "\u8000\u5dde"], "\u5ef6\u5b89": ["\u5ef6\u5b89"], "\u8fd0\u57ce": ["\u8fd0\u57ce", "\u8fd0\u57ce\u5317"], "\u4e34\u6c7e": ["\u4e34\u6c7e", "\u4e34\u6c7e\u897f"], "\u664b\u57ce": ["\u664b\u57ce", "\u664b\u57ce\u4e1c"], "\u957f\u6cbb": ["\u957f\u6cbb", "\u957f\u6cbb\u4e1c"], "\u5ffb\u5dde": ["\u5ffb\u5dde", "\u5ffb\u5dde\u897f"], "\u6714\u5dde": ["\u6714\u5dde", "\u6714\u5dde\u4e1c", "\u6714\u5dde\u897f"], "\u5927\u540c": ["\u5927\u540c", "\u5927\u540c\u5357"], "\u9633\u6cc9": ["\u9633\u6cc9", "\u9633\u6cc9\u4e1c", "\u9633\u6cc9\u5317"], "\u5b9d\u9e21": ["\u5b9d\u9e21", "\u5b9d\u9e21\u5357"], "\u4e2d\u536b": ["\u4e2d\u536b", "\u4e2d\u536b\u5357"], "\u77f3\u5634\u5c71": ["\u77f3\u5634\u5c71", "\u77f3\u5634\u5c71\u5357"], "\u4e4c\u6d77": ["\u4e4c\u6d77", "\u4e4c\u6d77\u4e1c"], "\u5305\u5934": ["\u5305\u5934", "\u5305\u5934\u4e1c"], "\u4e4c\u5170\u5bdf\u5e03": ["\u4e4c\u5170\u5bdf\u5e03", "\u96c6\u5b81\u5357"], "\u8d64\u5cf0": ["\u8d64\u5cf0", "\u8d64\u5cf0\u5357"], "\u9521\u6797\u90ed\u52d2": ["\u9521\u6797\u6d69\u7279"], "\u5174\u5b89": ["\u4e4c\u5170\u6d69\u7279"], "\u547c\u4f26\u8d1d\u5c14": ["\u6d77\u62c9\u5c14"], "\u8425\u53e3": ["\u8425\u53e3", "\u8425\u53e3\u4e1c"], "\u76d8\u9526": ["\u76d8\u9526", "\u76d8\u9526\u5317"], "\u9526\u5dde": ["\u9526\u5dde", "\u9526\u5dde\u5357", "\u9526\u5dde\u5317"], "\u846b\u82a6\u5c9b": ["\u846b\u82a6\u5c9b", "\u846b\u82a6\u5c9b\u5317"], "\u671d\u9633": ["\u671d\u9633\u5357", "\u8fbd\u5b81\u671d\u9633"], "\u5929\u6c34": ["\u5929\u6c34", "\u5929\u6c34\u5357"], "\u5b9a\u897f": ["\u5b9a\u897f", "\u5b9a\u897f\u5317"], "\u5e73\u51c9": ["\u5e73\u51c9", "\u5e73\u51c9\u5357"], "\u767d\u94f6": ["\u767d\u94f6", "\u767d\u94f6\u5357"], "\u6b66\u5a01": ["\u6b66\u5a01", "\u6b66\u5a01\u4e1c"], "\u5f20\u6396": ["\u5f20\u6396", "\u5f20\u6396\u897f"], "\u9152\u6cc9": ["\u9152\u6cc9", "\u9152\u6cc9\u5357"], "\u5609\u5cea\u5173": ["\u5609\u5cea\u5173", "\u5609\u5cea\u5173\u5357"], "\u6d77\u897f": ["\u5fb7\u4ee4\u54c8"], "\u6d77\u4e1c": ["\u6d77\u4e1c", "\u4e50\u90fd"], "\u5410\u9c81\u756a": ["\u5410\u9c81\u756a", "\u5410\u9c81\u756a\u5317"], "\u5df4\u97f3\u90ed\u695e": ["\u5e93\u5c14\u52d2"], "\u514b\u5b5c\u52d2\u82cf": ["\u963f\u56fe\u4ec0"], "\u4f0a\u7281": ["\u4f0a\u5b81"], "\u94c1\u5cad": ["\u94c1\u5cad", "\u94c1\u5cad\u897f"], "\u672c\u6eaa": ["\u672c\u6eaa", "\u672c\u6eaa\u65b0\u57ce"], "\u978d\u5c71": ["\u978d\u5c71", "\u978d\u5c71\u897f"], "\u767d\u5c71": ["\u767d\u5c71\u5e02"], "\u629a\u987a": ["\u629a\u987a", "\u629a\u987a\u5317"], "\u901a\u5316": ["\u901a\u5316", "\u901a\u5316\u897f"], "\u5ef6\u8fb9": ["\u5ef6\u5409", "\u5ef6\u5409\u897f"], "\u5ef6\u5409": ["\u5ef6\u5409", "\u5ef6\u5409\u897f"], "\u9e21\u897f": ["\u9e21\u897f", "\u9e21\u897f\u897f"], "\u4e03\u53f0\u6cb3": ["\u4e03\u53f0\u6cb3", "\u4e03\u53f0\u6cb3\u897f"], "\u53cc\u9e2d\u5c71": ["\u53cc\u9e2d\u5c71\u897f"], "\u4f73\u6728\u65af": ["\u4f73\u6728\u65af", "\u4f73\u6728\u65af\u897f"], "\u5927\u5e86": ["\u5927\u5e86", "\u5927\u5e86\u4e1c", "\u5927\u5e86\u897f"], "\u9f50\u9f50\u54c8\u5c14": ["\u9f50\u9f50\u54c8\u5c14", "\u9f50\u9f50\u54c8\u5c14\u5357"], "\u5174\u5b89\u76df": ["\u4e4c\u5170\u6d69\u7279"], "\u9521\u6797\u90ed\u52d2\u76df": ["\u9521\u6797\u6d69\u7279"], "\u695a\u96c4": ["\u695a\u96c4", "\u695a\u96c4\u5357"], "save": []} # 同城车站数据

print("Welcome to the Rail Rhythm railway timetable query tool")
if os.path.exists('global_data/city_station.json'):
    with open('global_data/city_station.json', 'r') as f1:
        city_station = json.load(f1)
print("Current date setting:", auto_date)
while s != "exit":
    s = input("Input instruction: ")
    s = s.lower()
    if s == "":
        continue
    if s in callback:
        s = callback[s]
    if s[0:6].lower() == "import": # 联网导入
        head = []
        if s[-2:] == " 1" or s[-2:] == " 2":
            mode = int(s[-1])
            s = s[:-2]
        else:
            mode = 0
        type = s[7:].upper()
        if 'A' in type:
            type = "GDCZTKSYP"
        for prefix in ['G', 'D', 'C', 'Z', 'T', 'K', 'S', 'Y', 'P']:
            if prefix in type:
                if prefix in ['Z', 'T', 'Y']:
                    for num in range(1, 10):
                        head.append(prefix + str(num))
                elif prefix == 'P':
                    for num in range(1, 10):
                        head.append(str(num))
                else:
                    for num in range(1, 100):
                        head.append(prefix + str(num))
        get_all_info(head, mode=mode)
        count_code()
        continue

    # 时间设置，时间设置之后自动读取
    if s.lower() == "time" or s.lower() == "date":
        print("Current date setting:", auto_date)
        auto_date = input("Input time setting (xxxx-xx-xx) : ")
        if bool(re.match(r'^\d{4}-\d{2}-\d{2}$', auto_date)):
            auto_date_1 = auto_date.replace("-", "")
            s = "load"
        else:
            print("Date format not correct")
            continue
    if bool(re.match(r'^\d{4}-\d{2}-\d{2}$', s)):
        print("Date has been changed from", auto_date, "to", s)
        auto_date = s
        auto_date_1 = auto_date.replace("-", "")
        s = "load"

    # 保存数据
    if s.lower() == "save":
        for i in train_list:
            train_list[i][0]["start_station_name"] = train_list[i][0]["start_station_name"].replace(" ", "")
            train_list[i][0]["end_station_name"] = train_list[i][0]["end_station_name"].replace(" ", "")
            for j in train_list[i]:
                j["station_name"] = j["station_name"].replace(" ", "")
        with open('train_data/train_list' + auto_date_1 + '.json', 'w') as f1:
            json.dump(train_list, f1)
        with open('train_data/no_list' + auto_date_1 + '.json', 'w') as f2:
            json.dump(no_list, f2)
        print("Save over")
        line_cut()
        continue

    # 载入数据
    if s.lower() == "load":
        if (os.path.exists('train_data/train_list' + auto_date_1 + '.json') and
                os.path.exists('train_data/no_list' + auto_date_1 + '.json')):
            with open('train_data/train_list' + auto_date_1 + '.json', 'r') as f1:
                train_list = json.load(f1)
            with open('train_data/no_list' + auto_date_1 + '.json', 'r') as f2:
                no_list = json.load(f2)
            print("Load over")
            count_code()
        else:
            print("File is not exist, load fail")
        continue

    # 同城车站清单编辑
    if s.lower() == "city_station":
        while True:
            new = input("City name: ")
            if new in city_station:
                print(new, " ", city_station[new])
                tmp = city_station[new]
            else:
                print(new, "new in city_station list")
                tmp = "tmp"
            city_station[new] = []
            if new == "save" or new == "exit":
                break
            station_name = ""
            city_station[new] = []
            n = input("Station name: ")
            if n == "delete" or n == "删除":
                city_station.pop(new)
                continue
            while n != "0" and n.lower() != "end" and n.lower() != "undo":
                city_station[new].append(n)
                n = input("Station name: ")
            if n.lower() == "undo":
                city_station[new] = tmp
                if tmp == "tmp":
                    city_station.pop(new)
        with open('global_data/city_station.json', 'w') as f1:
            json.dump(city_station, f1)
        print("City stations data save over")
        continue

    # 编辑user-agent
    if s.lower() == "agent":
        print("Current simulated user-agent:", headers["User-Agent"])
        headers["User-Agent"] = input("Input user-agent setting: ")
        continue

    # 车次计数
    if s.lower() == "sum":
        count_code()
        continue

    # 回溯
    if trace_code > 1 and (s == "<<" or s == "《《"):
        trace_code -= 1
        s = trace[trace_code-1]
    elif trace_code < trace_max and (s == ">>" or s =="》》"):
        trace_code += 1
        s = trace[trace_code-1]
    elif s == "<<" or s == "《《":
        print("Cannot move backward")
        continue
    elif s == ">>" or s =="》》":
        print("Cannot move forward")
        continue
    else:
        trace[trace_code] = s
        trace_code += 1
        trace_max = trace_code

    # 处理字头筛选
    r = "GDCKTZSYP"
    if "*" in s:
        s, pre = s.split("*")
        r = pre.upper()

    # 车次查
    if s[0:4].lower() == "code" or s[0] == '.' or s[0] == '。':
        if s[0:4].lower() == "code":
            target = s[5:].upper()
        else:
            target = s[1:].upper()
        if not target in no_list:
            print("Code not found")
        elif not no_list[target] in train_list:
            print("Not operate on the appointed date")
        else:
            callback = print_train(train_list[no_list[target]])
            continue

    # 按站点查
    if s[0:7].lower() == "station" or s[-1:] == "站" or s.find("+") > 1 and s[s.find("+")-1] == "站":
        if s[0:7].lower() == "station":
            target = s[8:]
        elif "+" in s:
            target = s[:s.find("+")-1]
        else:
            target = s[:-1]
        if "+" in s:
            s, sort_order =s.split("+")
            callback = search_station(target, sort_order = sort_order, prefix = r)
        else:
            callback = search_station(target, prefix = r)
        continue

    # 同城车站处理
    if "--" in s:
        if s.count('-') > 2:
            trace_code -= 1
            print("Instruction grammar error")
            continue
        st, ed = s.split("--")
        add = ""
        if "+" in ed:
            ed, add = ed.split("+")
        s = ""
        if st in city_station:
            for sta in city_station[st]:
                s = s + "/" + sta
            s = s[1:]
        else:
            s = st
        s = s + "-"
        if ed in city_station:
            for sta in city_station[ed]:
                s = s + sta + "/"
            s = s[0:-1]
        else:
            s = s + ed
        if add != "":
            s = s + "+" + add

    # 站站查
    if "-" in s:
        if s.count('-') > 1:
            trace_code -= 1
            print("Instruction grammar error")
            continue
        st, ed = s.split("-")
        if "+" in ed:
            if ed.count('+') > 1:
                trace_code -= 1
                print("Instruction grammar error")
                continue
            ed, sort_order = ed.split("+")
            sts = st.split("/")
            eds = ed.split("/")
            callback = search_link(sts, eds, sort_order = sort_order.lower(), prefix = r)
        else:
            sts = st.split("/")
            eds = ed.split("/")
            callback = search_link(sts, eds, prefix = r)
        callback["//"] = st + "-" + ed
        callback["/st"] = st + "-" + ed + "+st" + "*" + r
        callback["/ed"] = st + "-" + ed + "+ed" + "*" + r
        callback["/v"] = st + "-" + ed + "+v" + "*" + r
        continue
    trace_code -= 1
    if trace_max == trace_code + 1:
        trace_max - 1
    print("No suitable instruction")