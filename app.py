from flask import Flask, render_template, request, jsonify, session
import os
import base64
from datetime import datetime
import uuid
from groq import Groq
from config import Config
from database.db_handler import save_conversation, get_user_conversations, save_image, get_image_by_id
import json
import markdown
import bleach

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = app.config['SECRET_KEY']

# Initialize Groq client with better error handling
try:
    client = Groq(api_key=app.config['GROQ_API_KEY'])
except Exception as e:
    print(f"Failed to initialize Groq client: {str(e)}")
    client = None

@app.before_request
def before_request():
    # Create a session ID if not exists
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    # Check if API key is configured
    if app.config['GROQ_API_KEY'] is None or app.config['GROQ_API_KEY'] == '':
        return jsonify({'error': 'GROQ_API_KEY is not configured'}), 500
        
    if client is None:
        return jsonify({'error': 'Groq client failed to initialize'}), 500
    
    data = request.json
    message = data.get('message', '')
    image_data = data.get('image')
    
    user_id = session['user_id']
    conversation_id = data.get('conversation_id') or str(uuid.uuid4())
    
    # Detect language from user message for concise response
    user_language = "en"  # Default to English
    if message and len(message.strip()) > 0:
        # Simple language detection based on common words
        message_lower = message.lower()
        if any(word in message_lower for word in ['bonjour', 'salut', 'merci', 'comment']):
            user_language = "fr"
        elif any(word in message_lower for word in ['hola', 'gracias', 'como', 'qué']):
            user_language = "es"
        elif any(word in message_lower for word in ['مرحبا', 'شكرا', 'كيف', 'سلام']):
            user_language = "ar"
    
    # Set memory cutoff - how many previous messages to include
    memory_cutoff = 10
    
    # Prepare the system message for olive expertise with language and conciseness instruction
    system_message = f"""
    You are an expert in agriculture, specifically olives and olive diseases. 
    Provide accurate and helpful information about olive cultivation, diseases, treatments, 
    and best practices. Your answers should be informative and understandable to farmers 
    and enthusiasts. If an image is provided, analyze it for signs of diseases or issues 
    with olive trees or fruits.
    
    IMPORTANT INSTRUCTIONS:
    1. Format your responses using markdown for better readability.
    2. Be concise and to the point. Limit your response to 3-4 sentences when possible.
    3. Respond in the same language as the user's query. The detected language is: {user_language}.
    4. For diseases, quickly identify the disease name, key symptoms, and basic treatment.
    5. Refer to the chat history to maintain context in the conversation.
    6. Address the user as Zouhaier in your responses.
    7. If the user mentions something from earlier in the conversation, acknowledge it.
    """
    
    # Format messages for the API
    messages = [{"role": "system", "content": system_message}]
    
    # Get conversation history if available
    try:
        history = get_user_conversations(user_id, conversation_id)
        
        # Only include the last 'memory_cutoff' messages
        limited_history = history[-memory_cutoff:] if len(history) > memory_cutoff else history
        
        for msg in limited_history:
            role = "assistant" if msg.get("is_bot", False) else "user"
            content = msg.get("message", "")
            messages.append({"role": role, "content": content})
    except Exception as e:
        print(f"Error retrieving conversation history: {str(e)}")
        # Continue without history if there's an error
    
    image_id = None
    # Prepare the user message with text and optional image
    if image_data:
        # Save image to database if it exists
        try:
            # Extract base64 data
            if "base64," in image_data:
                image_base64 = image_data.split("base64,")[1]
            else:
                image_base64 = image_data
                
            # Save image and get ID
            image_id = save_image(user_id, conversation_id, image_base64)
        except Exception as e:
            print(f"Error saving image: {str(e)}")
        
        # Prepare content array for multimodal input
        content_array = []
        
        # Add text part if present
        if message:
            content_array.append({
                "type": "text",
                "text": message
            })
        
        # Add image to content array
        content_array.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{image_base64}"
            }
        })
        
        # Add the multimodal message
        messages.append({
            "role": "user",
            "content": content_array
        })
    else:
        # Just add the text message if no image
        messages.append({"role": "user", "content": message})
    
    # Call the Groq API
    try:
        print(f"Sending request to Groq API with model: meta-llama/llama-4-scout-17b-16e-instruct")
        print(f"Number of messages in context: {len(messages)}")
        
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=messages,
            temperature=0.5,
            max_tokens=1024
        )
        
        bot_response = response.choices[0].message.content
        
        # Convert markdown to HTML for the response
        html_response = markdown.markdown(bot_response)
        
        # Sanitize HTML to prevent XSS
        allowed_tags = ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'em', 
                       'ul', 'ol', 'li', 'blockquote', 'code', 'pre', 'br', 'a']
        allowed_attrs = {'a': ['href', 'title']}
        html_response = bleach.clean(html_response, tags=allowed_tags, attributes=allowed_attrs)
        
        # Save the conversation to the database
        timestamp = datetime.now()  # Using Python datetime object, not ISO string
        
        # Try to save, but continue even if it fails
        db_save_success = True
        
        # Save user's message
        user_msg = message if message else "[Image uploaded]"
        try:
            save_conversation(user_id, conversation_id, user_msg, False, timestamp, image_id)
        except Exception as e:
            print(f"Error saving user message: {str(e)}")
            db_save_success = False
        
        # Save bot's response - save the markdown version in the database
        try:
            save_conversation(user_id, conversation_id, bot_response, True, timestamp)
        except Exception as e:
            print(f"Error saving bot response: {str(e)}")
            db_save_success = False
        
        if not db_save_success:
            print("Warning: Failed to save conversation to database")
        
        return jsonify({
            'response': html_response,  # Send the HTML version to the frontend
            'raw_response': bot_response,  # Also send the raw markdown for history
            'conversation_id': conversation_id
        })
        
    except Exception as e:
        error_msg = str(e)
        print(f"Groq API error: {error_msg}")
        
        # If there's a specific error about multimedia content not being supported
        if "multimodal" in error_msg.lower() or "content array" in error_msg.lower() or "image" in error_msg.lower():
            # Fallback to text-only request
            try:
                print("Attempting fallback to text-only request")
                # Replace the multimodal message with text-only
                if image_data:
                    # Find and replace the last message (which would be the multimodal one)
                    messages[-1] = {
                        "role": "user", 
                        "content": message if message else "I've uploaded an image of olive trees/fruits. Please analyze it for any visible issues or diseases."
                    }
                    
                    response = client.chat.completions.create(
                        model="meta-llama/llama-4-scout-17b-16e-instruct",
                        messages=messages,
                        temperature=0.5,
                        max_tokens=1024
                    )
                    
                    bot_response = response.choices[0].message.content
                    fallback_note = "**Note: I couldn't process the image, but I can still help with your text query.**\n\n"
                    bot_response = fallback_note + bot_response
                    
                    # Convert markdown to HTML
                    html_response = markdown.markdown(bot_response)
                    html_response = bleach.clean(html_response, tags=allowed_tags, attributes=allowed_attrs)
                    
                    # Save conversations with proper datetime object
                    timestamp = datetime.now()
                    user_msg = message if message else "[Image uploaded]"
                    save_conversation(user_id, conversation_id, user_msg, False, timestamp, image_id)
                    save_conversation(user_id, conversation_id, bot_response, True, timestamp)
                    
                    return jsonify({
                        'response': html_response,
                        'raw_response': bot_response,
                        'conversation_id': conversation_id
                    })
                
            except Exception as fallback_error:
                print(f"Fallback also failed: {str(fallback_error)}")
                
        return jsonify({
            'error': error_msg,
            'message': "There was an error processing your request. If you uploaded an image, please try again with text only as this model may not support image processing through the Groq API."
        }), 500

@app.route('/api/history', methods=['GET'])
def get_history():
    user_id = session['user_id']
    try:
        history = get_user_conversations(user_id)
        
        # Convert markdown to HTML for all bot messages in history
        for conversation in history:
            for msg in conversation['messages']:
                if msg.get('is_bot') and not msg.get('message', '').startswith('<'):
                    # Convert markdown to HTML
                    msg['message'] = markdown.markdown(msg['message'])
                    
                    # Sanitize HTML
                    allowed_tags = ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'em', 
                                   'ul', 'ol', 'li', 'blockquote', 'code', 'pre', 'br', 'a']
                    allowed_attrs = {'a': ['href', 'title']}
                    msg['message'] = bleach.clean(msg['message'], tags=allowed_tags, attributes=allowed_attrs)
        
        return jsonify(history)
    except Exception as e:
        print(f"Error retrieving history: {str(e)}")
        return jsonify([]), 500

@app.route('/api/images/<image_id>', methods=['GET'])
def get_image(image_id):
    from flask import send_file
    from io import BytesIO
    import base64
    
    try:
        image_data = get_image_by_id(image_id)
        
        if not image_data:
            return "Image not found", 404
            
        # Convert base64 to binary
        binary_data = base64.b64decode(image_data)
        
        # Create a BytesIO object
        image_io = BytesIO(binary_data)
        
        # Send the file
        return send_file(image_io, mimetype='image/jpeg')
    except Exception as e:
        print(f"Error retrieving image: {str(e)}")
        return "Error retrieving image", 500

if __name__ == '__main__':
    app.run(debug=True)