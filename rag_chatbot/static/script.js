document.addEventListener('DOMContentLoaded', () => {
    const chatWindow = document.getElementById('chat-window');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');

    // Gera um UUID simples para a sessão do navegador
    const sessionId = 'session_' + Math.random().toString(36).substr(2, 9);

    sendButton.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });

    async function sendMessage() {
        const message = userInput.value.trim();
        if (message === '') return;

        // Adiciona a mensagem do usuário à janela
        addMessageToWindow(message, 'user');
        userInput.value = '';
        userInput.disabled = true;
        sendButton.disabled = true;
        addLoadingIndicator();

        try {
            // Envia a mensagem para o backend
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    session_id: sessionId
                }),
            });

            removeLoadingIndicator();
            userInput.disabled = false;
            sendButton.disabled = false;
            userInput.focus();

            if (!response.ok) {
                throw new Error('Erro na resposta do servidor.');
            }

            const data = await response.json();

            // Adiciona a resposta do bot à janela, com o message_id
            addMessageToWindow(data.response, 'bot', data.message_id);

        } catch (error) {
            console.error('Erro ao enviar mensagem:', error);
            removeLoadingIndicator();
            userInput.disabled = false;
            sendButton.disabled = false;
            addMessageToWindow('Desculpe, ocorreu um erro de comunicação com o servidor.', 'bot');
        }
    }

    function addMessageToWindow(message, sender, messageId = null) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', `${sender}-message`);

        const textElement = document.createElement('p');
        textElement.textContent = message;
        messageElement.appendChild(textElement);

        // Adiciona botões de feedback se for uma mensagem do bot
        if (sender === 'bot' && messageId) {
            const feedbackElement = document.createElement('div');
            feedbackElement.classList.add('feedback-buttons');

            const likeButton = document.createElement('button');
            likeButton.classList.add('feedback-btn', 'like');
            likeButton.innerHTML = '👍';
            likeButton.onclick = () => sendFeedback(messageId, 'like', likeButton);

            const dislikeButton = document.createElement('button');
            dislikeButton.classList.add('feedback-btn', 'dislike');
            dislikeButton.innerHTML = '👎';
            dislikeButton.onclick = () => sendFeedback(messageId, 'dislike', dislikeButton);

            feedbackElement.appendChild(likeButton);
            feedbackElement.appendChild(dislikeButton);
            messageElement.appendChild(feedbackElement);
        }

        chatWindow.appendChild(messageElement);
        chatWindow.scrollTop = chatWindow.scrollHeight; // Auto-scroll
    }

    function addLoadingIndicator() {
        const loadingElement = document.createElement('div');
        loadingElement.classList.add('message', 'bot-message');
        loadingElement.id = 'loading-indicator';
        loadingElement.innerHTML = '<p>Digitando...</p>';
        chatWindow.appendChild(loadingElement);
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    function removeLoadingIndicator() {
        const loadingElement = document.getElementById('loading-indicator');
        if (loadingElement) {
            loadingElement.remove();
        }
    }

    async function sendFeedback(messageId, rating, button) {
        try {
            await fetch('/feedback', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message_id: messageId,
                    rating: rating
                }),
            });

            // Desativa os botões de feedback após o clique e destaca o selecionado
            const parent = button.parentElement;
            parent.querySelectorAll('.feedback-btn').forEach(btn => btn.disabled = true);
            if (rating === 'like') {
                button.classList.add('liked');
            } else {
                button.classList.add('disliked');
            }
            console.log(`Feedback (${rating}) enviado para message_id: ${messageId}`);

        } catch (error) {
            console.error('Erro ao enviar feedback:', error);
        }
    }
});