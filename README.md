# PhoneCall_Voicebots_SIM800C


The program implements the Voicebots with Phone Call using ATK-SIM800C GSM/GPRS Module. Natural TTS will be integrated to facilitate advanced features. This project covers lots of scopes, like serial programming, multithreading, audio processing, and NLP-related features supported by Google Could Platform (GCP).

## Getting started
In order to use Python Client for Cloud Text-to-Speech API, you ought to go through the following steps:

1. `Select or create a Cloud Platform project.`
2. `Enable billing for your project.`
3. `Enable the Cloud Text-to-Speech API.`
4. `Setup Authentication.`

### Setting up a Python development environment and GCP configuration

Given multiple APIs would be used, it is recommended to have a pre-project environment when developing locally with Python. As for GCP, Please refer to [Google Cloud Guide](https://cloud.google.com/python/docs/setup#windows) to set up virtual environment. In addition, you may refer to [Text-to-Speech client libraries Guide](<https://cloud.google.com/text-to-speech/docs/libraries#client-libraries-install-python>) to further set up authentication and the environment.

<pre><code> from google.cloud import texttospeech
</code></pre>

## Multithreading with thread pool

More details will be available later.

## NLP-related features

Apart from calling function, it provides basic MP3 playing function, and audio recording. As for advanced NLP-related features, which include

> 1. Convert a text file to mp3/wav format utilizing Google Cloud API, and this file would be played later.
> 2. Convert the audio recording file in wav to text file.
> 3. Languages should preferably include English, Cantonese and Mandrian. 

Those are achieved with the help of [Google Texttospeech API](https://cloud.google.com/text-to-speech). For 


## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details

