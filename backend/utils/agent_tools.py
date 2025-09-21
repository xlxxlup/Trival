import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
load_dotenv
def get_llm():
    model = os.getenv("MODEL_NAME")
    api_key = os.getenv("MODEL_API_KEY")
    base_url = os.getenv("MODEL_BASE_URL")
    
    llm = ChatOpenAI(model_name=model,openai_api_key=api_key,openai_api_base=base_url,temperature=0)
    return llm