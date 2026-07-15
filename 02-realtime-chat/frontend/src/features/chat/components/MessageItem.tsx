import React from 'react';
import { Message } from '../../../types/message';

interface MessageItemProps {
  message: Message;
  isOwnMessage?: boolean;
}

export const MessageItem: React.FC<MessageItemProps> = ({
  message,
  isOwnMessage = false,
}) => {
  if (message.username === 'System') {
    return (
      <div className="message-system">
        {message.content}
      </div>
    );
  }

  return (
    <div className={`message-item ${isOwnMessage ? 'message-own' : 'message-other'}`}>
      <div className="message-header">
        <span className="message-username">{message.username}</span>
        <span className="message-timestamp">{message.timestamp}</span>
      </div>
      <div className="message-content">{message.content}</div>
    </div>
  );
};
