import React, { useEffect, useRef, useState } from 'react';
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

  const socketRef = useRef<WebSocket | null>(null);
  const pendingMessagesRef = useRef<string[]>([]);
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
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('connecting');
  const [activeUsers, setActiveUsers] = useState<string[]>([]);

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new WebSocket(`${protocol}//${window.location.hostname}:8000/ws/${encodeURIComponent(decodedRoom)}/${encodeURIComponent(decodedUsername)}`);
    socketRef.current = socket;
    setConnectionStatus('connecting');

    socket.addEventListener('open', () => {
      setConnectionStatus('connected');
      while (pendingMessagesRef.current.length > 0) {
        const pendingMessage = pendingMessagesRef.current.shift();
        if (pendingMessage) {
          socket.send(pendingMessage);
        }
      }
    });

    socket.addEventListener('message', (event) => {
      const messageText = event.data;
      if (messageText.startsWith('Active users:')) {
        const users = messageText.replace('Active users:', '').split(',').map((user) => user.trim()).filter(Boolean);
        setActiveUsers(users);
        return;
      }

      const newMessage: Message = {
        id: `${Date.now()}-${Math.random()}`,
        username: 'Server',
        content: messageText,
        timestamp: new Date().toLocaleTimeString('pt-BR', {
          hour: '2-digit',
          minute: '2-digit',
        }),
      };
      setMessages((currentMessages) => [...currentMessages, newMessage]);
    });

    socket.addEventListener('close', () => {
      setConnectionStatus('disconnected');
    });

    socket.addEventListener('error', () => {
      setConnectionStatus('error');
    });

    return () => {
      socket.close();
      socketRef.current = null;
    };
  }, [decodedRoom, decodedUsername]);

  const handleSendMessage = (content: string) => {
    const socket = socketRef.current;
    console.log('sending message', { content, readyState: socket?.readyState, status: connectionStatus });

    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(content);
    } else {
      pendingMessagesRef.current.push(content);
      console.warn('WebSocket is not open; queued message', socket?.readyState);
    }
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
          <span className="chat-username">Socket: {connectionStatus}</span>
        </div>
        <Button onClick={handleLeaveRoom} type="button">
          Leave Room
        </Button>
      </div>

      <div className="chat-content">
        <div style={{ padding: '0.75rem 1rem', borderBottom: '1px solid #e5e7eb' }}>
          <strong>Active users:</strong> {activeUsers.length > 0 ? activeUsers.join(', ') : 'None'}
        </div>
        <MessageList messages={messages} currentUsername={decodedUsername} />
      </div>

      <div className="chat-footer">
        <MessageInput onSendMessage={handleSendMessage} disabled={connectionStatus !== 'connected'} />
      </div>
    </div>
  );
};
