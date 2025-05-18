from sqlalchemy import Column, String, Boolean, DateTime, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import Config

Base = declarative_base()

class Conversation(Base):
    __tablename__ = 'conversations'
    
    id = Column(String, primary_key=True)
    image_id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    conversation_id = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    is_bot = Column(Boolean, default=False)
    timestamp = Column(DateTime, nullable=False)

# Create engine and session
engine = create_engine(Config.DATABASE_URI)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)