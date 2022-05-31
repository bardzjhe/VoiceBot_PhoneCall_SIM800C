# Updated version with advanced NLP features, including t2s, s2t
from __future__ import division
import io
import os
import re
import sys
import time
import wave
import queue
import serial
import pyaudio
import threading
import serial.tools.list_ports
from pygame import mixer
from concurrent.futures import ThreadPoolExecutor
from google.cloud import texttospeech

from six.moves import queue

# Audio recording parameters
RATE = 16000
CHUNK = int(RATE/10) # 100ms

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'demoServiceAccount.json'
client = texttospeech.TextToSpeechClient()

def text2speech(text):

    synthesis_input = texttospeech.SynthesisInput(text=text)

    voice1 = texttospeech.VoiceSelectionParams(
        language_code='en-in', 
        ssml_gender=texttospeech.SsmlVoiceGender.MALE
    )

    # print(client.list_voices())

    audio_config = texttospeech.AudioConfig(
        audio_encoding= texttospeech.AudioEncoding.MP3
    )

    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice1,
        audio_config=audio_config
    )

    with open('audio file1.mp3', 'wb') as output:
        output.write(response.audio_content)

class PlayMP3():

    # Constructor to assign the fileName, which is the mp3 file to play
    def __init__(self, name):
        self._filename = name

    def play(self):
        mixer.init()
        mixer.music.load(self._filename)
        # print("* recording")
        mixer.music.play()
        print("The mp3 should be played")
        while mixer.music.get_busy():  # wait for music to finish playing
            time.sleep(1)
        mixer.music.stop()


class AudiRecorder():  # Audio class based on pyAudio and Wave

    # constructor
    def __init__(self):
        self.open = True
        self.rate = 44100
        self.frames_per_buffer = 1024
        self.channels = 2
        self.format = pyaudio.paInt16
        self.audio_filename = "temp_audio.wav"  # Recording file name
        self.audio = pyaudio.PyAudio()
        self.stream = self.audio.open(format=self.format,
                                      channels=self.channels,
                                      rate=self.rate,
                                      input=True,
                                      frames_per_buffer=self.frames_per_buffer)
        self.audio_frames = []
        # Audio starts being recorded

    def record(self):

        self.stream.start_stream()
        while (self.open == True):
            data = self.stream.read(self.frames_per_buffer)
            self.audio_frames.append(data)
            if self.open == False:
                break

    # Finishes the audio recording therefore the thread too
    def stop(self):

        if self.open == True:
            self.open = False
            self.stream.stop_stream()
            self.stream.close()
            self.audio.terminate()

            waveFile = wave.open(self.audio_filename, 'wb')
            waveFile.setnchannels(self.channels)
            waveFile.setsampwidth(self.audio.get_sample_size(self.format))
            waveFile.setframerate(self.rate)
            waveFile.writeframes(b''.join(self.audio_frames))
            waveFile.close()
        pass

    # Launches the audio recording function using a thread
    def start(self):
        audio_thread = threading.Thread(target=self.record)
        print("The recording should start")
        audio_thread.start()


def calling(phonenum):
    executor = ThreadPoolExecutor(max_workers=16)
    port_list = list(serial.tools.list_ports.comports())
    print("A works")
    print(len(port_list))
    if len(port_list) == 0:
        print("nothing to be used")

    else:
        print('D')
# print all available port name
#         for i in port_list:
#             print(i)

    # find the correct port for data transmission
        for i in port_list:
            if str(i).find('CH340') != -1:
                s = serial.Serial(i.device, 115200, timeout=0.5)
        #s = serial.Serial(port_list[0].device, 115200, timeout=0.5)
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
        print("G works")
        while 1:
            # print(sio.readlines()) it leads to a big problem
            x = "".join(sio.readlines())
            print(x)
            if x.find('+COLP: \"') != -1:
                print("dialed")
                # Start audio recording
                audio_thread = AudiRecorder()
                executor.submit(audio_thread.start(), )

                # Text to speech
                text = "What's the matter with you. I'm gonna fly to LA next month. Do you think I have to go if I haven been to Hong Kong before, it is ridiculous!"
                text2speech(text);
                pl = PlayMP3('audio file1.mp3')
                executor.submit(pl.play())


            if x.find('NO CARRIER') != -1:
                print("Ring off")
                # Stop audio recording after the end of the call
                executor.submit(audio_thread.stop)
                break

#           if x == '\nNO CARRIER\n':  # Dial failed


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


# Required and wanted processing of final files
def file_manager(filename):
    local_path = os.getcwd()

    if os.path.exists(str(local_path) + "/temp_audio.wav"):
        os.remove(str(local_path) + "/temp_audio.wav")


def main():

    calling(56117107)


    print("Done")
    exit()


if __name__ == "__main__":
    main()