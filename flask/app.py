### Importing libraries (if part of the deployed app they will need to be added to the 'requirements.txt' file)
from flask import Flask, render_template, request, redirect, url_for, jsonify
import requests
import pandas as pd
import io
import azure.cognitiveservices.speech as speechsdk
import openai
from openai import OpenAI
import os
import re
from databricks.connect import DatabricksSession
import base64

app = Flask(__name__)

### Replace with your Azure speeck key and service region values
speech_key, service_region = "", ""
### Replace with you own OpenAI API key
api_key = ""
client = OpenAI(api_key=api_key)

### Replace with your Databricks API token and workspace URL
DATABRICKS_TOKEN = ""
DATABRICKS_WORKSPACE_URL = ""

UPLOAD_FOLDER = os.path.join(app.root_path, 'voice_samples')  #Create 'voice_samples' folder if needed
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

### Helper functions
#Creation of incremental file names
def create_incremental_filename(prefix, extension):
    """Creates a new filename with an incrementing integer."""
    i = 1
    while True:
        filename = f"{prefix}_{i}.{extension}"
        if not os.path.exists(filename):
            break
        i += 1
    return filename

### DATABRICKS Implementation
def read_file_from_dbfs(dbfs_path):
    try:
        response = requests.get(
            f"{DATABRICKS_WORKSPACE_URL}/api/2.0/dbfs/read",
            headers={'Authorization': f'Bearer {DATABRICKS_TOKEN}'},
            params={'path': dbfs_path},
        )
        response.raise_for_status()  # Raise an exception for bad status codes
        if 'application/json' in response.headers.get('Content-Type', ''):
            return response.json()
        else:
            # data = response.json()['data']  # Assuming the response is in JSON format
            # csv_data = io.StringIO(data)  # Create a file-like object
            # df = pd.read_csv(csv_data)  
            # return df
            return response.text  # Assume text content by default
    except requests.exceptions.RequestException as e:
        print(f"Error reading file from DBFS: {e}")
        return None

### Function to create a matching file name for the response in Databricks
def compile_response_filename(question_filename):
    match = re.search(r'\d+', question_filename)
    if match:
        digit = match.group(0)
        return f"response_{digit}.txt"
    else:
        return None

### Home page
@app.route('/', methods=['GET', 'POST'])
def index():
  return render_template('index.html')

### Home page button from other pages (not index.html)
@app.route('/home', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        if 'home' in request.form:
            return render_template('index.html')

### Page for voice biometrics
@app.route('/submit_name', methods=['GET','POST'])
def submit_name():
    return render_template('biometrics.html')

### Page for voice biometrics: recording voice sample.
@app.route('/upload_voice_sample', methods=['GET', 'POST'])
def upload_voice():
    if request.method == 'POST':
        if 'audio_data' in request.files:
            file = request.files['audio_data']
            sample_filename = create_incremental_filename('sample_voice', 'wav')
            with open(sample_filename, 'w') as f:
                f.write(str(file))

            with open(sample_filename, "r") as f:
                file_content = f.read() 
                print('Sample voice file name is', sample_filename)

        ### Location for uploading the recorded voice sample to the DBFS folder in Databricks           
        dbfs_path_0 = "" + sample_filename
        files = {'file': (sample_filename, file_content, 'audio/wav')}
        response = requests.post(f"{DATABRICKS_WORKSPACE_URL}/api/2.0/dbfs/put", 
            headers={'Authorization': f'Bearer {DATABRICKS_TOKEN}'}, 
            data={'path': dbfs_path_0, 'overwrite': 'true'},
            files=files)
        voice_sample = sample_filename
        print('Voice sample is: ', voice_sample)
    return render_template('biometrics.html')

### Page for Databricks dataset display and questions: displaying the dataframe before questions
@app.route('/display_db', methods=['GET', 'POST'])
def display_df():
    df = pd.read_csv('static/bank_transactions.csv')
    content = df.to_html(classes='table table-striped', 
         index=True, 
         justify='left',
         border=0,  
         max_rows=6, 
         max_cols=None)
    return render_template('display_df.html', content=content)

### Page for Databricks dataset: asking questions using voice
@app.route('/db', methods=['GET', 'POST'])
def db():
    result = ''
    file_content = ''
    file_content_answer = ''
    if request.method == 'POST':
        if 'db' in request.form:
            # Speech to text and text to speech parameters 
            speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
            speech_config.speech_recognition_language="en-US"
            # audio config is set to the default microphone on device
            audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
            # audio config_1 is set to the default speaker on device
            audio_config_1 = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
            # Voice selection can be changed as desired
            speech_config.speech_synthesis_voice_name='en-US-AvaMultilingualNeural'
            speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config_1)
            speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

            print("Hi, I am your Data GIN, please ask me any question about your dataset.")
            speech_recognition_result = speech_recognizer.recognize_once_async().get()

            if speech_recognition_result.reason == speechsdk.ResultReason.RecognizedSpeech:
                result = speech_recognition_result.text
                print("Recognized: {}".format(speech_recognition_result.text))
            
            filename = create_incremental_filename('voice', 'wav')
            with open(filename, 'w') as f:
                f.write(str(result))

            with open(filename, "r") as f:
                file_content = f.read()
                print('Filename is', filename)

            ### Upload the recorded question as audio file to Databricks DBFS
            dbfs_path = "" + filename
            files = {'file': (filename, file_content, 'audio/wav')}
            response = requests.post(f"{DATABRICKS_WORKSPACE_URL}/api/2.0/dbfs/put", 
                headers={'Authorization': f'Bearer {DATABRICKS_TOKEN}'}, 
                data={'path': dbfs_path, 'overwrite': 'true'},
                files=files)
            question_filename = filename
            print('Question_filename is', question_filename) #For error handling
            response_filename = compile_response_filename(question_filename)
            print(response_filename) #For error handling

            ### Importing response from Databrciks for the same number as the number in the question
            dbfs_path = "" + response_filename
            file_content_json = read_file_from_dbfs(dbfs_path)
            if file_content_json:
                # Decode the Base64 content
                file_content_answer = base64.b64decode(file_content_json['data']).decode('utf-8')
                # Speech to text and text to speech parameters 
                speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
                speech_config.speech_recognition_language="en-US"
                # audio config_1 is set to the default speaker on device
                audio_config_1 = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
                # Voice selection can be changed as desired
                speech_config.speech_synthesis_voice_name='en-US-AvaMultilingualNeural'
                speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config_1)
                speech_synthesis_result = speech_synthesizer.speak_text_async(file_content_answer).get()
                print(speech_synthesis_result) #For error handling
                print(file_content_answer) #For error handling
    return render_template('db_chat.html', result=result, file_content=file_content_answer)

### Page to upload your local dataset and ask questions
@app.route('/upload', methods=['POST'])
def upload():
  if request.method == 'POST':
    if 'upload' in request.form:
      return render_template('upload.html')

### Page to display the uploaded dataset
@app.route('/display', methods=['GET', 'POST'])
def display():
    if request.method == 'POST':
        if 'file' not in request.files:
            return 'No file part'
        file = request.files['file']
        if file.filename == '':
            return 'No selected file'
        if file:
            try:
                df = pd.read_csv(file)
                print(df)
                df.to_csv('uploaded_file.txt', sep=' ', index=False)
                content = df.to_html(classes='table table-striped', 
                         index=True,
                         justify='left',
                         border=0, 
                         max_rows=6, 
                         max_cols=None)
                return render_template('display.html', content=content)
            except Exception as e:
                return f'Error reading file: {e}'

### Page to ask a question about the local dataset
@app.route('/answer', methods=['POST'])
def answer():
    result = ''
    answer = ''
    if request.method == 'POST':
        if 'answer' in request.form:
            # Speech to text and text to speech parameters 
            speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
            speech_config.speech_recognition_language="en-US"
            # audio config is set to the default microphone on device
            audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
            # audio config_1 is set to the default speaker on device
            audio_config_1 = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
            # Voice selection can be changed as desired
            speech_config.speech_synthesis_voice_name='en-US-AvaMultilingualNeural'
            speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config_1)
            speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

            print("Hi, I am your Data GIN, please ask me any question about your dataset.")
            speech_recognition_result = speech_recognizer.recognize_once_async().get()

            if speech_recognition_result.reason == speechsdk.ResultReason.RecognizedSpeech:
                result = speech_recognition_result.text
                print("Recognized: {}".format(speech_recognition_result.text))
            #generating OpenAI response
            datagen_model = "gpt-4o"
            df = pd.read_table('uploaded_file.txt', sep=' ')
            question = result
            response = client.chat.completions.create(
            model=datagen_model,
            messages=[
                {"role": "system", "content":f"You are a helpful voice assistant for datasets {df} and you only respond in one sentence about the dataset {df}."},
                {"role": "user", "content":f"You are a helpful voice assistant for my dataset {df}. Only answer {question} about information in {df}."}
            ])
            res = response.choices[0].message.content
            print(res)
            answer = res
            print(answer)
            speech_synthesis_result = speech_synthesizer.speak_text_async(res.strip()).get()
    return render_template('answer.html', result=result, answer=answer)

### Page to ask another question about the same dataset
@app.route('/answer_again', methods=['GET', 'POST'])
def answer_again():
    result_again = ''
    answer_again = ''
    if request.method == 'POST':
        if 'answer_again' in request.form:
            # Speech to text and text to speech parameters 
            speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
            speech_config.speech_recognition_language="en-US"
            # audio config is set to the default microphone on device
            audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
            # audio config_1 is set to the default speaker on device
            audio_config_1 = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
            # Voice selection can be changed as desired
            speech_config.speech_synthesis_voice_name='en-US-AvaMultilingualNeural'
            speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config_1)
            speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

            print("Hi, I am your Data GIN, please ask me any question about your dataset.")
            speech_recognition_result = speech_recognizer.recognize_once_async().get()

            if speech_recognition_result.reason == speechsdk.ResultReason.RecognizedSpeech:
                result_again = speech_recognition_result.text
                print("Recognized: {}".format(speech_recognition_result.text))
            #generating OpenAI response
            datagen_model = "gpt-4o"
            df = pd.read_table('uploaded_file.txt', sep=' ')
            question = result_again
            response = client.chat.completions.create(
            model=datagen_model,
            messages=[
                {"role": "system", "content":f"You are a helpful voice assistant for datasets {df} and you only respond in one sentence about the dataset {df}."},
                {"role": "user", "content":f"You are a helpful voice assistant for my dataset {df}. Only answer {question} about information in {df}."}
            ])
            res = response.choices[0].message.content
            answer_again = res
            print(answer_again)
            speech_synthesis_result = speech_synthesizer.speak_text_async(res.strip()).get()
    return render_template('answer_again.html', result=result_again, answer=answer_again)

### Page for chatting with AI
@app.route('/chat', methods=['POST'])
def chat():
    result = ''
    answer = ''
    if request.method == 'POST':
        if 'chat' in request.form:
            # Speech to text and text to speech parameters 
            speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
            speech_config.speech_recognition_language="en-US"
            # audio config is set to the default microphone on device
            audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
            # audio config_1 is set to the default speaker on device
            audio_config_1 = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
            # Voice selection can be changed as desired
            speech_config.speech_synthesis_voice_name='en-US-AvaMultilingualNeural'
            speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config_1)
            speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

            print("Hi, I am your Data GIN, please ask me any question about your dataset.")
            speech_recognition_result = speech_recognizer.recognize_once_async().get()

            if speech_recognition_result.reason == speechsdk.ResultReason.RecognizedSpeech:
                result = speech_recognition_result.text
                print("Recognized: {}".format(speech_recognition_result.text))
            
            # Generating OpenAI response
            datagen_model = "gpt-4o"
            question = result
            response = client.chat.completions.create(
            model=datagen_model,
            messages=[
                {"role": "system", "content": "You are a helpful voice assistant. Respond in one sentence."},
                {"role": "user", "content": question}
            ])
            res = response.choices[0].message.content
            print(res)
            speech_synthesis_result = speech_synthesizer.speak_text_async(res.strip()).get()
            answer = res
    return render_template('chat.html', result=result, answer=answer)

if __name__ == '__main__':
    app.run(debug=True)
