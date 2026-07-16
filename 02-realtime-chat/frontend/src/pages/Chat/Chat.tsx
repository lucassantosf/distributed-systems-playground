import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MessageList } from '../../features/chat/components/MessageList';
import { MessageInput } from '../../features/chat/components/MessageInput';
import { Message } from '../../types/message';
import { Button } from '../../components/Button/Button';

const MAX_RECONNECT_ATTEMPTS = 10;
const RECONNECT_DELAY = 3_000;

export const Chat: React.FC = () => {
  const navigate = useNavigate();
  const storedUsername = sessionStorage.getItem('chat.username') ?? 'Guest';
  const storedRoom = sessionStorage.getItem('chat.room') ?? 'general';

  const decodedUsername = storedUsername;
  const decodedRoom = storedRoom;

  const socketRef = useRef<WebSocket | null>(null);
  const pendingMessagesRef = useRef<string[]>([]);
  const chatContentRef = useRef<HTMLDivElement>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectingRef = useRef(false);
  const intentionalCloseRef = useRef(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'reconnecting' | 'disconnected'>('connecting');
  const [reconnectAttempt, setReconnectAttempt] = useState(0);
  const [activeUsers, setActiveUsers] = useState<string[]>([]);

  const connectSocket = useCallback(() => {
    reconnectingRef.current = false;
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new WebSocket(`${protocol}//${window.location.hostname}:8000/ws/${encodeURIComponent(decodedRoom)}/${encodeURIComponent(decodedUsername)}`);
    socketRef.current = socket;

    if (reconnectAttemptsRef.current > 0) {
      setConnectionStatus('reconnecting');
    } else {
      setConnectionStatus('connecting');
    }

    socket.addEventListener('open', () => {
      setConnectionStatus('connected');
      reconnectingRef.current = false;
      reconnectAttemptsRef.current = 0;
      setReconnectAttempt(0);
      while (pendingMessagesRef.current.length > 0) {
        const pendingMessage = pendingMessagesRef.current.shift();
        if (pendingMessage) {
          socket.send(pendingMessage);
        }
      }
    });

    socket.addEventListener('message', (event) => {
      const messageText = event.data;

      try {
        const data = JSON.parse(messageText);
        if (data.type === 'ping') {
          socket.send(JSON.stringify({ type: 'pong' }));
          return;
        }
      } catch {
        // not JSON, continue with regular parsing
      }

      if (messageText.startsWith('Active users:')) {
        const users = messageText
          .replace('Active users:', '')
          .split(',')
          .map((user) => user.trim())
          .filter(Boolean);
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
      setMessages((currentMessages) => {
        const alreadyPresent = currentMessages.some((message) => message.content === content && message.username === sender && message.timestamp === newMessage.timestamp);
        if (alreadyPresent) {
          return currentMessages;
        }
        return [...currentMessages, newMessage];
      });
    });

    socket.addEventListener('close', () => {
      if (!intentionalCloseRef.current) {
        scheduleReconnect();
      }
    });

    socket.addEventListener('error', () => {
      if (!intentionalCloseRef.current) {
        scheduleReconnect();
      }
    });
  }, [decodedRoom, decodedUsername]);

  const scheduleReconnect = useCallback(() => {
    if (reconnectingRef.current) {
      return;
    }

    if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
      setConnectionStatus('disconnected');
      return;
    }

    reconnectingRef.current = true;
    reconnectAttemptsRef.current += 1;
    setReconnectAttempt(reconnectAttemptsRef.current);
    setConnectionStatus('reconnecting');

    reconnectTimerRef.current = setTimeout(() => {
      connectSocket();
    }, RECONNECT_DELAY);
  }, [connectSocket]);

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
    connectSocket();

    return () => {
      intentionalCloseRef.current = true;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, [decodedRoom, decodedUsername, connectSocket]);

  useEffect(() => {
    const container = chatContentRef.current;
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }, [messages]);

  const handleSendMessage = (content: string) => {
    const socket = socketRef.current;
    const optimisticMessage: Message = {
      id: `local-${Date.now()}`,
      username: decodedUsername,
      content,
      timestamp: new Date().toLocaleTimeString('pt-BR', {
        hour: '2-digit',
        minute: '2-digit',
      }),
    };

    setMessages((currentMessages) => [...currentMessages, optimisticMessage]);

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
        </div>
        <Button onClick={handleLeaveRoom} type="button">
          Leave Room
        </Button>
      </div>

      {connectionStatus !== 'connected' && (
        <div className={`connection-banner ${connectionStatus === 'disconnected' ? 'banner-error' : 'banner-reconnecting'}`}>
          {connectionStatus === 'connecting' && 'Connecting...'}
          {connectionStatus === 'reconnecting' && `Reconnecting... (attempt ${reconnectAttempt}/${MAX_RECONNECT_ATTEMPTS})`}
          {connectionStatus === 'disconnected' && 'Connection lost. Refresh the page.'}
        </div>
      )}

      <div className="chat-content" ref={chatContentRef}>
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
