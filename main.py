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
import multiprocessing
import serial.tools.list_ports
from pygame import mixer
from concurrent.futures import ThreadPoolExecutor
from google.cloud import texttospeech
from google.cloud import speech
from six.moves import queue
from datetime import datetime
from configurator import getConfig

import requests

# Audio recording parameters
STREAMING_LIMIT = 240000  # 4 minutes
SAMPLE_RATE = 8000
CHUNK_SIZE = int(SAMPLE_RATE / 10)  # 100ms

settingFilePath = "SETTING.txt"
setting = getConfig(settingFilePath)

executor = ThreadPoolExecutor(max_workers=16)
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = setting["googleApplicationCredentials"]
config_serialDeviceName = setting["serialDeviceName"]
phonenum = ''
client = texttospeech.TextToSpeechClient()
speech_client = speech.SpeechClient()
audio_temp_folder = 'audio_temp/'


RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"


def get_current_time():
    """Return Current Time in MS."""

    return int(round(time.time() * 1000))

class ResumableMicrophoneStream:
    """Opens a recording stream as a generator yielding the audio chunks."""

    def __init__(self, rate, chunk_size):
        self._rate = rate
        self.chunk_size = chunk_size
        self._num_channels = 1
        self._buff = queue.Queue()
        self.closed = True
        self.start_time = get_current_time()
        self.restart_counter = 0
        self.audio_input = []
        self.last_audio_input = []
        self.result_end_time = 0
        self.is_final_end_time = 0
        self.final_request_end_time = 0
        self.bridging_offset = 0
        self.last_transcript_was_final = False
        self.new_stream = True
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            channels=self._num_channels,
            rate=self._rate,
            input=True,
            frames_per_buffer=self.chunk_size,
            # Run the audio stream asynchronously to fill the buffer object.
            # This is necessary so that the input device's buffer doesn't
            # overflow while the calling thread makes network requests, etc.
            stream_callback=self._fill_buffer,
        )

    def __enter__(self):

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

    def _fill_buffer(self, in_data, *args, **kwargs):
        """Continuously collect data from the audio stream, into the buffer."""

        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        """Stream Audio from microphone to API and to local buffer"""

        while not self.closed:
            data = []

            if self.new_stream and self.last_audio_input:

                chunk_time = STREAMING_LIMIT / len(self.last_audio_input)

                if chunk_time != 0:

                    if self.bridging_offset < 0:
                        self.bridging_offset = 0

                    if self.bridging_offset > self.final_request_end_time:
                        self.bridging_offset = self.final_request_end_time

                    chunks_from_ms = round(
                        (self.final_request_end_time - self.bridging_offset)
                        / chunk_time
                    )

                    self.bridging_offset = round(
                        (len(self.last_audio_input) - chunks_from_ms) * chunk_time
                    )

                    for i in range(chunks_from_ms, len(self.last_audio_input)):
                        data.append(self.last_audio_input[i])

                self.new_stream = False

            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            chunk = self._buff.get()
            self.audio_input.append(chunk)

            if chunk is None:
                return
            data.append(chunk)
            # Now consume whatever other data's still buffered.
            while True:
                try:
                    chunk = self._buff.get(block=False)

                    if chunk is None:
                        return
                    data.append(chunk)
                    self.audio_input.append(chunk)

                except queue.Empty:
                    break

            yield b"".join(data)

def AI_Enquiry(transcript, language_code, phonenum):
    # get result from kimia AI 
    # 使用 GET 方式下載普通網頁
    
    requestURL = 'https://kimia.toyokoexpress.com/chat/?text='+ transcript +'&kiosk_type=17&session=' + str(phonenum)
    print(f"Request: {requestURL}")
    r = requests.get(requestURL)

    # 檢查狀態碼是否 OK
    if r.status_code == requests.codes.ok:
        print("Response received!")

    # 輸出網頁 HTML 原始碼
    print("-----------Kimia AI Response-----------")
    print(r.text)
    print("---------------------------------------")
    
    if r.text != "":
        return r.text
    else:
        if language_code == "en-us" or language_code == "en-uk":
            return "Sorry, I don't understand your question."
        elif language_code == "zh" or language_code == "cmn-hans-cn" or language_code == "zh-TW":
            return "對不起，我不明白你的問題。"
        else:
            return "對唔住，我唔知你講咩。"

def listen_print_loop(responses, stream, phonenum):
    """Iterates through server responses and prints them.

    The responses passed is a generator that will block until a response
    is provided by the server.

    Each response may contain multiple results, and each result may contain
    multiple alternatives; for details, see https://goo.gl/tjCPAU.  Here we
    print only the transcription for the top alternative of the top result.

    In this case, responses are provided for interim results as well. If the
    response is an interim one, print a line feed at the end of it, to allow
    the next result to overwrite it, until the response is a final one. For the
    final one, print a newline to preserve the finalized transcription.
    """

    for response in responses:
        if get_current_time() - stream.start_time > STREAMING_LIMIT:
            stream.start_time = get_current_time()
            break

        if not response.results:
            continue

        result = response.results[0]

        if not result.alternatives:
            continue
        
        transcript = result.alternatives[0].transcript

        result_seconds = 0
        result_micros = 0

        if result.result_end_time.seconds:
            result_seconds = result.result_end_time.seconds

        if result.result_end_time.microseconds:
            result_micros = result.result_end_time.microseconds

        stream.result_end_time = int((result_seconds * 1000) + (result_micros / 1000))

        corrected_time = (
            stream.result_end_time
            - stream.bridging_offset
            + (STREAMING_LIMIT * stream.restart_counter)
        )
        # Display interim results, but with a carriage return at the end of the
        # line, so subsequent lines will overwrite them.

        if result.is_final:
            sys.stdout.write(GREEN)
            sys.stdout.write("\033[K")
            sys.stdout.write(str(corrected_time) + ": " + transcript + "\n")
            string = AI_Enquiry(transcript, result.language_code, phonenum)
            text2speech(string, result.language_code)

            if result.language_code == "en-us" or result.language_code == "en-uk":
                print("Reply: What can I help you?")
                text2speech("What can I help you?", result.language_code)
            elif result.language_code == "zh" or result.language_code == "cmn-hans-cn" or result.language_code == "zh-TW":
                print("Reply: 請問還有什麼可以幫到你?")
                text2speech("請問還有什麼可以幫你?", result.language_code)
            else:
                print("Reply: 請問重有咩可以幫你?")
                text2speech("請問重有咩可以幫你?", result.language_code)

            stream.is_final_end_time = stream.result_end_time
            stream.last_transcript_was_final = True

            # Exit recognition if any of the transcribed phrases could be
            # one of our keywords.
            # if re.search(r"\b(exit|quit)\b", transcript, re.I):
            #     sys.stdout.write(YELLOW)
            #     sys.stdout.write("Exiting...\n")
            #     stream.closed = True
            #     break

            # temporary test funciton
            stream.closed = True
            break

        else:
            sys.stdout.write(RED)
            sys.stdout.write("\033[K")
            sys.stdout.write(str(corrected_time) + ": " + transcript + "\r")

            stream.last_transcript_was_final = False

def speech2text(phonenum):
    primary_language = "yue-Hant-HK"  # a BCP-47 language tag
    secondary_language1 = "en-US"
    secondary_language2 = "zh"
    """start bidirectional streaming from microphone input to speech API"""

    client = speech.SpeechClient()
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=SAMPLE_RATE,
        speech_contexts=[speech.SpeechContext(phrases=["$ORDINAL"])],
        language_code=primary_language,
        # alternative_language_codes=[secondary_language1, secondary_language2],
        max_alternatives=1,
    )

    streaming_config = speech.StreamingRecognitionConfig(
        config=config, interim_results=True
    )

    text2speech("您好, 我係人工智能服務大使Kimia, 請問有咩可以幫到您呢?", "yue-Hant-HK")
    
    while True:
        mic_manager = ResumableMicrophoneStream(SAMPLE_RATE, CHUNK_SIZE)
        print(mic_manager.chunk_size)
        sys.stdout.write(YELLOW)
        sys.stdout.write('\nListening....\n\n')
        sys.stdout.write("End (ms)       Transcript Results/Status\n")
        sys.stdout.write("=====================================================\n")

        with mic_manager as stream:

            while not stream.closed:
                sys.stdout.write(YELLOW)
                sys.stdout.write(
                    "\n" + str(STREAMING_LIMIT * stream.restart_counter) + ": NEW REQUEST\n"
                )

                stream.audio_input = []
                audio_generator = stream.generator()

                requests = (
                    speech.StreamingRecognizeRequest(audio_content=content)
                    for content in audio_generator
                )

                responses = client.streaming_recognize(streaming_config, requests)

                # Now, put the transcription responses to use.
                listen_print_loop(responses, stream, phonenum)

                if stream.result_end_time > 0:
                    stream.final_request_end_time = stream.is_final_end_time
                stream.result_end_time = 0
                stream.last_audio_input = []
                stream.last_audio_input = stream.audio_input
                stream.audio_input = []
                stream.restart_counter = stream.restart_counter + 1

                if not stream.last_transcript_was_final:
                    sys.stdout.write("\n")
                stream.new_stream = True

def text2speech(text, language_code):
    synthesis_input = texttospeech.SynthesisInput(text=text)

    voice1 = texttospeech.VoiceSelectionParams(
        language_code=language_code, 
        ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
    )

    audio_config = texttospeech.AudioConfig(
        audio_encoding= texttospeech.AudioEncoding.MP3
    )

    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice1,
        audio_config=audio_config
    )

    isExist = os.path.exists(audio_temp_folder)
    if not isExist:
        # Create a new directory because it does not exist 
        os.makedirs(audio_temp_folder)
        print("The new directory is created!")

    date_string = datetime.now().strftime("%d%m%Y%H%M%S")
    # write response to the audio file
    with open(audio_temp_folder+'result_'+date_string+'.mp3', 'wb') as output:
        output.write(response.audio_content)

    # Play the audio file to let the user hear the sound
    pl = PlayMP3(audio_temp_folder+'result_'+date_string+'.mp3')
    pl.play()

# Play mp3 files, which is converted from the text using GCP API. 
class PlayMP3():
    # Constructor to assign the fileName, which is the mp3 file to play
    def __init__(self, name):
        self._filename = name

    def play(self):
        # mixer.init(devicename = 'Line 1 (Virtual Audio Cable)')
        mixer.init()
        mixer.music.load(self._filename)
        mixer.music.play()
        print("The mp3 should be played")
        while mixer.music.get_busy():  # wait for music to finish playing
            time.sleep(1)
        mixer.music.stop()
        mixer.quit()

        # delete all files inside folder audio_temp
        for f in os.listdir(audio_temp_folder):
            os.remove(os.path.join(audio_temp_folder, f))

def run_sim800c():
    global phonenum
    language_code = "yue-Hant-HK"
    port_list = list(serial.tools.list_ports.comports())
    dialed = False

    print("The port number is: " + str(len(port_list)))
    if len(port_list) == 0:
        print("\nno port can be used :(")
        exit(0)
    else:
        # find the correct port for data transmission
        for i in port_list:
            if str(i).find(config_serialDeviceName) != -1:
                s = serial.Serial(i.device, 115200, timeout=0)

        sio = io.TextIOWrapper(io.BufferedRWPair(s, s))

        sio.write(f'AT+DDET=1\nATS0=2\nATE1\nAT+COLP=1\nAT+CLIP=1\n')
        ''' 
        AT+DDET=1: enable DTMF detection

        ATS0=2: Set Number of Rings before Automatically Answering the Call

        ATE1: 用於設置開啓回顯模式，檢測Module與串口是否連通，能否接收AT命令
        開啓回顯，有利於調試
        
        AT+COLP=1: 開啓被叫號碼顯示，即成功撥通的時候（被叫接聼電話），模塊會
        返回被叫號碼      
        
        ATD電話號碼;:用於撥打電話號碼
        '''

        sio.flush()

        print("Waiting for call (If it cannot work for long, please use XCOM V2.0 to check)....")
        while 1:
            # print(sio.readlines()) it leads to a big problem
            try:
                x = "".join(sio.readlines())
            except Exception:
                print("\nError occurs accidentally, check the port or other devices :(")
                exit()

            # Dailed
            if x.find('+COLP: \"') != -1:
                print("\ndialed")
                executor.submit(speech2text, phonenum)

            if x.find('+DTMF: 1') != -1:
                string = AI_Enquiry("1號", language_code, phonenum)
                executor.submit(text2speech, string, "yue-Hant-HK")
            elif x.find('+DTMF: 2') != -1:
                string = AI_Enquiry("2號", language_code, phonenum)
                executor.submit(text2speech, string, "yue-Hant-HK")
            elif x.find('+DTMF: 3') != -1:
                string = AI_Enquiry("3號", language_code, phonenum)
                executor.submit(text2speech, string, "yue-Hant-HK")
            elif x.find('+DTMF: 4') != -1:
                string = AI_Enquiry("4號", language_code, phonenum)
                executor.submit(text2speech, string, "yue-Hant-HK")
            elif x.find('+DTMF: 5') != -1:
                string = AI_Enquiry("5號", language_code, phonenum)
                executor.submit(text2speech, string, "yue-Hant-HK")
            elif x.find('+DTMF: 6') != -1:
                string = AI_Enquiry("6號", language_code, phonenum)
                executor.submit(text2speech, string, "yue-Hant-HK")
            elif x.find('+DTMF: 7') != -1:
                string = AI_Enquiry("7號", language_code, phonenum)
                executor.submit(text2speech, string, "yue-Hant-HK")
            elif x.find('+DTMF: 8') != -1:
                string = AI_Enquiry("8號", language_code, phonenum)
                executor.submit(text2speech, string, "yue-Hant-HK")
            elif x.find('+DTMF: 9') != -1:
                string = AI_Enquiry("9號", language_code, phonenum)
                executor.submit(text2speech, string, "yue-Hant-HK")
            elif x.find('+DTMF: 0') != -1:
                string = AI_Enquiry("0號", language_code, phonenum)
                executor.submit(text2speech, string, "yue-Hant-HK")
            elif x.find('+DTMF: #') != -1:
                string = AI_Enquiry("你好", language_code, phonenum)
                executor.submit(text2speech, string, "yue-Hant-HK")
            elif x.find('+DTMF: *') != -1:
                print("\nDTMF:*")

            if x.find('NO CARRIER') != -1:
                print("\nRing off")
                dialed = False
                process.terminate() # terminate the running process
                print("Process terminated!")

            if (x.find('BUSY') != -1) | (x.find('NO ANSWER') != -1):
                print("\nHe/She hangs up")
                break

            if (x.find('ERROR') != -1): 
                print("\nErrors occurr in SIM card (it's not China Mobile card or it arrears), \nor in other devices, \nor Card installation error")
                break

            if dialed == False:
                if (x.find('+CLIP: "') != -1):
                    phonenum = int(x[x.find('+CLIP: "')+8:x.find('+CLIP: "')+16])
                    print(str(phonenum) + " called in")
                    sio.write('ATA\n') # accept call
                    time.sleep(10)
                    dialed = True
                    print("\ndialed")
                    process = multiprocessing.Process(target=speech2text, args=(phonenum,)) # create a new process to handle phone call
                    process.start() # start process
                    # executor.submit(speech2text, phonenum)

def main():
    print("   _____ _____ __  __  ___   ___   ___   _____   ____   ____ _______ ")
    print("  / ____|_   _|  \/  |/ _ \ / _ \ / _ \ / ____| |  _ \ / __ \__   __|")
    print(" | (___   | | | \  / | (_) | | | | | | | |      | |_) | |  | | | |   ")
    print("  \___ \  | | | |\/| |> _ <| | | | | | | |      |  _ <| |  | | | |   ")
    print("  ____) |_| |_| |  | | (_) | |_| | |_| | |____  | |_) | |__| | | |   ")
    print(" |_____/|_____|_|  |_|\___/ \___/ \___/ \_____| |____/ \____/  |_|     Ver0.2 beta")
    print("")

    run_sim800c()

    print("Done")
    os._exit(1)


if __name__ == "__main__":
    main()
