// Updated main.js with markdown and image support in history

document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const chatContainer = document.getElementById('chat-container');
    const imageUpload = document.getElementById('image-upload');
    const imagePreviewContainer = document.getElementById('image-preview-container');
    const toggleSidebar = document.getElementById('toggle-sidebar');
    const closeSidebar = document.getElementById('close-sidebar');
    const sidebar = document.getElementById('sidebar');
    const newChatButton = document.getElementById('new-chat');
    const historyContainer = document.getElementById('history-container');
    
    // State
    let currentConversationId = null;
    let currentImage = null;
    
    // Auto resize textarea
    userInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 120) + 'px';
    });
    
    // Toggle sidebar
    toggleSidebar.addEventListener('click', function() {
        sidebar.classList.add('active');
    });
    
    closeSidebar.addEventListener('click', function() {
        sidebar.classList.remove('active');
    });
    
    // Handle new chat
    newChatButton.addEventListener('click', function() {
        currentConversationId = null;
        clearChat();
        sidebar.classList.remove('active');
        
        // Add initial message
        const botMessage = createMessageElement('Hello Zouhaier, how can I help you today?', true);
        chatContainer.appendChild(botMessage);
    });
    
    // Handle image upload
    imageUpload.addEventListener('change', function(e) {
        if (e.target.files.length > 0) {
            const file = e.target.files[0];
            const reader = new FileReader();
            
            reader.onload = function(event) {
                currentImage = event.target.result;
                displayImagePreview(currentImage);
            };
            
            reader.readAsDataURL(file);
        }
    });
    
    // Handle form submission
    chatForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const message = userInput.value.trim();
        if (!message && !currentImage) return;
        
        // Add user message to chat
        const userMessage = createMessageElement(message, false);
        chatContainer.appendChild(userMessage);
        
        // Add image to chat if uploaded
        if (currentImage) {
            const imageElement = document.createElement('div');
            imageElement.className = 'message user-message';
            imageElement.innerHTML = `
                <div class="message-content">
                    <img src="${currentImage}" alt="User uploaded image" style="max-width: 200px; max-height: 200px; border-radius: 8px;">
                </div>
            `;
            chatContainer.appendChild(imageElement);
        }
        
        // Add typing indicator
        const typingIndicator = document.createElement('div');
        typingIndicator.className = 'message bot-message typing-indicator';
        typingIndicator.innerHTML = `
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        `;
        chatContainer.appendChild(typingIndicator);
        
        // Scroll to bottom
        chatContainer.scrollTop = chatContainer.scrollHeight;
        
        // Clear input
        userInput.value = '';
        userInput.style.height = 'auto';
        imagePreviewContainer.innerHTML = '';
        
        // Send message to server
        sendMessage(message, currentImage)
            .then(response => {
                // Remove typing indicator
                chatContainer.removeChild(typingIndicator);
                
                // Add bot response - now using HTML directly since server sends markdown converted to HTML
                const botMessage = document.createElement('div');
                botMessage.className = 'message bot-message';
                botMessage.innerHTML = `
                    <div class="message-content">
                        ${response.response}
                    </div>
                `;
                chatContainer.appendChild(botMessage);
                
                // Update conversation ID
                if (!currentConversationId) {
                    currentConversationId = response.conversation_id;
                    loadChatHistory();
                }
                
                // Scroll to bottom
                chatContainer.scrollTop = chatContainer.scrollHeight;
            })
            .catch(error => {
                console.error('Error:', error);
                chatContainer.removeChild(typingIndicator);
                
                const errorMessage = createMessageElement('Sorry, I encountered an error. Please try again.', true);
                chatContainer.appendChild(errorMessage);
                
                chatContainer.scrollTop = chatContainer.scrollHeight;
            });
        
        // Reset current image
        currentImage = null;
    });
    
    // Function to send message to server
    async function sendMessage(message, image) {
        const data = {
            message: message,
            conversation_id: currentConversationId
        };
        
        if (image) {
            data.image = image; // Send the complete data URL
        }
        
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        
        return response.json();
    }
    
    // Function to create message element
    function createMessageElement(content, isBot, imageId = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = isBot ? 'message bot-message' : 'message user-message';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        // For bot messages, we handle both raw text and HTML
        if (isBot) {
            // Content already contains HTML or we treat it as HTML
            contentDiv.innerHTML = content;
        } else {
            // Plain text content needs formatting
            contentDiv.innerHTML = formatMessage(content);
            
            // If there's an image ID associated with this message, display it
            if (imageId) {
                const imageElement = document.createElement('img');
                imageElement.src = `/api/images/${imageId}`;
                imageElement.alt = "Uploaded image";
                imageElement.style.maxWidth = '200px';
                imageElement.style.maxHeight = '200px';
                imageElement.style.borderRadius = '8px';
                imageElement.style.marginTop = '8px';
                contentDiv.appendChild(imageElement);
            }
        }
        
        messageDiv.appendChild(contentDiv);
        return messageDiv;
    }
    
    // Function to format message (convert URLs, add line breaks, etc.)
    function formatMessage(text) {
        if (!text) return '';
        
        // Convert URLs to clickable links
        const urlRegex = /(https?:\/\/[^\s]+)/g;
        text = text.replace(urlRegex, url => `<a href="${url}" target="_blank">${url}</a>`);
        
        // Convert line breaks to <br>
        text = text.replace(/\n/g, '<br>');
        
        return text;
    }
    
    // Function to display image preview
    function displayImagePreview(image) {
        imagePreviewContainer.innerHTML = '';
        
        const previewDiv = document.createElement('div');
        previewDiv.className = 'image-preview';
        previewDiv.innerHTML = `
            <img src="${image}" alt="Preview">
            <button class="remove-image"><i class="fas fa-times"></i></button>
        `;
        
        imagePreviewContainer.appendChild(previewDiv);
        
        // Add event listener to remove button
        const removeButton = previewDiv.querySelector('.remove-image');
        removeButton.addEventListener('click', function() {
            imagePreviewContainer.innerHTML = '';
            currentImage = null;
            imageUpload.value = '';
        });
    }
    
    // Function to load chat history
    async function loadChatHistory() {
        try {
            const response = await fetch('/api/history');
            const data = await response.json();
            
            historyContainer.innerHTML = '';
            
            if (data.length === 0) {
                const emptyMessage = document.createElement('div');
                emptyMessage.textContent = 'No conversation history';
                emptyMessage.style.color = '#888';
                emptyMessage.style.textAlign = 'center';
                emptyMessage.style.padding = '16px 0';
                historyContainer.appendChild(emptyMessage);
                return;
            }
            
            data.forEach(conversation => {
                const historyItem = document.createElement('div');
                historyItem.className = 'history-item';
                historyItem.dataset.id = conversation.id;
                
                // Get a clean text version for display (strip HTML tags if present)
                let displayText = conversation.last_message;
                if (displayText.includes('<')) {
                    // Create a temporary div to strip HTML
                    const tempDiv = document.createElement('div');
                    tempDiv.innerHTML = displayText;
                    displayText = tempDiv.textContent || tempDiv.innerText;
                }
                
                historyItem.textContent = displayText.length > 30 
                    ? displayText.substring(0, 30) + '...' 
                    : displayText;
                
                // Highlight current conversation
                if (conversation.id === currentConversationId) {
                    historyItem.style.backgroundColor = 'var(--secondary-color)';
                }
                
                historyItem.addEventListener('click', function() {
                    loadConversation(conversation.id, conversation.messages);
                });
                
                historyContainer.appendChild(historyItem);
            });
        } catch (error) {
            console.error('Error loading history:', error);
        }
    }
    
    // Function to load a specific conversation
    function loadConversation(conversationId, messages) {
        currentConversationId = conversationId;
        clearChat();
        
        messages.forEach(msg => {
            // Check if message has an associated image
            const imageId = msg.image_id;
            
            if (!msg.is_bot && imageId) {
                // First add the text message
                const messageElement = createMessageElement(msg.message, msg.is_bot);
                chatContainer.appendChild(messageElement);
                
                // Then add the image as a separate message
                const imageElement = document.createElement('div');
                imageElement.className = 'message user-message';
                imageElement.innerHTML = `
                    <div class="message-content">
                        <img src="/api/images/${imageId}" alt="User uploaded image" style="max-width: 200px; max-height: 200px; border-radius: 8px;">
                    </div>
                `;
                chatContainer.appendChild(imageElement);
            } else {
                // Regular message without image or bot message
                const messageElement = createMessageElement(msg.message, msg.is_bot);
                chatContainer.appendChild(messageElement);
            }
        });
        
        chatContainer.scrollTop = chatContainer.scrollHeight;
        sidebar.classList.remove('active');
        
        // Update history item highlighting
        const historyItems = document.querySelectorAll('.history-item');
        historyItems.forEach(item => {
            if (item.dataset.id === conversationId) {
                item.style.backgroundColor = 'var(--secondary-color)';
            } else {
                item.style.backgroundColor = '';
            }
        });
    }
    
    // Function to clear chat
    function clearChat() {
        chatContainer.innerHTML = '';
    }
    
    // Load chat history on page load
    loadChatHistory();
});