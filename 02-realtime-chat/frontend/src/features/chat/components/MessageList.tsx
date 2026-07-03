import React from 'react';
import { Message } from '../../../types/message';
import { MessageItem } from './MessageItem';

interface MessageListProps {
  messages: Message[];
  currentUsername?: string;
}

export const MessageList: React.FC<MessageListProps> = ({
  messages,
  currentUsername,
}) => {
  return (
    <div className="message-list">
      {messages.map((message) => (
        <MessageItem
          key={message.id}
          message={message}
          isOwnMessage={message.username === currentUsername}
        />
      ))}
    </div>
  );
};
