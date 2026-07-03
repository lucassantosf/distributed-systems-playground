import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Input } from '../../components/Input/Input';
import { Button } from '../../components/Button/Button';
import { JoinChatFormData } from '../../types/chat';

export const Home: React.FC = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<JoinChatFormData>({
    username: '',
    room: '',
  });

  const handleJoinChat = () => {
    if (formData.username.trim() && formData.room.trim()) {
      navigate(`/chat/${encodeURIComponent(formData.username)}/${encodeURIComponent(formData.room)}`);
    }
  };

  const isFormValid = formData.username.trim() !== '' && formData.room.trim() !== '';

  return (
    <div className="home-container">
      <div className="home-card">
        <h1 className="home-title">Join Chat</h1>
        <p className="home-subtitle">Enter your details to join a room</p>

        <div className="home-form">
          <Input
            label="Username"
            placeholder="Enter your username"
            value={formData.username}
            onChange={(value) => setFormData({ ...formData, username: value })}
          />

          <Input
            label="Room"
            placeholder="Enter room name"
            value={formData.room}
            onChange={(value) => setFormData({ ...formData, room: value })}
          />

          <Button
            onClick={handleJoinChat}
            disabled={!isFormValid}
            type="submit"
          >
            Join Chat
          </Button>
        </div>
      </div>
    </div>
  );
};
