import io
import re 
import time 
import serial 
import serial.tools.list_ports
import pyaudio
import threading
from multiprocessing import Process
from concurrent.futures import ThreadPoolExecutor
Flag=True
import wave

def recording(wave_out_path):
    CHUNK = 1024
    WIDTH = 2
    CHANNELS = 2
    RATE = 44100
    # RECORD_SECONDS = 5

    p = pyaudio.PyAudio()

    stream = p.open(format=p.get_format_from_width(WIDTH),
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    output=True,
                    input_device_index=1,
                    frames_per_buffer=CHUNK)

    wf = wave.open(wave_out_path, 'wb')
    wf.setnchannels(CHANNELS)

    wf.setframerate(RATE)  # 采样频率设置

    print("* recording")

    while Flag:

        data = stream.read(CHUNK)  #read audio stream
        stream.write(data, CHUNK)  #play back audio stream

    stream.stop_stream()
    stream.close()
    p.terminate()

class AudiRecorder(): # Audio class based on pyAudio and Wave

    # constructor
    def __init__(self):
        self.open = True
        self.rate = 44100
        self.frames_per_buffer = 1024
        self.channels = 2
        self.format = pyaudio.paInt16
        self.audio_filename = "temp_audio.wav"
        self.audio = pyaudio.PyAudio()
        self.stream = self.audio.open(format=self.format,
                                      channels=self.channels,
                                      rate=self.rate,
                                      input=True,
                                      frames_per_buffer = self.frames_per_buffer)
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
        audio_thread.start()

def calling(phonenum):
    port_list=list(serial.tools.list_ports.comports())
    print("A works")

    print(len(port_list))
    if(len(port_list)==0):
        print("nothing to be used")
    else:
        print('D')
        s=serial.Serial(port_list[0].device, timeout=1)
        print('E')
        sio=io.TextIOWrapper(io.BufferedRWPair(s,s))
        print("B works")
        sio.write(f'ATE1\nAT+COLP=1\nATD{str(phonenum)};\n')
        sio.flush()
        print("C works")
        while 1:
         x=''.join(sio.readlines())
         if(x=='\nNO CARRIER\n'):
             Flag=False
             break


def str2unicdoe(rawstr):
    result=''
    for c in rawstr:
        _hex=hex(ord(c))
        if len(_hex) == 4:
            _hex=_hex.replace('0x','00')
        else:
            _hex=_hex.replace('0x','')
        result+=_hex.upper()
    return result


def textmessage(rawtext,rawphonenum):
    send_test=str2unicdoe(rawtext)
    phonenum=str2unicdoe(rawphonenum)
    port_list=list(serial.tools.list_ports.comports())
    if(len(port_list)==0):
        print("nothing to be used")
    else:
        s=serial.Serial(port_list[0].device, timeout=1)
        sio=io.TextIOWrapper(io.BufferedRWPair(s,s))
        sio.write(f'AT+CMGF=1\nAT+CSMP=17, 167, 2, 25\nAT+CSCS="UCS2"\nAT+CMGS="{phonenum}"\n')
        sio.flush()
        print(''.join(sio.readlines()))
        time.sleep(1)
        sio.write(send_test+'\n')
        sio.flush()
        print(''.join(sio.readlines()))
        s.write(b'\x1a')
        sio.flush()
        print(''.join(sio.readlines()))
        s.close()


 
executor = ThreadPoolExecutor(max_workers=16)
executor.submit(calling, 94030591)
time.sleep(5)
record = AudiRecorder()
record.start()