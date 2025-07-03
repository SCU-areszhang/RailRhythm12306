from matplotlib import pyplot as plt
import os.path
import random
import json

from matplotlib import font_manager

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
    plt.grid(True, color='lightgrey', linestyle='-', linewidth=0.3)
    # 设置标题
    plt.title(table_name["name"])

    # 设置横纵坐标起止点
    plt.xlim(330, 1440)
    plt.ylim(0, max(ticks_y))

    plt.gca().set_aspect(6.5)
    return fig


import random
import math


def generate_color(seed):
    if seed == 0:
        normalized = 0.0
    else:
        normalized = math.log(abs(seed) + 1, 10) / 5  # 假设10^5为"大数"的分界线
        normalized = min(max(normalized, 0.0), 1.0)  # 限制在0-1之间

    # 根据数值大小选择不同的颜色范围
    if normalized > 0.7:  # 大数 - 偏向棕色、红色、橙色
        base_hue = random.uniform(0.0, 0.15)  # 0-0.15是红到橙的范围
        saturation = 0.7 + random.random() * 0.3  # 高饱和度
        lightness = 0.4 + random.random() * 0.2  # 中等亮度
    else:  # 小数 - 偏向蓝色、绿色、黄色、紫色
        base_hue = random.uniform(0.4, 0.8)  # 蓝到绿到紫的范围
        saturation = 0.4 + random.random() * 0.4  # 中等饱和度
        lightness = 0.7 + random.random() * 0.2  # 较高亮度

    # 添加一些随机变化
    hue_variation = random.gauss(0, 0.05)
    final_hue = (base_hue + hue_variation) % 1.0

    # 将HSL转换为RGB
    def hsl_to_rgb(h, s, l):
        def hue_to_rgb(p, q, t):
            t = t % 1.0
            if t < 1 / 6: return p + (q - p) * 6 * t
            if t < 1 / 2: return q
            if t < 2 / 3: return p + (q - p) * (2 / 3 - t) * 6
            return p

        if s == 0:
            r = g = b = l
        else:
            q = l * (1 + s) if l < 0.5 else l + s - l * s
            p = 2 * l - q
            r = hue_to_rgb(p, q, h + 1 / 3)
            g = hue_to_rgb(p, q, h)
            b = hue_to_rgb(p, q, h - 1 / 3)
        return round(r * 255), round(g * 255), round(b * 255)

    r, g, b = hsl_to_rgb(final_hue, saturation, lightness)

    # 转换为16进制
    return "#{:02x}{:02x}{:02x}".format(r, g, b)

def find_pass(train_list, station_list, find_access_num, auto_judge=True, up_or_dn = 0):
    pass_list = []
    for train in train_list:
        cnt = 0
        pack = []
        for station_data in train_list[train]:
            if station_data["station_name"] in station_list:
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


def draw_line(train_data, station_dict, up_or_dn = 0):
    color = generate_color(train_data[0]["station_train_code"][0])
    x_list = []
    y_list = []
    for station in train_data:
        if station["station_name"] in station_dict:
            if len(station["arrive_time"]) == 5:
                x_list.append(time_transfer(station["arrive_time"]))
                y_list.append(station_dict[station["station_name"]])
            if len(station["start_time"]) == 5:
                x_list.append(time_transfer(station["start_time"]))
                y_list.append(station_dict[station["station_name"]])
    if (x_list[0] - x_list[-1]) * (y_list[-1] - y_list[0]) > 0:
        if up_or_dn == 1:
            return
    else:
        if up_or_dn == 2:
            return
    # 求首尾点连线斜率的绝对值
    k = abs((y_list[-1] - y_list[0]) / (x_list[-1] - x_list[0]))
    print(k)

    if x_list and y_list:
        # 绘制折线图，没有点，只有线
        plt.plot(x_list, y_list, marker='', linestyle='-', color=color, linewidth=0.5)

line_pack = {
    "京沪": {
        "line_name": "京沪高速铁路",
        "station_dict": {
    "北京南": 0,
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
    "上海虹桥": 1318
        }
    },
    "杭甬": {
        "line_name": "杭甬客运专线",
        "station_dict": {
    "杭州东": 0,
    "杭州南": 5,
    "绍兴北": 18,
    "绍兴东": 28,
    "余姚北": 40,
    "庄桥": 54,
    "宁波": 60,
}
    },
}


if __name__ == "__main__":
    # instruction = input("Input instruction: ")
    # date = input("Input date: ")
    instruction = "京沪 0"
    date = "20250703"
    target_line, up_or_dn = instruction.split(" ")
    up_or_dn = int(up_or_dn)

    station_dict = scale_values(line_pack[target_line]["station_dict"], new_max=60)
    table_name = {
        "name": line_pack[target_line]["line_name"] + "运行图" + date
    }
    if up_or_dn == 1:
        table_name["name"] += "上行"
    elif up_or_dn == 2:
        table_name["name"] += "下行"
    # 导入train_list,no_list
    # date = input("Input date: ")
    up_or_dn = 1

    file_name_train = 'train_data/train_list'+date+'.json'
    file_name_no = 'train_data/no_list'+date+'.json'
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
    pass_list = find_pass(train_list, stations, 2, auto_judge=True)
    print(pass_list)

    # 调用绘制框架函数
    figure = setup_plot(station_dict, table_name)

    for train in pass_list:
        # 在每个车次的基础上，调用函数，绘制折线图
        draw_line(train, station_dict, up_or_dn=up_or_dn)
    # 保存图片
    plt.savefig("京沪高速铁路.png", dpi=300)
    # plt.show()



