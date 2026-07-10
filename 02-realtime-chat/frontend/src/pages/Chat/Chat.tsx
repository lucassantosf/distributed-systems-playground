import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MessageList } from '../../features/chat/components/MessageList';
import { MessageInput } from '../../features/chat/components/MessageInput';
import { Message } from '../../types/message';
import { Button } from '../../components/Button/Button';

export const Chat: React.FC = () => {
  const navigate = useNavigate();
  const storedUsername = sessionStorage.getItem('chat.username') ?? 'Guest';
  const storedRoom = sessionStorage.getItem('chat.room') ?? 'general';

  const decodedUsername = storedUsername;
  const decodedRoom = storedRoom;

  const socketRef = useRef<WebSocket | null>(null);
  const pendingMessagesRef = useRef<string[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('connecting');
  const [activeUsers, setActiveUsers] = useState<string[]>([]);

  useEffect(() => {
    const loadHistory = async () => {
      try {
        const response = await fetch(`http://${window.location.hostname}:8000/history/${encodeURIComponent(decodedRoom)}`);
        if (!response.ok) {
          return;
        }

        const history = await response.json();
        const formattedHistory: Message[] = history.map((item: any) => ({
          id: String(item.id),
          username: item.username,
          content: item.content,
          timestamp: new Date(item.created_at).toLocaleTimeString('pt-BR', {
            hour: '2-digit',
            minute: '2-digit',
          }),
        }));

        setMessages(formattedHistory);
      } catch (error) {
        console.error('Failed to load room history', error);
      }
    };

    void loadHistory();

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

      const separatorIndex = messageText.indexOf(': ');
      const sender = separatorIndex >= 0 ? messageText.slice(0, separatorIndex) : 'Server';
      const content = separatorIndex >= 0 ? messageText.slice(separatorIndex + 2) : messageText;

      const newMessage: Message = {
        id: `${Date.now()}-${Math.random()}`,
        username: sender,
        content,
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
    sessionStorage.removeItem('chat.username');
    sessionStorage.removeItem('chat.room');
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
