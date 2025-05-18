from sqlalchemy import Column, String, Boolean, DateTime, Text, create_engine, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import Config
import uuid
from datetime import datetime
import os

Base = declarative_base()

class Conversation(Base):
    __tablename__ = 'conversations'
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    conversation_id = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    is_bot = Column(Boolean, default=False)
    timestamp = Column(DateTime, nullable=False)
    image_id = Column(String, nullable=True)  # Reference to image if present

class Image(Base):
    __tablename__ = 'images'
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    conversation_id = Column(String, nullable=False)
    image_data = Column(Text, nullable=False)  # Base64 encoded image
    timestamp = Column(DateTime, nullable=False)

# Create engine
db_path = Config.DATABASE_URI
if db_path.startswith('sqlite:///'):
    db_file = db_path.replace('sqlite:///', '')
    db_dir = os.path.dirname(db_file)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)

engine = create_engine(Config.DATABASE_URI)

# Handle database migration for existing tables
def setup_database():
    from sqlalchemy import inspect, MetaData
    
    inspector = inspect(engine)
    metadata = MetaData()
    
    # Check if conversations table exists
    if 'conversations' in inspector.get_table_names():
        # Check if image_id column exists
        columns = [col['name'] for col in inspector.get_columns('conversations')]
        if 'image_id' not in columns:
            print("Adding image_id column to conversations table...")
            try:
                with engine.connect() as connection:
                    connection.execute("ALTER TABLE conversations ADD COLUMN image_id VARCHAR")
                    connection.commit()
                print("Column added successfully")
            except Exception as e:
                print(f"Error adding column: {str(e)}")
    
    # Create tables that don't exist
    Base.metadata.create_all(engine)
    
    # Check if images table exists
    if 'images' not in inspector.get_table_names():
        print("Creating images table...")
        try:
            with engine.connect() as connection:
                connection.execute("""
                CREATE TABLE images (
                    id VARCHAR PRIMARY KEY,
                    user_id VARCHAR NOT NULL,
                    conversation_id VARCHAR NOT NULL,
                    image_data TEXT NOT NULL,
                    timestamp DATETIME NOT NULL
                )
                """)
                connection.commit()
            print("Images table created successfully")
        except Exception as e:
            print(f"Error creating images table: {str(e)}")

# Run database setup
setup_database()

# Create session
Session = sessionmaker(bind=engine)

def save_conversation(user_id, conversation_id, message, is_bot, timestamp, image_id=None):
    """Save a conversation message to the database"""
    session = Session()
    try:
        # Ensure timestamp is a Python datetime object
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp)
            except ValueError:
                timestamp = datetime.now()
        
        new_message = Conversation(
            id=str(uuid.uuid4()),
            user_id=user_id,
            conversation_id=conversation_id,
            message=message,
            is_bot=is_bot,
            timestamp=timestamp,
            image_id=image_id
        )
        session.add(new_message)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"Database error: {str(e)}")
        return False
    finally:
        session.close()

def save_image(user_id, conversation_id, image_data):
    """Save an image to the database and return its ID"""
    session = Session()
    try:
        image_id = str(uuid.uuid4())
        new_image = Image(
            id=image_id,
            user_id=user_id,
            conversation_id=conversation_id,
            image_data=image_data,
            timestamp=datetime.now()
        )
        session.add(new_image)
        session.commit()
        return image_id
    except Exception as e:
        session.rollback()
        print(f"Database error saving image: {str(e)}")
        raise
    finally:
        session.close()

def get_image_by_id(image_id):
    """Get image data by ID"""
    session = Session()
    try:
        image = session.query(Image).filter_by(id=image_id).first()
        if image:
            return image.image_data
        return None
    finally:
        session.close()

def get_user_conversations(user_id, conversation_id=None):
    """Get conversations for a user, optionally filtered by conversation ID"""
    session = Session()
    try:
        query = session.query(Conversation).filter_by(user_id=user_id)
        
        if conversation_id:
            # Get messages for a specific conversation
            messages = query.filter_by(conversation_id=conversation_id)\
                         .order_by(Conversation.timestamp).all()
            
            # Check if image_id column exists in the result
            has_image_id = hasattr(messages[0], 'image_id') if messages else False
            
            result = []
            for msg in messages:
                message_dict = {
                    "message": msg.message,
                    "is_bot": msg.is_bot,
                    "timestamp": msg.timestamp.isoformat(),
                }
                
                # Add image_id if the column exists
                if has_image_id:
                    message_dict["image_id"] = msg.image_id
                    
                result.append(message_dict)
        else:
            # Get all conversations for the user
            conversations = {}
            for msg in query.order_by(Conversation.timestamp).all():
                if msg.conversation_id not in conversations:
                    conversations[msg.conversation_id] = {
                        "id": msg.conversation_id,
                        "last_message": msg.message,
                        "timestamp": msg.timestamp.isoformat(),
                        "messages": []
                    }
                
                message_dict = {
                    "message": msg.message,
                    "is_bot": msg.is_bot,
                    "timestamp": msg.timestamp.isoformat(),
                }
                
                # Add image_id if the column exists
                if hasattr(msg, 'image_id'):
                    message_dict["image_id"] = msg.image_id
                
                conversations[msg.conversation_id]["messages"].append(message_dict)
            
            result = list(conversations.values())
        
        return result
    except Exception as e:
        print(f"Error in get_user_conversations: {str(e)}")
        # Return empty result on error
        return [] if conversation_id is None else []
    finally:
        session.close()