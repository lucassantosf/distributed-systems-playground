import { createBrowserRouter } from 'react-router-dom';
import { Home } from '../pages/Home/Home';
import { Chat } from '../pages/Chat/Chat';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Home />,
  },
  {
    path: '/chat/:username/:room',
    element: <Chat />,
  },
]);
