from matplotlib import pyplot as plt
import os.path
import random
import json

from matplotlib import font_manager
from requests import delete

font = font_manager.FontProperties(fname='C:/Windows/Fonts/simhei.ttf')  # 黑体字体路径，不同系统路径可能不同
plt.rcParams['font.family'] = font.get_name()

def time_transfer(time):
    """这个函数用于将时间转换为分钟数
    参数time为一个字符串，格式为HH:MM"""
    return int(time[:2])*60+int(time[3:])
def time_transfer_back(time):
    """这个函数用于将分钟数转换为时间
    参数time为一个整数"""
    return str(time//60).zfill(2)+":"+str(time%60).zfill(2)

def scale_values(data_dict, new_max=60):
    """将字典值线性缩放到[0, new_max]区间"""
    values = list(data_dict.values())
    min_val = min(values)
    max_val = max(values)
    scaled_dict = {
        k: (v - min_val) * new_max / (max_val - min_val)
        for k, v in data_dict.items()
    }
    return scaled_dict

def print_train(x):
    """这个函数用于输出一个车次的信息
    参数x为一个字典"""
    # print(x)
    code = x[0]["station_train_code"]
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
        if i["arrive_day_diff"] != d:
            d = i["arrive_day_diff"]
            print("Day",int(d)+1,end="  ")
        if i["station_train_code"] != code:
            code = i["station_train_code"]
            print("switch to",code,end="  ")
        print("",end="\n")
def setup_plot(station_dict, table_name):
    """
    此函数用于设置绘图的基本参数，包括创建绘图窗口、设置刻度和标题等。

    :param station_dict: 车站字典，键为车站名称，值为位置值
    :param table_name: 包含图表标题的字典，使用 "name" 键获取标题
    """
    # 绘制横线
    fig = plt.figure
    # 设置绘图区的大小
    plt.figure(figsize=(25, 10))
    # 刻度设置
    ticks_x = []
    labels_x = []
    ticks_y = []
    labels_y = []
    for i in range(240, 1441, 30):
        ticks_x.append(i)
        labels_x.append(time_transfer_back(i))
    for station_name, position in station_dict.items():
        ticks_y.append(position)
        labels_y.append(station_name)
    plt.xticks(ticks_x, labels_x, rotation=45, fontsize=9)
    plt.yticks(ticks_y, labels_y, fontsize=9)
    plt.grid(True, color='lightgrey', linestyle='-', linewidth=0.4)
    # 设置标题，标题上移一段距离
    plt.title(table_name["name"], fontsize=30, y=1.05, weight='bold', x=0.5, ha='center')
    # 设置副标题
    plt.suptitle("         https://github.com/wj0575/RailRhythm12306", fontsize=8, font='consolas',
                 y=0.868, color=generate_color(0.5, 1), x=0.5, ha='center')
    # 设置背景文字，放置在最底层
    bg_setting = table_name["background_text"]
    if bg_setting[0]!= "":
        for i in range(0, bg_setting[3]):
            plt.text(random.random()*0.8+0.1, random.random()*0.8+0.1, bg_setting[0],
                     fontsize=bg_setting[2], color=bg_setting[1], rotation=random.random()*360,
                     ha='center', va='center', transform=plt.gca().transAxes, zorder=0)
    # 设置横纵坐标起止点
    plt.xlim(330, 1440)
    plt.ylim(0, max(ticks_y))

    plt.gca().set_aspect(6.5)
    return fig

def generate_color(seed, mark):
    if seed > mark:  # 大数
        r = random.random() * 100 + 155 # 127-255
        g = random.random() * 100  # 0-64
        b = random.random() * 32  # 0-64
    else:  # 小数
        while True:
            r = random.random() * 128  # 64-128
            g = random.random() * 255  # 0-255
            b = random.random() * 255  # 0-255
            if 128 < r + g * 0.8 + b < 512:
                break

    return "#{:02x}{:02x}{:02x}".format(int(r), int(g), int(b))

def find_pass(train_list, station_list, find_access_num, auto_judge, delete_list):
    pass_list = []
    for train in train_list:
        # print(train)
        flag = False
        for delete_train in delete_list[0]:
            if no_list[delete_train] == train:
                flag = True
        if flag:
            continue
        cnt = 0
        pack = []
        for station_data in train_list[train]:
            if station_data["station_name"] in station_list:
                if(station_data["station_train_code"] + station_data["station_name"]) in delete_list[1]:
                    continue
                pack.append({
                    "station_name": station_data["station_name"],
                    "station_train_code": station_data["station_train_code"],
                    "arrive_time": station_data["arrive_time"],
                    "start_time": station_data["start_time"],
                    "arrive_day_diff": station_data["arrive_day_diff"],
                })
                cnt += 1
            else:
                if cnt >= find_access_num:
                    if auto_judge:
                        pass_list.append(pack)
                    else:
                        print_train(train_list[train])
                        r = input("Input 1 to pass, 0 to not pass: ")
                        if r == '1':
                            pass_list.append(pack)
                cnt = 0
                pack = []
        if cnt >= find_access_num:
            if auto_judge:
                pass_list.append(pack)
            else:
                print_train(train_list[train])
                r = input("Input 1 to pass, 0 to not pass: ")
                if r == '1':
                    pass_list.append(pack)
    return pass_list
def select_pass(line_name, pass_list):
    """
    这个函数用于筛选符合条件的车次。特殊判断法。新增加线路时要手动添加特征。
    :param line_name:
    :param pass_list:
    :return:
    """
    if line_name == "京沪":
        # 使用列表推导式创建新列表（避免遍历时修改原列表的问题）
        filtered_list = [
            train for train in pass_list
            if not (
                len(train) == 2 and
                {train[0]["station_name"], train[1]["station_name"]} <= {"昆山南", "上海虹桥", "上海"}
            )
        ]
        return filtered_list
    elif line_name == "杭甬" or line_name == "杭深":
        filtered_list = [
            train for train in pass_list
            if not (
                len(train) == 2 and
                {train[0]["station_name"], train[1]["station_name"]} <= {"杭州南", "杭州东"}
            )
        ]
        return filtered_list
    elif line_name == "沪昆":
        filtered_list = [
            train for train in pass_list
            if not (
                len(train) == 2 and
                {train[0]["station_name"], train[1]["station_name"]} <= {"上海虹桥", "上海松江", "上海南"} or
                {train[0]["station_name"], train[1]["station_name"]} <= {"杭州南", "杭州东"} or
                {train[0]["station_name"], train[1]["station_name"]} <= {"贵安", "贵阳北"} or
                {train[0]["station_name"], train[1]["station_name"]} <= {"贵阳北", "贵阳东"}
            ) and not(
                train[0]["station_train_code"][0] in "KTZY" or
                train[0]["station_train_code"][0] == 'D' and int(train[0]["station_train_code"][1:]) < 400 or
                train[0]["station_train_code"][0] == 'C' and int(train[0]["station_train_code"][1:]) < 1000 or
                train[0]["station_train_code"][0] == 'C' and 4000 < int(train[0]["station_train_code"][1:]) < 5000
            )
        ]
        return filtered_list
    return pass_list

def draw_line(train_data, station_dict, mark, code = 0, up_or_dn = 0):
    x_list = []
    y_list = []
    for station in train_data:
        if station["station_name"] in station_dict:
            if len(station["arrive_time"]) == 5:
                x_list.append(time_transfer(station["arrive_time"]) + int(station["arrive_day_diff"]) * 1440)
                y_list.append(station_dict[station["station_name"]])
            if len(station["start_time"]) == 5:
                x_list.append(time_transfer(station["start_time"]) + int(station["arrive_day_diff"]) * 1440)
                y_list.append(station_dict[station["station_name"]])
    if (x_list[0] - x_list[-1]) * (y_list[-1] - y_list[0]) > 0:
        if up_or_dn == 1:
            return
    else:
        if up_or_dn == 2:
            return
    # 求首尾点连线斜率的绝对值
    k = abs((y_list[-1] - y_list[0]) / (x_list[-1] - x_list[0]))
    # print(k)
    color = generate_color(k, mark)
    if x_list and y_list:
        plt.plot(x_list, y_list, marker='', linestyle='-', color=color, linewidth=0.5)
    # 如果code为1，则在图上标注车次
    if code == 1:
        if up_or_dn == 1:
            rotation = -45
            ha = 'left'
            va = 'top'
            ha_1 = 'right'
            va_1 = 'bottom'
        elif up_or_dn == 2:
            rotation = 45
            ha = 'left'
            va = 'bottom'
            ha_1 = 'right'
            va_1 = 'top'
        else:
            rotation = 90
            ha = 'center'
            va = 'bottom'
            ha_1 = 'center'
            va_1 = 'bottom'
        text = train_data[0]["station_train_code"]
        plt.text(x_list[0], y_list[0], text, fontsize=3, color=color, font='Arial',
                 ha=ha, va=va, rotation=rotation)
        plt.text(x_list[-1], y_list[-1], text, fontsize=3, color=color, font='Arial',
                 ha=ha_1, va=va_1, rotation=rotation)

line_pack = {
    "京沪": {
        "line_name": "京沪高速铁路",
        "mark": 0.2,
        "station_dict": {
    "北京南": 0-10, # 补偿限速
    "廊坊": 60,
    "天津南": 122,
    "沧州西": 210,
    "德州东": 314,
    "济南西": 406,
    "泰安": 465,
    "曲阜东": 535,
    "滕州东": 591,
    "枣庄": 627,
    "徐州东": 692,
    "宿州东": 760,
    "蚌埠南": 848,
    "定远": 902,
    "滁州": 964,
    "南京南": 1023,
    "镇江南": 1088,
    "丹阳北": 1120,
    "常州北": 1153,
    "无锡东": 1210,
    "苏州北": 1237,
    "昆山南": 1268,
    "上海虹桥": 1318,
    "上海": 1335
        },
        "delete_list": [
            ["G1830", "D1606", "D1605", "D1603", "D2777", "G1829", "D1643"],
            {"G380德州东"}
        ],
    },
    "杭甬": {
        "line_name": "杭甬客运专线-甬台温铁路",
        "mark": 0.3,
        "station_dict": {
    "杭州东": 0,
    "杭州南": 16,
    "绍兴北": 43,
    "绍兴东": 74,
    "余姚北": 106,
    "庄桥": 147,
    "宁波": 155,
    "奉化": 193,
    "宁海": 227,
    "三门县": 261,
    "临海": 284,
    "台州西": 307,
    "温岭": 331,
    "雁荡山": 354,
    "乐清": 395,
    "温州北": 412,
    "温州南": 430,
    "瑞安": 470,
    "平阳": 487,
    "苍南": 524,
},
        "delete_list": [[],[]]
    },
    "沪昆": {
        "line_name": "沪昆高速铁路（东段）",
        "mark": 0.2,
        "station_dict": {
    "上海虹桥": 0-5, # 修正
    "上海南": 0,
    "上海松江": 31,
    "金山北": 48,
    "嘉善南": 67,
    "嘉兴南": 84,
    "桐乡": 112,
    "海宁西": 133,
    "临平南": 144,
    "杭州东": 159,
    "杭州南": 175,
    "诸暨": 225,
    "义乌": 268,
    "金华": 320,
    "龙游": 369,
    "衢州": 398,
    "江山": 428,
    "玉山南": 466,
    "上饶": 500,
    "弋阳": 560,
    "鹰潭北": 601,
    "抚州东": 644,
    "进贤南": 683,
    "南昌西": 741,
    "高安": 788,
    "新余北": 868,
    "宜春": 917,
    "萍乡北": 978,
    "醴陵东": 1007,
    "长沙南": 1083,
}
    }
}


if __name__ == "__main__":
    # instruction = input("Input instruction: ")
    # date = input("Input date: ")
    """"""
    instruction = "沪昆 2 1"
    date = "20250703"
    background_text = ["", "#EEEEFF", 10, 20] # 字号，个数
    """"""
    target_line, up_or_dn, code= instruction.split(" ")
    mark = line_pack[target_line]["mark"]
    if "delete_list" in line_pack[target_line]:
        delete_list = line_pack[target_line]["delete_list"]
    else:
        delete_list = [[],[]]
    up_or_dn, code= int(up_or_dn), int(code)

    station_dict = scale_values(line_pack[target_line]["station_dict"], new_max=60)
    table_name = {
        "name": line_pack[target_line]["line_name"] + date,
        "background_text": background_text
    }
    if up_or_dn == 1:
        table_name["name"] += "下行"
    elif up_or_dn == 2:
        table_name["name"] += "上行"

    file_name_train = 'train_data/train_list' + date + '.json'
    file_name_no = 'train_data/no_list' + date + '.json'
    if os.path.exists(file_name_train) and os.path.exists(file_name_no):
        with open(file_name_train, 'r') as f:
            train_list = json.load(f)
        with open(file_name_no, 'r') as f:
            no_list = eval(f.read())
        print("Import success.")
    else:
        print("File not exists.")
        exit()

    # 将station_dict的车站名称提取出来
    stations = list(station_dict.keys())
    # 筛选出符合条件的车次，即车次连续经过至少两个站
    pass_list = find_pass(train_list, stations, 2, delete_list=delete_list, auto_judge=True)

    pass_list = select_pass(target_line, pass_list)

    # print(pass_list)

    # 调用绘制框架函数
    figure = setup_plot(station_dict, table_name)

    for train in pass_list:
        # 在每个车次的基础上，调用函数，绘制折线图
        draw_line(train, station_dict, mark=mark, code=code, up_or_dn=up_or_dn)
    # 保存图片
    plt.savefig(table_name["name"] + ".png", dpi=300)
    # 给出路径
    print("Picture saved in " + table_name["name"] + ".png")
    # plt.show()



