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

# Text as global variable
text = "Hello. This is Jack. Long Time No See. How is everything going these days.  I wanna ask do you have any comments on our service? please reply and I will record your audio. When you finish your comment, please ring off directly. "

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'ServiceAccount.json' # plz modify the name if needed
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


def listen_print_save_loop(responses):
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
        overwrite_chars = " " * (num_chars_printed - len(transcript))

        if not result.is_final:
            sys.stdout.write(transcript + overwrite_chars + "\r")
            sys.stdout.flush()

            num_chars_printed = len(transcript)

        else:
            print(transcript + overwrite_chars)

            # Exit recognition if any of the transcribed phrases could be
            # one of our keywords.
            if re.search(r"\b(exit|quit)\b", transcript, re.I):
                print("Exiting..")
                break

            num_chars_printed = 0


def speech2text():
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
        config=config, interim_results=True
    )

    with MicrophoneStream(RATE, CHUNK) as stream:
        audio_generator = stream.generator()
        requests = (
            speech.StreamingRecognizeRequest(audio_content=content)
            for content in audio_generator
        )

        responses = client.streaming_recognize(streaming_config, requests)

        # Now, put the transcription responses to use.
        listen_print_save_loop(responses)


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


# @Deprecated version: convert speech from wav file to text, not simultaneously. 
# def speech2text():
#     ## Step 1. Loadd the media files (Transcribe media files)
#     primary_language = "yue-Hant-HK"  # a BCP-47 language tag
#     secondary_language1 = "en-US"
#     secondary_language2 = "zh"
#     media_file_name_wav = 'temp_audio.wav'
#     with open(media_file_name_wav, 'rb') as f2:
#         byte_data_wav = f2.read()
#     audio_wav = speech.RecognitionAudio(content=byte_data_wav)

#     ## Step 2. Configure Media Files Output
#     config_wav = speech.RecognitionConfig(
#         sample_rate_hertz=44100,
#         enable_automatic_punctuation=True,
#         language_code='en_us',
#         alternative_language_codes=[secondary_language1, secondary_language2],
#         audio_channel_count=2
#     )
      
#     ## Step 3. Transcribing the Recognition objects
#     response_standard_wav = speech_client.recognize(
#         config=config_wav,
#         audio=audio_wav
#     )
#     print (response_standard_wav)


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


# Record Audio
# class AudiRecorder():  # Audio class based on pyAudio and Wave

#     # constructor
#     def __init__(self):
#         self.open = True
#         self.rate = 44100
#         self.frames_per_buffer = 1024
#         self.channels = 2
#         self.format = pyaudio.paInt16
#         self.audio_filename = "temp_audio.wav"  # Recording file name
#         self.audio = pyaudio.PyAudio()
#         self.stream = self.audio.open(format=self.format,
#                                       channels=self.channels,
#                                       rate=self.rate,
#                                       input=True,
#                                       frames_per_buffer=self.frames_per_buffer)
#         self.audio_frames = []
#         # Audio starts being recorded

#     def record(self):

#         self.stream.start_stream()
#         while (self.open == True):
#             data = self.stream.read(self.frames_per_buffer)
#             self.audio_frames.append(data)
#             if self.open == False:
#                 break

#     # Finishes the audio recording therefore the thread too
#     def stop(self):

#         if self.open == True:
#             self.open = False
#             self.stream.stop_stream()
#             self.stream.close()
#             self.audio.terminate()

#             waveFile = wave.open(self.audio_filename, 'wb')
#             waveFile.setnchannels(self.channels)
#             waveFile.setsampwidth(self.audio.get_sample_size(self.format))
#             waveFile.setframerate(self.rate)
#             waveFile.writeframes(b''.join(self.audio_frames))
#             waveFile.close()
#         pass

#     # Launches the audio recording function using a thread
#     def start(self):
#         audio_thread = threading.Thread(target=self.record)
#         print("The recording should start")
#         audio_thread.start()


def calling(phonenum):
    executor = ThreadPoolExecutor(max_workers=16)
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

                # @Deprecated save the user's voice into a file after he/she hangs up
                # Start audio recording
                # audio_thread = AudiRecorder()
                # executor.submit(audio_thread.start(), )

                # New Version:
                # Transcribe streaming audio from a microphone 
                executor.submit(speech2text(), )

                # Text to speech
                global text
                text2speech(text)

                # Play the audio file to let the user hear the sound
                pl = PlayMP3('audio file1.mp3')
                executor.submit(pl.play())


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

    calling(...) # Fill your telephone number 

    # print("test t2s API:")
    # text2speech()

    # print('\ntest s2t API:')
    # speech2text()

    print("Done")
    exit()


if __name__ == "__main__":
    main()
