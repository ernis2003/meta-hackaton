import { BACKEND_URL, BACKEND_PORT } from '../../constants';

export type AuthResponse = {
  success: boolean;
  access_token: string;
  token_type: string;
  user: { id: string; email: string; role: 'user' | 'admin' };
};

export type SignupData = {
  name: string;
  surname: string;
  email: string;
  organization: string;
  password: string;
};

export async function fetchAPI<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok) {
    const detail = result.detail;
    throw new Error(
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((item: { msg: string }) => item.msg).join('. ')
          : 'Request failed. Please try again.',
    );
  }
  return result as T;
}

async function authenticate(path: string, data: unknown): Promise<AuthResponse> {
  const result = await fetchAPI<AuthResponse>(`${BACKEND_URL}:${BACKEND_PORT}/api/${path}`, data);
  sessionStorage.setItem('access_token', result.access_token);
  sessionStorage.setItem('user_role', result.user.role);
  return result;
}

export function userSignUpAuth(data: SignupData) {
  return authenticate('signup', data);
}

export function userLoginAuth(email: string, password: string) {
  return authenticate('login', { email, password });
}

export function clearAuth() {
  sessionStorage.removeItem('access_token');
  sessionStorage.removeItem('user_role');
}
