import json
import os

from openai import OpenAI
from prompts import assistant_instructions
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL')

class OpenAIClient:
    _instance = None
    
    def __init__(self):
        self.client = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def initialize(self, api_key, base_url=None):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
    
    def get_client(self):
        if self.client is None:
            raise ValueError("OpenAI client not initialized. Please set API key first.")
        return self.client

# 使用单例模式
openai_client = OpenAIClient.get_instance()

# Create or load assistant
def create_assistant(client):
    assistant_file_path = 'assistant.json'

    # If there is an assistant.json file already, then load that assistant
    if os.path.exists(assistant_file_path):
        with open(assistant_file_path, 'r') as file:
            assistant_data = json.load(file)
            assistant_id = assistant_data['assistant_id']
            print("Loaded existing assistant ID.")
    else:
        # If no assistant.json is present, create a new assistant using the below specifications

        # To change the knowledge document, modify the file name below to match your document If you want to add
        # multiple files, paste this function into ChatGPT and ask for it to add support for multiple files
        # file = client.files.create(file=open("resume/my_cover.pdf", "rb"),
        #                            purpose='assistants')
        vector_store = client.vector_stores.create(name="My Resume")
        print(vector_store.id)
        file_streams = [open("resume/my_cover.pdf", "rb")]
        # Use the upload and poll SDK helper to upload the files, add them to the vector store,
        # and poll the status of the file batch for completion.
        file_batch = client.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vector_store.id, files=file_streams
        )

        print(file_batch.status)
        print(file_batch.file_counts)
        # New version of the assistant
        assistant = client.beta.assistants.create(
            instructions=assistant_instructions,
            model="gpt-4o",
            tools=[{"type": "file_search"}],
        )

        assistant = client.beta.assistants.update(
            assistant_id=assistant.id,
            tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
        )

        # Create a new assistant.json file to load on future runs
        with open(assistant_file_path, 'w') as file:
            json.dump({'assistant_id': assistant.id}, file)
            print("Created a new assistant and saved the ID.")

        assistant_id = assistant.id

    return assistant_id
