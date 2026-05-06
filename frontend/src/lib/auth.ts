export interface UserSession {
  email: string;
  uuid: string;
  role: 'user' | 'admin';
}

export function getCurrentUser(): UserSession | null {
  if (typeof window === 'undefined') return null;
  const session = localStorage.getItem("sugarcane_user");
  if (!session) return null;
  try {
    return JSON.parse(session);
  } catch {
    return null;
  }
}

export function logout() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem("sugarcane_user");
  window.location.href = "/login";
}
