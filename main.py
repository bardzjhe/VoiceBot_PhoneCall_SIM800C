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
from google.cloud import speech

from six.moves import queue

# Audio recording parameters
RATE = 16000
CHUNK = int(RATE/10) # 100ms

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'ServiceAccount.json'
client = texttospeech.TextToSpeechClient()
speech_client = speech.SpeechClient()

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

def speech2text():
    ## Step 1. Loadd the media files (Transcribe media files)
    primary_language = "yue-Hant-HK"  # a BCP-47 language tag
    secondary_language1 = "en-US"
    secondary_language2 = "zh"
    media_file_name_wav = 'temp_audio.wav'
    with open(media_file_name_wav, 'rb') as f2:
        byte_data_wav = f2.read()
    audio_wav = speech.RecognitionAudio(content=byte_data_wav)

    ## Step 2. Configure Media Files Output
    config_wav = speech.RecognitionConfig(
        sample_rate_hertz=44100,
        enable_automatic_punctuation=True,
        language_code='en_us',
        alternative_language_codes=[secondary_language1, secondary_language2],
        audio_channel_count=2
    )
      
    ## Step 3. Transcribing the Recognition objects
    response_standard_wav = speech_client.recognize(
        config=config_wav,
        audio=audio_wav
    )
    print (response_standard_wav)

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

    print("Debug info\nA works")
    print("The port number is: " + str(len(port_list)))
    if len(port_list) == 0:
        print("\nno port can be used")
        exit(0)
    else:
        print('\nB works')
# print all available port name
#         for i in port_list:
#             print(i)

    # find the correct port for data transmission
        for i in port_list:
            if str(i).find('CH340') != -1:
                s = serial.Serial(i.device, 115200, timeout=0)
        #s = serial.Serial(port_list[0].device, 115200, timeout=0.5)
        print('\nC works')
        sio = io.TextIOWrapper(io.BufferedRWPair(s, s))

        print("\nD works")
        sio.write(f'ATE1\nAT+COLP=1\nATD{str(phonenum)};\n')
        ''' 
        ATE1: 用於設置開啓回顯模式，檢測Module與串口是否連通，能否接收AT命令
        開啓回顯，有利於調試
        
        AT+COLP=1: 開啓被叫號碼顯示，即成功撥通的時候（被叫接聼電話），模塊會
        返回被叫號碼      
        
        ATD電話號碼;:用於撥打電話號碼
        '''

        sio.flush()
        print("\nE works")
        print("Calling....")
        while 1:
            # print(sio.readlines()) it leads to a big problem
            x = "".join(sio.readlines())

            # Detect status 
            # print(x)

            # Dailed
            if x.find('+COLP: \"') != -1:
                print("\ndialed")

                # Start audio recording
                audio_thread = AudiRecorder()
                executor.submit(audio_thread.start(), )

                # Text to speech
                text = "Hello. This is Jack. Long Time No See. How is everything going these days. This calling is from Google Cloud Platform using Artificial Intelligence. I wanna ask if Polyu has any room for improvement, please reply and I will record your audio. When you finish your comment, please ring off directly. "

                text2speech(text);
                pl = PlayMP3('audio file1.mp3')
                executor.submit(pl.play())


            if x.find('NO CARRIER') != -1:
                print("\nRing off")
                # Stop audio recording after the end of the call
                executor.submit(audio_thread.stop)
                break

            if (x.find('BUSY') != -1) | (x.find('ERROR') != -1) | (x.find('NO ANSWER') != -1): 
                print("\nHe/She hangs up")
                break

def main():

    calling()

    speech2text()
    print("Done")
    exit()


if __name__ == "__main__":
    main()
