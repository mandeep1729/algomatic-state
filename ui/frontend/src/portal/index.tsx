import { RouterProvider } from 'react-router-dom';
import { router } from './routes';

export default function Portal() {
  return <RouterProvider router={router} />;
}
