const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080/api";

export async function fetchApi(path: string, options: RequestInit = {}) {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  if (response.status === 204) {
    return null;
  }

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || "Something went wrong");
  }

  return data;
}

export async function loginApi(username: string, password: string) {
  const params = new URLSearchParams();
  params.append("username", username);
  params.append("password", password);

  const response = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: params,
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || "Authentication failed");
  }

  return data; // { access_token, token_type }
}
