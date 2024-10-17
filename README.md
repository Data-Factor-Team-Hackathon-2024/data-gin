# data-gin

This is a submission for the Generative AI World Cup 2024, organized by Databricks.
Hackathon (stackup.dev)

We are The Data Factor Team. Our solution is Data GIN - an interactive web application, that allows users to ask questions about their data using voice. The voice request is further translated into SQL query, with final results being returned as both speech and text. It also allows user personalization by applying voice recognition model. 
The solution is built using Databricks platform, and Flask/JavaScript/HTML/CSS for a web application.

The following code modules are included:

	1. Web application 'Data GIN'
	
	Flask-based application is a full stack web interface hosted locally. It is built to record user's voice, to ingest CSV files and display them within HTML pages, to send requests to the Databricks environment with CSV, text and audio files, to run LLMs and display LLM responses via voice in the user interface.
	
	2. Databricks Notebook 'VoiceRecognitionModel'
	This notebook trains a model to recognize user's voice.
	
	3. Databricks Notebook 'VoiceInference'
	This notebook converts audio of the user's request into text, and performs user's voice recognition.
	
	4. Databricks Notebook 'Read UC Dataset PandasAI OpenAI'
	This notebook uses PandasAI library to process user's request in natural language into SQL and return results back to the web application.
	
	5. Databricks Workflow 'VoiceRecognitionModel' (json file)
	This workflow checks for new audio file arrival and trains voice recognition model.
	
	6. Databricks Workflow 'VoiceInference' (json file)
	This workflow checks for new audio file arrival, and triggers voice recognition and PandasAI notebooks.
	
	5. CSV file 'bank_transaction'
This file is a dummy bank transactions dataset.![image](https://github.com/user-attachments/assets/b0b9c33d-b0f4-4281-bbe0-2f52e4fabb58)
