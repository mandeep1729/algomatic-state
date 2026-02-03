import { USE_MOCKS } from '../mocks/enable';
import * as mockApi from '../mocks/mockApi';
import * as realApi from './client';

const api = USE_MOCKS ? mockApi : realApi;
export default api;
