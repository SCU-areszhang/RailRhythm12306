import tkinter as tk
import ctypes
from tkinter import ttk
# Rail Rhythm 中国铁路时刻表查询工具
# wj_0575 2025.1
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

def print_train(x, ask = False):
    """这个函数用于输出一个车次的信息
    参数x为一个字典"""
    pack = {"names": ["序号", "站名", "到点", "开点", "停时", "事件", "运行"],
            "widths": [5, 11, 8, 8, 8, 20, 10],
            "data": [],
            "head": x[0]["station_train_code"]}
    callback = {}
    for i in x:
        if not i["station_train_code"] in pack["head"]:
            pack["head"] += " / " + i["station_train_code"]
    pack["head"] += (" " + x[0]["start_station_name"] + " - "
                     + x[0]["end_station_name"])
    code = x[0]["station_train_code"]
    d = "0"
    for index, i in enumerate(x):
        index += 1
        insert = [index, i["station_name"], i["arrive_time"], i["start_time"],
                  " "+str(i["stop_time"])+'\'', "", i["running_time"]]
        if i == x[-1]:
            insert[3] = ""
            insert[4] = ""
        if index == 1:
            insert[2] = ""
            insert[4] = ""
        if i["arrive_day_diff"] != d:
            d = i["arrive_day_diff"]
            insert[5] = "第" + str(int(d)+1) + "天"
        if i["station_train_code"] != code:
            if insert[5] != "":
                insert[5] += " 切换为" + i["station_train_code"]
            else:
                insert[5] = "切换为" + i["station_train_code"]
            code = i["station_train_code"]
        pack["data"].append(insert)
    if ask:
        pack["callback"] = callback
        return pack
    return callback

def print_station(x, t1='00:00', t2='24:00', sort_order = "", prefix = ""):
    """这个函数用来查找车站的时刻表
    在sort_order中，如果包含up/dn，说明需要显示上/下行车次
    如果包含st/ed/ps，说明需要显示始发/终到/过路车次"""
    tail = []
    if 'P' in prefix:
        prefix += "0123456789"
    pack = {"names": ["序号", "车次", "到点", "开点", "停时", "始发终到", "类型"],
            "widths": [5, 11, 8, 8, 8, 20, 10],
            "data":[],
            "head":""}
    if "up" in sort_order:
        tail.extend(list("24680"))
    if "dn" in sort_order:
        tail.extend(list("13579"))
    st = "st" in sort_order
    ed = "ed" in sort_order
    ps = "ps" in sort_order
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
        return {}
    callback = {}
    for index, i in enumerate(sorted(table.keys())):
        index += 1
        if not table[i]["code"][-1:] in tail:
            continue
        if not table[i]["code"][0] in prefix:
            continue
        if table[i]["st"] == x:
            if not st:
                continue
        elif table[i]["ed"] == x:
            if not ed:
                continue
        else:
            if not ps:
                continue
        visible += 1
        insert = [visible, table[i]["code"], table[i]["arrive_time"], table[i]["start_time"],
                  " "+str(table[i]["stop_time"])+'\'', table[i]["st"]+"-"+table[i]["ed"], table[i]["class"]]
        if table[i]["st"] == x:
            insert[2] = ""
            insert[4] = ""
        elif table[i]["ed"] == x:
            insert[3] = ""
            insert[4] = ""
        pack["data"].append(insert)
        callback[visible] = "." + table[i]["code"]
    pack["callback"] = callback
    pack["head"] = x + "站 " + str(visible) + "个车次"
    return pack

def print_link(st, ed, sort_order = "st", prefix = "GDCKTZSYP"):
    """起止站搜索，st，ed是两个列表，表示起止站，sort_order表示结果的排序方式，分为st，ed，v。
    prefix表示车次前缀的筛选范围"""
    pack = {"names": ["序号", "车次", "发站", "开点", "到站", "到点", "历时", "始发终到", "类型"],
            "widths": [5, 8, 10, 8, 10, 8, 8, 20, 6],
            "data": [],
            "head": ""}
    if 'P' in prefix:
        prefix += "0123456789"
    callback = {}
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
    print(cnt, "results")
    for i in sorted(index):
        t = table[index[i]]
        if t["code"][0] in prefix:
            visible += 1
            callback[str(visible)] = "." + code
            insert = [visible, t["code"], t["st"], t["start_time"], t["ed"], t["arrive_time"], t["time"],
                      t["start_station"] + '-' + t["end_station"], t["class"]]
            pack["data"].append(insert)

    pack["head"] = st[0] + ' → ' + ed[0] + " " + str(visible) + "个车次"
    return pack


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
city_station = {}

if (os.path.exists('train_data/train_list' + auto_date_1 + '.json') and
        os.path.exists('train_data/no_list' + auto_date_1 + '.json')):
    with open('train_data/train_list' + auto_date_1 + '.json', 'r') as f1:
        train_list = json.load(f1)
    with open('train_data/no_list' + auto_date_1 + '.json', 'r') as f2:
        no_list = json.load(f2)
    print("Load over")
    count_code()

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except AttributeError:
    pass

root = tk.Tk()
root.title("Rail Rhythm 中国铁路时刻表查询工具")
root.geometry("1500x900")

color_lightgreen = "#CCFFF6"
color_white = "#ffffff"

# 左上控制区
control_frame = tk.Frame(root, bg=color_white)
control_frame.place(relx=0.15, rely=0.20, relwidth=0.26, relheight=0.18, anchor="center")
# 日期
control_date_label = tk.Label(control_frame, text="日期", bg=color_white)
control_date_label.place(relx=0.15, rely=0.4, relwidth=0.22, relheight=0.26, anchor="center")
# 创建输入框
control_date_entry = tk.Entry(control_frame)
control_date_entry.place(relx=0.47, rely=0.4, relwidth=0.44, relheight=0.26, anchor="center")
# 创建确定按钮
def date_change():
    date = control_date_entry.get()
    date = date.replace("-", "")
    date = date.replace("/", "")
    print(len(date))
    if len(date) == 8 and 2024 < int(date[0:4]) < 2030 and 0 < int(date[4:6]) < 13 and 0 < int(date[6:]) < 32:
        global auto_date
        global auto_date_1
        auto_date = date[0:4] + '-' + date[4:6] + "-" + date[6:]
        auto_date_1 = auto_date.replace("-", "")
        create_head("日期已经调整为" + auto_date.replace("-", "/"))
    else:
        create_head("日期格式不正确")

control_date_confirm_button = tk.Button(control_frame, text="确定", command=date_change)
control_date_confirm_button.place(relx=0.84, rely=0.4, relwidth=0.22, relheight=0.26, anchor="center")
# 加载按钮
control_load_button = tk.Button(control_frame, text="Load")
control_load_button.place(relx=0.19, rely=0.75, relwidth=0.28, relheight=0.26, anchor="center")
# 保存按钮
control_save_button = tk.Button(control_frame, text="save")
control_save_button.place(relx=0.5, rely=0.75, relwidth=0.28, relheight=0.26, anchor="center")
# 导入按钮
control_save_button = tk.Button(control_frame, text="import")
control_save_button.place(relx=0.81, rely=0.75, relwidth=0.28, relheight=0.26, anchor="center")

# 左中查询操作区
search_frame = tk.Frame(root, bg=color_white)
search_frame.place(relx=0.15, rely=0.58, relwidth=0.26, relheight=0.36, anchor="center")

# 查车次相关组件
search_code = tk.Label(search_frame, text="查车次", bg=color_white)
search_code.place(relx=0.15, rely=0.2, relwidth=0.22, relheight=0.2, anchor="center")
# 创建查车次的输入框
search_code_entry = tk.Entry(search_frame)
search_code_entry.place(relx=0.47, rely=0.2, relwidth=0.44, relheight=0.13, anchor="center")
# 查车次返回文本函数
def get_search_code():
    s = search_code_entry.get()
    search("." + search_code_entry.get())
    if not s in no_list:
        create_head(s + " 不存在")
    elif not no_list[s] in train_list:
        create_head(s + " 当日不开行")
    else:
        pack = print_train(train_list[no_list[s]], ask=True)
        create_table(root, data=pack)
# 创建查车次的确定按钮
search_code_confirm_button = tk.Button(search_frame, text="查询", command=get_search_code)
search_code_confirm_button.place(relx=0.84, rely=0.2, relwidth=0.22, relheight=0.13, anchor="center")

# 查车站相关组件
search_station = tk.Label(search_frame, text="查车站", bg=color_white)
search_station.place(relx=0.15, rely=0.4, relwidth=0.22, relheight=0.2, anchor="center")
# 创建查车站的输入框
search_station_entry = tk.Entry(search_frame)
search_station_entry.place(relx=0.47, rely=0.4, relwidth=0.44, relheight=0.13, anchor="center")
# 查车站返回文本函数
def get_search_station():
    station = search_station_entry.get()
    prefixs = get_prefix_selected_buttons()
    s = "+"
    for index, train_type in enumerate(search_station_train_type_buttons_state):
        if train_type:
            s += search_station_train_type[index]
    search("Station " + station + s + prefixs)
    pack = print_station(x=station, sort_order=s, prefix=prefixs)
    if pack == {}:
        create_head("找不到“" + station + "”站")
    else:
        create_table(root, data=pack)
# 创建查车站的确定按钮
search_station_confirm_button = tk.Button(search_frame, text="查询", command=get_search_station)
search_station_confirm_button.place(relx=0.84, rely=0.4, relwidth=0.22, relheight=0.13, anchor="center")
search_station_train_type = ["st", "ed", "ps", "dn", "up"]
# 列车类型名称列表
search_station_train_type_name = ["始发", "终到", "经停", "下行", "上行"]
# 列车类型按钮状态列表，初始都为 True 表示开启
search_station_train_type_buttons_state = [True, True, True, True, True]
# 初始化按钮列表
search_station_train_type_button = []
# 定义切换按钮状态的函数
def toggle_search_station_train_type_button(index):
    global search_station_train_type_buttons_state
    # 切换对应索引按钮的状态
    search_station_train_type_buttons_state[index] = not search_station_train_type_buttons_state[index]
    if search_station_train_type_buttons_state[index]:
        search_station_train_type_button[index].config(bg="green", text=search_station_train_type_name[index])
    else:
        search_station_train_type_button[index].config(bg="red", text=search_station_train_type_name[index])
# 循环创建按钮
for index, train_type in enumerate(search_station_train_type):
    all_select_button = tk.Button(search_frame, text=search_station_train_type_name[index],
                                  bg="green" if search_station_train_type_buttons_state[index] else "red",
                                  command=lambda idx=index: toggle_search_station_train_type_button(idx))
    all_select_button.place(relx=0.31 + index * 0.145, rely=0.55, relwidth=0.12, relheight=0.13, anchor="center")
    search_station_train_type_button.append(all_select_button)


# 查站站相关组件 - 第一行
search_link = tk.Label(search_frame, text="查站站", bg=color_white)
search_link.place(relx=0.15, rely=0.73, relwidth=0.22, relheight=0.2, anchor="center")
# 第一个文本框
search_link_st = tk.Entry(search_frame)
search_link_st.place(relx=0.4, rely=0.73, relwidth=0.3, relheight=0.13, anchor="center")
# 向右箭头 Label
search_link_arrow = tk.Label(search_frame, text="→", bg=color_white)
search_link_arrow.place(relx=0.6, rely=0.73, relwidth=0.05, relheight=0.2, anchor="center")
# 第二个文本框
search_link_ed = tk.Entry(search_frame)
search_link_ed.place(relx=0.8, rely=0.73, relwidth=0.3, relheight=0.13, anchor="center")
# 查站站相关组件-排序方式
modes = ["出发时间", "到达时间", "运行时长"]
search_link_sort_mode = 0
def toggle_mode():
    global search_link_sort_mode
    search_link_sort_mode = (search_link_sort_mode + 1) % 3
    current_mode = modes[search_link_sort_mode]
    if current_mode == "出发时间":
        search_link_sort_order.config(bg="red", text=current_mode)
    elif current_mode == "到达时间":
        search_link_sort_order.config(bg="green", text=current_mode)
    else:
        search_link_sort_order.config(bg="blue", text=current_mode)
search_link_sort_order = tk.Button(search_frame, text=modes[search_link_sort_mode], bg="red", command=toggle_mode)
search_link_sort_order.place(relx=0.36, rely=0.88, relwidth=0.22, relheight=0.13, anchor="center")
# 是否模糊站名
search_link_fuzzy_button_state = False  # 初始状态为未选中
def search_link_fuzzy_button():
    global search_link_fuzzy_button_state
    if search_link_fuzzy_button_state:
        search_link_fuzzy_button.config(bg="red", text="精准站名")
        search_link_fuzzy_button_state = False
    else:
        search_link_fuzzy_button.config(bg="green", text="模糊站名")
        search_link_fuzzy_button_state = True
search_link_fuzzy_button = tk.Button(search_frame, text="精准站名", bg="red", command=search_link_fuzzy_button)
search_link_fuzzy_button.place(relx=0.6, rely=0.88, relwidth=0.22, relheight=0.13, anchor="center")
def get_search_link():
    if search_link_fuzzy_button_state:
        link_char = "--"
    else:
        link_char = "-"
    if search_link_sort_mode == 0:
        sort_mode = "+st"
    elif search_link_sort_mode == 1:
        sort_mode = "+ed"
    else:
        sort_mode = "+v"
    search(search_link_st.get() + link_char + search_link_ed.get() + get_prefix_selected_buttons())
    st = [search_link_st.get()]
    ed = [search_link_ed.get()]
    pack = print_link(st, ed, sort_order=sort_mode, prefix=get_prefix_selected_buttons())
    create_head(pack["head"])
    create_table(root, data=pack)
# 查询按钮
search_link_confirm_button = tk.Button(search_frame, text="查询", command=get_search_link)
search_link_confirm_button.place(relx=0.84, rely=0.88, relwidth=0.22, relheight=0.13, anchor="center")

# 创建 prefix_control 框架，筛选字头供查车站、查站站
prefix_control = tk.Frame(root, bg=color_white)
prefix_control.place(relx=0.15, rely=0.82, relwidth=0.26, relheight=0.08, anchor="center")
# 按钮文本列表
button_texts = list("GDCZTKSYP")
# 按钮状态列表，初始全为 True
prefix_control_button_states = [True] * len(button_texts)
# 按钮对象列表
prefix_control_button = []
# 切换按钮状态的函数
def toggle_button_state(index):
    prefix_control_button_states[index] = not prefix_control_button_states[index]
    if prefix_control_button_states[index]:
        prefix_control_button[index].config(bg="green")
    else:
        prefix_control_button[index].config(bg="red")
# 循环创建按钮
for i, text in enumerate(button_texts):
    button = tk.Button(prefix_control, text=text, bg="green", command=lambda idx=i: toggle_button_state(idx))
    button.place(relx=0.11+i*0.1, rely=0.5, relwidth=0.08, relheight=0.6, anchor="center")
    prefix_control_button.append(button)
def get_prefix_selected_buttons():
    result = "*"
    for i, state in enumerate(prefix_control_button_states):
        if state:
            result += button_texts[i]
    return result

# 搜索词转化为instruction后的显示
instruction_show = tk.Frame(root, bg=color_white)
instruction_show.place(relx=0.15, rely=0.92, relwidth=0.26, relheight=0.08, anchor="center")
# 在 instruction_show 框架内添加一个 Label 用于显示文本
instruction_label = tk.Label(instruction_show, text="", bg=color_white)
instruction_label.pack(fill=tk.BOTH, expand=True)

def search(s):
    # 更新 instruction_label 的文本内容为 s
    instruction_label.config(text=s)



# 创建一个 Label 用于放置表格
table_label = tk.Label(root, bg=color_white, text="github.com/wj0575/RailRhythm12306",
                       font=("Calibri", 20, "italic"), fg="#D17474")
table_label.place(relx=0.63, rely=0.5, anchor=tk.CENTER, relwidth=0.66, relheight=0.92)
word = tk.Label(table_label, bg=color_white, text="Rail Rhythm", font=("Calibri", 40, "italic"))
word.place(relx=0.5, rely=0.42, anchor="center", relwidth=0.66, relheight=0.1)

head_label = None
def create_head(head_text):
    global head_label
    if head_label:
        # 如果 Label 组件已经存在，更新其文本内容
        head_label.config(text=head_text)
    else:
        # 如果 Label 组件不存在，创建新的 Label 组件
        head_label = tk.Label(root, text=head_text, font=('黑体', 18))
        head_label.place(relx=0.15, rely=0.06, relwidth=0.3, relheight=0.1, anchor="center")

def on_item_click(item_text):
    print(f"你点击了: {item_text}")
def create_table(root, data):
    global table_frame
    if 'table_frame' in globals() and table_frame.winfo_exists():
        for widget in table_frame.winfo_children():
            widget.destroy()
        table_frame.destroy()

    # 创建一个带有滚动条的框架，放置在 Label 内
    table_frame = tk.Frame(table_label)
    table_frame.place(relx=0.01, rely=0.01, relwidth=0.98, relheight=0.98)
    # 创建一个 Canvas 用于放置表格
    canvas = tk.Canvas(table_frame)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    # 创建垂直滚动条
    scrollbar = ttk.Scrollbar(table_frame, command=canvas.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    # 配置 Canvas 与滚动条关联
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    # 创建一个内部框架用于放置表格内容
    inner_frame = tk.Frame(canvas)
    canvas.create_window((0, 0), window=inner_frame, anchor="nw")
    # 创建总览
    create_head(data["head"])
    # 创建表头
    for i, (name, width) in enumerate(zip(data["names"], data["widths"])):
        label = tk.Label(inner_frame, text=name, width=width, pady=8, font=("黑体", 11), borderwidth=0)
        label.grid(row=0, column=i, sticky="nsew")

    # 创建表格内容
    for row_index, row_data in enumerate(data["data"], start=1):
        bg_color = "white" if row_index % 2 == 1 else None  # 判断是否为奇数行
        for col_index, item in enumerate(row_data):
            if isinstance(item, tuple):
                # 如果是可点击的文字，创建一个按钮
                text, callback = item
                button = tk.Button(inner_frame, text=text, width=data["widths"][col_index], pady=8, borderwidth=0,
                                   command=lambda t=text: callback(t), font=("黑体", 13), bg=bg_color)
                button.grid(row=row_index, column=col_index, sticky="nsew")
            else:
                # 普通文字，创建一个标签
                label = tk.Label(inner_frame, text=item, width=data["widths"][col_index], pady=8, borderwidth=0,
                                 font=("黑体", 13), bg=bg_color)
                label.grid(row=row_index, column=col_index, sticky="nsew")

    # 绑定鼠标滚轮事件
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    canvas.bind_all("<MouseWheel>", _on_mousewheel)

root.mainloop()