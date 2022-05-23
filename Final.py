import io
import re
import sys
import time
import serial
import argparse
import serial.tools.list_ports
import pyaudio
from pygame import mixer
from multiprocessing import Process
from concurrent.futures import ThreadPoolExecutor
import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav


import sounddevice as sd
from scipy.io.wavfile import write
import wavio as wv

Flag = True
Connected = False

def int_or_str(text):
    """Helper function for argument parsing."""
    try:
        return int(text)
    except ValueError:
        return text

def mic_function():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        '-l', '--list-devices', action='store_true',
        help='show list of audio devices and exit')
    args, remaining = parser.parse_known_args()
    if args.list_devices:
        print(sd.query_devices())
        parser.exit(0)
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[parser])
    parser.add_argument(
        '-i', '--input-device', type=int_or_str,
        help='input device (numeric ID or substring)')
    parser.add_argument(
        '-o', '--output-device', type=int_or_str,
        help='output device (numeric ID or substring)')
    parser.add_argument(
        '-c', '--channels', type=int, default=2,
        help='number of channels')
    parser.add_argument('--dtype', help='audio data type')
    parser.add_argument('--samplerate', type=float, help='sampling rate')
    parser.add_argument('--blocksize', type=int, help='block size')
    parser.add_argument('--latency', type=float, help='latency in seconds')
    args = parser.parse_args(remaining)

    def callback(indata, outdata, frames, time, status):
        if status:
            print(status)
        outdata[:] = indata

    try:
        with sd.Stream(device=(args.input_device, args.output_device),
                       samplerate=args.samplerate, blocksize=args.blocksize,
                       dtype=args.dtype, latency=args.latency,
                       channels=args.channels, callback=callback):
            print('#' * 80)
            print("* recording")
            print('press Return to quit')
            print('#' * 80)
            input()

    except KeyboardInterrupt:
        parser.exit('')

    except Exception as e:
        parser.exit(type(e).__name__ + ': ' + str(e))

def mp3_function(filename):
    mixer.init()
    mixer.music.load(filename)
    #print("* recording")
    mixer.music.play()
    time.sleep(30)
    mixer.music.stop()


def inout():
    CHUNK = 1024
    WIDTH = 2
    CHANNELS = 2
    RATE = 44100
    RECORD_SECONDS = 5

    p = pyaudio.PyAudio()

    stream = p.open(format=p.get_format_from_width(WIDTH),
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    output=True,
                    input_device_index=1,
                    frames_per_buffer=CHUNK)

    print("* recording")

    while Flag:
        data = stream.read(CHUNK)  # read audio stream
        stream.write(data, CHUNK)  # play back audio stream

    stream.stop_stream()
    stream.close()
    p.terminate()


def calling(phonenum):
    port_list = list(serial.tools.list_ports.comports())
    print("A works")
    print(len(port_list))
    if (len(port_list) == 0):
        print("nothing to be used")

    else:
        print('D')
        s = serial.Serial(port_list[0].device, timeout=0)
        print('E')
        sio = io.TextIOWrapper(io.BufferedRWPair(s, s))
        print("B works")
        sio.write(f'ATE1\nAT+COLP=1\nATD{str(phonenum)};\n')
        ''' 
        ATE1: 用於設置開啓回顯模式，檢測Module與串口是否連通，能否接收AT命令
        開啓回顯，有利於調試
        
        AT+COLP=1: 開啓被叫號碼顯示，即成功撥通的時候（被叫接聼電話），模塊會
        返回被叫號碼      
        
        ATD電話號碼;:用於撥打電話號碼
        '''
        sio.flush()
        Connected = True
        while 1:
            x = ''.join(sio.readlines())

            if (x == '\nNO CARRIER\n' |
                    x == '\nNO ANSWER\n' |
                    x == '\nERROR\n'):  # Dial failed
                Flag = False
                break


def str2unicdoe(rawstr):
    result = ''
    for c in rawstr:
        _hex = hex(ord(c))
        if len(_hex) == 4:
            _hex = _hex.replace('0x', '00')
        else:
            _hex = _hex.replace('0x', '')
        result += _hex.upper()
    return result


def textmessage(rawtext, rawphonenum):
    send_test = str2unicdoe(rawtext)
    phonenum = str2unicdoe(rawphonenum)
    port_list = list(serial.tools.list_ports.comports())

    if (len(port_list) == 0):
        print("nothing to be used")

    else:
        s = serial.Serial(port_list[0].device, timeout=1)
        sio = io.TextIOWrapper(io.BufferedRWPair(s, s))
        sio.write(f'AT+CMGF=1\nAT+CSMP=17, 167, 2, 25\nAT+CSCS="UCS2"\nAT+CMGS="{phonenum}"\n')

        '''
        AT+CMGF=1:設置爲文本内容
        AT+CSMP=17, 167, 2, 25:設置文本參數
        AT+CSCS="UCS2":設置爲16位通用8直接倍數編碼字符集  
        '''

        sio.flush()
        print(''.join(sio.readlines()))
        time.sleep(1)
        sio.write(send_test + '\n')
        sio.flush()
        print(''.join(sio.readlines()))
        s.write(b'\x1a')
        sio.flush()
        print(''.join(sio.readlines()))
        s.close()

def main():
    executor = ThreadPoolExecutor(max_workers=16)

    # variable = int(input("enter 1 for mic function, enter 2 for mp3 functon:\n"))
    executor.submit(calling, 94030591)
    inout()
    if Connected:
        mp3_function("01.mp3")
    # inout()
    '''
    if variable == 1:
        mic_function()
    elif variable == 2:
        mp3_function("01.mp3")
    else:
        sys.exit(0)
    '''

if __name__ == "__main__":
    main()
