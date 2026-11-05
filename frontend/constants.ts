const sameOrigin = import.meta.env.VITE_API_SAME_ORIGIN === 'true';
const BACKEND_URL = sameOrigin
  ? `${window.location.protocol}//${window.location.hostname}`
  : 'http://127.0.0.1';
const BACKEND_PORT = sameOrigin
  ? window.location.port || (window.location.protocol === 'https:' ? '443' : '80')
  : '8001';

export { BACKEND_URL, BACKEND_PORT };
