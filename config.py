import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-default-secret-key')
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
    DATABASE_URI = os.environ.get('DATABASE_URI', 'sqlite:///olive_chatbot.db')