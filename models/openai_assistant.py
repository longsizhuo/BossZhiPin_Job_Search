import json
import os

from openai import OpenAI
from models.prompts import assistant_instructions
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL')

# Init OpenAI Client
client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)


# Create or load assistant
def create_assistant(chatgpt_model, client):
    assistant_file_path = '../assistant.json'

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
        print(vector_store)
        file_streams = [open("./resume/my_cover.pdf", "rb")]
        # Use the upload and poll SDK helper to upload the files, add them to the vector store,
        # and poll the status of the file batch for completion.
        file_batch = client.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vector_store.id, files=file_streams
        )
        # New version of the assistant
        assistant = client.beta.assistants.create(
            instructions=assistant_instructions,
            model=chatgpt_model,
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
