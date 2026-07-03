import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { MessageList } from '../../features/chat/components/MessageList';
import { MessageInput } from '../../features/chat/components/MessageInput';
import { Message } from '../../types/message';
import { Button } from '../../components/Button/Button';

export const Chat: React.FC = () => {
  const { username, room } = useParams<{ username: string; room: string }>();
  const navigate = useNavigate();

  const decodedUsername = username ? decodeURIComponent(username) : 'Guest';
  const decodedRoom = room ? decodeURIComponent(room) : 'general';

  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      username: 'Alice',
      content: 'Hey everyone! 👋',
      timestamp: '14:30',
    },
    {
      id: '2',
      username: 'Bob',
      content: 'Hi Alice! How are you?',
      timestamp: '14:31',
    },
    {
      id: '3',
      username: 'Lucas',
      content: 'Hello! Welcome to the chat',
      timestamp: '14:32',
    },
    {
      id: '4',
      username: 'Alice',
      content: 'Thanks! This is a great room',
      timestamp: '14:33',
    },
  ]);

  const handleSendMessage = (content: string) => {
    const newMessage: Message = {
      id: Date.now().toString(),
      username: decodedUsername,
      content: content,
      timestamp: new Date().toLocaleTimeString('pt-BR', {
        hour: '2-digit',
        minute: '2-digit',
      }),
    };
    setMessages([...messages, newMessage]);
  };

  const handleLeaveRoom = () => {
    navigate('/');
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        <div className="chat-header-info">
          <h2 className="chat-room-name">#{decodedRoom}</h2>
          <span className="chat-username">Logged in as: {decodedUsername}</span>
        </div>
        <Button onClick={handleLeaveRoom} type="button">
          Leave Room
        </Button>
      </div>

      <div className="chat-content">
        <MessageList messages={messages} currentUsername={decodedUsername} />
      </div>

      <div className="chat-footer">
        <MessageInput onSendMessage={handleSendMessage} />
      </div>
    </div>
  );
};
