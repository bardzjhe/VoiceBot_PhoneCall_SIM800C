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

# 引入 requests 模組
import requests

# Audio recording parameters
RATE = 16000
CHUNK = int(RATE/10) # 100ms

executor = ThreadPoolExecutor(max_workers=16)
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'ambient-sum-352109-87d42557e70d.json' # plz modify the name if needed
client = texttospeech.TextToSpeechClient()
speech_client = speech.SpeechClient()


class MicrophoneStream(object):
    """Opens a recording stream as a generator yielding the audio chunks."""

    def __init__(self, rate, chunk):
        self._rate = rate
        self._chunk = chunk

        # Create a thread-safe buffer of audio data
        self._buff = queue.Queue()
        self.closed = True

    def __enter__(self):
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            # The API currently only supports 1-channel (mono) audio
            # https://goo.gl/z757pE
            channels=1,
            rate=self._rate,
            input=True,
            frames_per_buffer=self._chunk,
            # Run the audio stream asynchronously to fill the buffer object.
            # This is necessary so that the input device's buffer doesn't
            # overflow while the calling thread makes network requests, etc.
            stream_callback=self._fill_buffer,
        )

        self.closed = False

        return self

    def __exit__(self, type, value, traceback):
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        # Signal the generator to terminate so that the client's
        # streaming_recognize method will not block the process termination.
        self._buff.put(None)
        self._audio_interface.terminate()

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        """Continuously collect data from the audio stream, into the buffer."""
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        while not self.closed:
            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]

            # Now consume whatever other data's still buffered.
            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            yield b"".join(data)


def listen_print_save_loop(responses, stream, phonenum):
    """Iterates through server responses, then prints and saves them.

    The responses passed is a generator that will block until a response
    is provided by the server.

    Each response may contain multiple results, and each result may contain
    multiple alternatives; for details, see https://goo.gl/tjCPAU.  Here we
    print/save only the transcription for the top alternative of the top result.
    
    In this case, responses are provided for interim results as well. If the
    response is an interim one, print a line feed at the end of it, to allow
    the next result to overwrite it, until the response is a final one. For the
    final one, print a newline to preserve the finalized transcription.
    """
    num_chars_printed = 0
    for response in responses:
        if not response.results:
            continue

        # The `results` list is consecutive. For streaming, we only care about
        # the first result being considered, since once it's `is_final`, it
        # moves on to considering the next utterance.
        result = response.results[0]
        if not result.alternatives:
            continue

        # Display the transcription of the top alternative.
        transcript = result.alternatives[0].transcript

        # Display interim results, but with a carriage return at the end of the
        # line, so subsequent lines will overwrite them.
        #
        # If the previous result was longer than this one, we need to print
        # some extra spaces to overwrite the previous result
        stream.closed = True  # off mic

        # get result from kimia AI 
        # 使用 GET 方式下載普通網頁
        requestURL = 'https://kimia.toyokoexpress.com/chat/?text='+ transcript +'&kiosk_type=17&session=' + str(phonenum)
        print(f"Request: {requestURL}")
        r = requests.get(requestURL)

        # 檢查狀態碼是否 OK
        if r.status_code == requests.codes.ok:
            print("OK")

        # 輸出網頁 HTML 原始碼
        print(r.text)

        executor.submit(text2speech, str(r.text))


        overwrite_chars = " " * (num_chars_printed - len(transcript))

        if not result.is_final:
            sys.stdout.write(transcript + overwrite_chars + "\r")
            sys.stdout.flush()
            num_chars_printed = len(transcript)

        else:
            print(f"Transcript: {transcript + overwrite_chars}")
            print(f"Confidence: {result.alternatives[0].confidence:.0%}")

            # Exit recognition if any of the transcribed phrases could be
            # one of our keywords.
            if re.search(r"\b(exit|quit)\b", transcript, re.I):
                print("Exiting..")
                break

            num_chars_printed = 0


def speech2text(phonenum):
    # See http://g.co/cloud/speech/docs/languages
    # for a list of supported languages.
    primary_language = "yue-Hant-HK"  # a BCP-47 language tag
    secondary_language1 = "en-US"
    secondary_language2 = "zh"

    client = speech.SpeechClient()
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code=primary_language,
        alternative_language_codes=[secondary_language1, secondary_language2]
    )

    streaming_config = speech.StreamingRecognitionConfig(
        config=config, interim_results=False, single_utterance=True
    )

    while True:
        try:
            with MicrophoneStream(RATE, CHUNK) as stream:
                audio_generator = stream.generator()
                requests = (
                    speech.StreamingRecognizeRequest(audio_content=content)
                    for content in audio_generator
                )
                
                responses = client.streaming_recognize(streaming_config, requests, timeout = 5)
                print(responses)
                # Now, put the transcription responses to use.
                listen_print_save_loop(responses, stream, phonenum)
        except:
            continue


def text2speech(text):

    synthesis_input = texttospeech.SynthesisInput(text=text)

    voice1 = texttospeech.VoiceSelectionParams(
        language_code='yue-Hant-HK', 
        ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
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

    with open('result.mp3', 'wb') as output:
        output.write(response.audio_content)

    # Play the audio file to let the user hear the sound
    pl = PlayMP3('result.mp3')
    pl.play()

# Play mp3 files, which is converted from the text using GCP API. 
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

def calling(phonenum):
    port_list = list(serial.tools.list_ports.comports())

    print("Debug info\nA works")
    print("The port number is: " + str(len(port_list)))
    if len(port_list) == 0:
        print("\nno port can be used :(")
        exit(0)
    else:
        print('\nB works')
# print all available port name
#         for i in port_list:
#             print(i)

    # find the correct port for data transmission
        for i in port_list:
            if str(i).find('usbserial-110') != -1: # plz modify the device name if needed
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
        print("Calling (If it cannot work for long, please use XCOM V2.0 to check)....")
        while 1:
            # print(sio.readlines()) it leads to a big problem
            try:
                x = "".join(sio.readlines())
            except Exception:
                print("\nError occurs accidentally, check the port or other devices :(")
                exit()

            # Detect status 
            # print(x)

            # Dailed
            if x.find('+COLP: \"') != -1:
                print("\ndialed")
                executor.submit(speech2text, phonenum)

            if x.find('NO CARRIER') != -1:
                print("\nRing off")
                # Stop audio recording after the end of the call
                # executor.submit(audio_thread.stop)
                break

            if (x.find('BUSY') != -1) | (x.find('NO ANSWER') != -1):
                print("\nHe/She hangs up")
                break

            if (x.find('ERROR') != -1): 
                print("\nErrors occurr in SIM card (it's not China Mobile card or it arrears), \nor in other devices, \nor Card installation error")
                break

def main():
    calling(51153639) # Fill your telephone number
    
    # test = True
    # while 1:
    #     if test == True:
    #         executor.submit(speech2text, 51153639)
    #         test = False
    
    # print("test t2s API:")
    # text2speech(text)

    # print('\ntest s2t API:')
    # speech2text()

    print("Done")
    os._exit(1)


if __name__ == "__main__":
    main()
