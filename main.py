# coding=utf-8
import serial  # package name: pyserial
from serial.tools.list_ports import comports
import os
import time
import keyboard
# import tkinter.messagebox
# import tkinter
import matplotlib.pyplot as plt
import re
import csv
import datetime
import schedule
# import yaml


# create .exe: pyinstaller -F main.py


def DectoHex(dec):
    if 9 >= dec >= 0:
        return f'{dec}'
    elif dec == 10:
        return 'a'
    elif dec == 11:
        return 'b'
    elif dec == 12:
        return 'c'
    elif dec == 13:
        return 'd'
    elif dec == 14:
        return 'e'
    elif dec == 15:
        return 'f'
    else:
        raise ValueError


class CMDUI(object):
    def __init__(self):
        self.runflag = True
        self.comname = None  # 当前串口号
        self.com = None  # com类
        self.ADC1 = None  # ADC1解码后
        self.ADC2 = None  # ADC2解码后
        self.ADC3 = None  # ADC3解码后
        self.ADC4 = None  # ADC4解码后
        self.csvfile = None  # csv文件
        self.csvfilename = None  # csv文件名
        self.csvwriter = None  # csv writer

        """use yaml"""
        # if not os.path.exists("config.yaml"):  # 若不存在配置文件
        #     default_config = {
        #         'baundrate': 256000,
        #         'rxlength': 160,
        #         'SensorNum': 16,
        #         'savedir': './Receive',
        #         'csvmask': 0
        #     }
        #     print("配置文件不存在，已在程序根目录创建配置文件config.yaml，使用默认配置:")
        #     print(default_config)
        #     with open("config.yaml", "w", encoding="utf-8") as file:
        #         yaml.dump(default_config, file)
        #     with open("config.yaml", "a", encoding="utf-8") as file:
        #         file.writelines("\n##############################\n")
        #         file.writelines("# 请严格遵守yaml文件格式，如遇错误请删除此文件并重启程序\n")
        #         file.writelines("# baundrate: 波特率(默认256000)\n")
        #         file.writelines("# rxlength: 数据帧长度(默认80)\n")
        #         file.writelines("# SensorNum: 使用ADC的数量\n")
        #         file.writelines("# savedir: csv文件保存路径(默认./Receive)\n")
        #         file.writelines("# csvmask: csv储存通道屏蔽列表，1~32(max)，0为禁用，例如：\n#csvmask:\n#- 1\n#- 2\n#- 3\n")
        #
        # with open('config.yaml', 'r', encoding='utf-8') as file:  # 读取配置文件
        #     print("正在读取配置文件... 如遇错误，请删除config.yaml并重启程序.")
        #     config = yaml.load(file.read(), Loader=yaml.Loader)
        #     self.baundrate = config['baundrate']
        #     self.rxlength = config['rxlength']
        #     self.SensorNum = config['SensorNum']
        #     self.savedir = config['savedir']
        #     self.csvmask = config['csvmask']
        #     print("读取配置文件成功.\n如需更改配置参数，请手动修改config.yaml文件.")
        # if type(self.csvmask) is list and len(self.csvmask) > 0:
        #     self.csvmask.sort(reverse=True)
        # else:
        #     self.csvmask = []

        """not use yaml"""
        default_config = {
            'baundrate': 256000,
            'rxlength': 160,
            'SensorNum': 16,
            'savedir': './Receive',
            'csvmask': 0
        }
        self.baundrate = default_config['baundrate']
        self.rxlength = default_config['rxlength']
        self.SensorNum = default_config['SensorNum']
        self.savedir = default_config['savedir']
        self.csvmask = default_config['csvmask']
        if type(self.csvmask) is list and len(self.csvmask) > 0:
            self.csvmask.sort(reverse=True)
        else:
            self.csvmask = []

        self.plottimer = [0]  # 绘图的横坐标(时间t, 单位min)
        self.period_save = 10  # 自动保存周期, 单位sec
        self.period_plot = 0.2  # 绘图更新周期, 单位sec
        self.flag_plot = False
        self.period_display = 60  # 绘图显示长度，单位sec
        self.plotdata = [[0] for x in range(32)]  # 绘图数据
        self.savebuf = []

    def run(self):
        '''连接串口'''
        print("===== System Start =====")
        while not self.com:
            self._connect()
        '''接收前初始化'''
        # keyboard.add_hotkey('esc', self.__hotkey_esc)
        keyboard.add_hotkey('q', self.__hotkey_quit)
        keyboard.add_hotkey('w', self.__hotkey_save)
        schedule.every(self.period_save).seconds.do(self.__auto_saving)  # 设置定时执行: 自动保存csv
        schedule.every(self.period_plot).seconds.do(self.__flag_plot_True)  # 设置定时执行: 更新图像
        plt.ion()  # interactive mode on (不同于MATLAB的hold on)
        self.savedir_init()  # 初始化保存路径
        '''开始接收'''
        print("===== Start Receiving =====")
        while self.runflag:
            self._receive()
            schedule.run_pending()

    def stop_receive(self):
        self.runflag = False

    def savedir_init(self):
        if not os.path.exists(self.savedir):
            os.mkdir(self.savedir)
        csvfiletime = datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d_%H-%M-%S')
        self.csvfilename = 'comdata_{}.csv'.format(csvfiletime)
        self.csvfile = open('{}/{}'.format(self.savedir, self.csvfilename), 'a', newline='')
        self.csvwriter = csv.writer(self.csvfile)
        print("[INFO] Receive start from {}, save as {}/{}".format(csvfiletime, self.savedir, self.csvfilename))

    def _receive(self):
        try:  # 尝试接收
            counter = time.time()
            rxdata = self.com.read(self.rxlength).hex()  # 转换为十六进制
            if rxdata[:4] != 'aaaa':
                return
            print("\rReceive: {}... ({}bytes/{:.3f}s, using {} ADCs)".format(rxdata[0:40], self.rxlength, round(time.time() - counter, 3),
                                                                             self.SensorNum), end='')
        except serial.serialutil.SerialException:  # 若连接中断
            self.com = None
            print("\r[ERROR] Connection lost! Please check your cable and connection! Trying to reconnect...")
            while not self.com:  # 尝试重连
                try:
                    self.com = serial.Serial(self.comname, self.baundrate, timeout=1)
                except serial.serialutil.SerialException:
                    time.sleep(0.01)
                else:
                    print("[INFO] Successfully reconnect to {} at {} baundrate!".format(self.comname, self.baundrate))
        else:  # 若接收成功
            if rxdata:  # 若rxdata不为空
                self._decode_display(rxdata)

    def _decode_display(self, rxdata):
        """
        解码数据，保存csv
        :return:
        """
        locater = []
        for i in range(self.SensorNum):
            locater.append(str(rxdata).find(f'aaaa0{DectoHex(i)}00') + 8)
        rx = []
        for i, loc in enumerate(locater):
            if i < len(locater) - 1:
                rx.append(str(rxdata[locater[i]:locater[i + 1] - 8]))
            else:
                rx.append(str(rxdata[locater[i]:]))
            # x[2:]+x[:2]: abcd->cdab, /6553.5: transform to floatpoint number, findall(r'.{4}', rx1): split str every 4 char
            rx[-1] = list(map(lambda x: round(int(x[2:] + x[:2], 16), 6), re.findall(r'.{4}', rx[-1])))
            rx[-1] = list(map(lambda x: x / 6553.5 if x <= 32767 else (x - 65535) / 6553.5, rx[-1]))

        csvdata = []
        for x in range(self.SensorNum):
            csvdata += rx[x]
        for x in self.csvmask:
            del csvdata[x - 1]

        self.savebuf = csvdata
        # self._save_tocsv(csvdata)  # save every datapoints to csv

        if self.flag_plot is True:
            self._update_plot(rx)
            self.flag_plot = False

    def _save_tocsv(self, data):
        try:
            self.csvwriter.writerow(data)  # save every datapoints to csv
        except ValueError:
            if self.runflag:
                print("\n[ERROR] CSV file save error\n")

    def _write(self):
        # result = self.com.write(" ".encode("gbk"))
        # print("写总字节数:", result)
        pass

    def _connect(self):
        comlist = list(comports())
        if len(comlist):  # 若存在可用串口
            '''选择串口'''
            comlist = list(map(lambda x: list(x), comlist))
            print("[INFO] Available COMs are listed below:")
            if len(comlist) == 1 & str(comlist[0][1]).find('CH340') != -1:  # 若只存在一个串口且是CH340
                print(comlist)  # 打印出所有可用的串口，选择描述为“USB-SERIAL CH340”的设备
                self.comname = comlist[0][0]
                print("[INFO] Use {}.".format(self.comname))
            elif len(comlist) == 1 & str(comlist[0][1]).find('CH340') == -1:  # 若只存在一个串口且但不是CH340
                print(comlist)  # 打印出所有可用的串口
                print('[ERROR] COM of CH340 is not found! Please check your connection or driver. Press Enter to retry.')
                os.system('pause')
            else:  # 若存在多个串口
                self.comname = comcandidate = ''
                for item in comlist:
                    print(item[0], item)  # 打印出所有可用的串口
                    comcandidate = comcandidate + str(item[0])
                while self.comname == '':
                    self.comname = input("[INPUT] Which one to choose? Please type in a COM (for example: COM1):")
                    if comcandidate.find(self.comname) == -1:
                        print("[ERROR] {} is not exist! Please check your input and retry.".format(self.comname))
                        self.comname = ''
                    else:
                        print("[INFO] Use {}.".format(self.comname))
            '''尝试连接'''
            try:
                print("[INFO] Try to connect to {} at {} baundrate...".format(self.comname, self.baundrate))
                self.com = serial.Serial(self.comname, self.baundrate, timeout=1)
            except Exception as e:
                print("[ERROR]", e)
                print("Press Enter to retry.")
                os.system('pause')
            else:
                print("[INFO] Successfully connect to {} at {} baundrate!".format(self.comname, self.baundrate))
                '''出口'''
        else:  # 若不存在串口
            print("[ERROR] COM does not exist! Press Enter to retry.")
            os.system('pause')

    def _update_plot(self, rx):
        """
        更新绘图
        """
        cnames = ('aqua', 'aquamarine', 'black', 'blue', 'blueviolet', 'brown', 'burlywood',
                  'cadetblue', 'chartreuse', 'chocolate', 'coral', 'cornflowerblue',
                  'crimson', 'darkblue', 'darkcyan', 'darkgoldenrod', 'darkgray', 'darkgreen', 'darkkhaki',
                  'darkmagenta', 'darkolivegreen', 'darkorange', 'darkorchid', 'darkred')
        plt.cla()
        self.plottimer.append(self.plottimer[-1] + self.period_plot)
        try:
            '''散点图'''
            # for i, x in enumerate(self.ADC1 + self.ADC2 + self.ADC3 + self.ADC4):
            #     plt.scatter(self.plottimer[-1], x, color=cnames[i])
            # plt.pause(0.001)
            '''折线图'''
            for i, sensor in enumerate([rx[0], rx[-1]]):  # only draw fig for U1 and U16
                try:
                    for datai, data in enumerate(sensor):
                        self.plotdata[i * 8 + datai].append(data)
                        if len(self.plottimer) > self.period_display:
                            plt.plot(self.plottimer[:self.period_display],
                                     self.plotdata[i * 8 + datai][len(self.plotdata[i * 8 + datai]) - self.period_display - 1:-1],
                                     color=cnames[i * 8 + datai])
                        else:
                            plt.plot(self.plottimer, self.plotdata[i * 8 + datai], color=cnames[i * 8 + datai])
                except TypeError:
                    print('[ERROR] Plot error!')
            plt.pause(0.001)
        except IndexError:
            print("\n[ERROR] Com error.\n")

    def __flag_plot_True(self):
        self.flag_plot = True

    def __auto_saving(self):
        """
        close and reopen, to save csv file regularly
        """
        self.csvfile.close()
        self.csvfile = open('{}/{}'.format(self.savedir, self.csvfilename), 'a', newline='')
        self.csvwriter = csv.writer(self.csvfile)
        # Thread(target=shutil.copy, args=[self.savedir+'/'+self.csvfilename, self.savedir+'/'+self.csvfilename+'.{}.bkp'.
        #        format(datetime.datetime.strftime(datetime.datetime.now(),'%Y-%m-%d_%H-%M-%S'))]).start()

    # def __hotkey_esc(self):
    #     """
    #     热键函数，按键弹窗，不会阻塞主进程
    #     """
    #     top = tkinter.Tk()
    #     top.geometry('0x0+999999+0')
    #     res = tkinter.messagebox.askyesno("提示", "要执行此操作？")
    #     top.destroy()
    #     if res is True:
    #         self.csvfile.close()
    #         self.stop_receive()
    #         # sys.exit()  # 只能退出tk进程，无法退出主进程

    def __hotkey_save(self):
        try:
            self.csvwriter.writerow([datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d_%H:%M:%S')] + self.savebuf)
            print(f"\n[INFO] One data saved at {datetime.datetime.strftime(datetime.datetime.now(), '%H:%M:%S')}\nU1:{self.savebuf[:3]} U16:{self.savebuf[-3:]}\n")
        except ValueError:
            if self.runflag:
                print("\n[ERROR] CSV file save error\n")

    def __hotkey_quit(self):
        self.csvfile.close()
        self.stop_receive()


if __name__ == '__main__':
    print("\n====================================================================")
    print("\nNo Chinese in the directory of this program!")
    print("\n====================================================================\n\n")
    ui = CMDUI()
    ui.run()
