import axios from 'axios';

const baseURL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8008/api/v1';

export const api = axios.create({
  baseURL,
  timeout: 120000, // Increased to 120s
});

/**
 * Fetch-based POST for SSE streaming.
 * Axios doesn't support ReadableStream well in the browser.
 */
export const streamPost = async (url: string, data: FormData | Record<string, unknown>) => {
  const isFormData = data instanceof FormData;
  const response = await fetch(`${baseURL}${url}`, {
    method: 'POST',
    headers: isFormData ? {} : { 'Content-Type': 'application/json' },
    body: isFormData ? data : JSON.stringify(data),
  });
  
  if (!response.ok) {
    throw new Error(`Streaming request failed: ${response.statusText}`);
  }
  
  return response.body;
};
