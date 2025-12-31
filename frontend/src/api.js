/**
 * API client for the LLM Council backend.
 */

const API_BASE = 'http://localhost:8080';

export const api = {
  /**
   * Run a council session and stream responses from the backend.
   * @param {object} request - The council request payload.
   * @param {(chunk: object) => void} onChunk - Callback for each streamed JSON line.
   * @param {AbortSignal} [signal] - Optional abort signal.
   */
  async runSessionStream(request, onChunk, signal) {
    const response = await fetch(`${API_BASE}/council/run`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
      signal,
    });

    if (!response.ok || !response.body) {
      throw new Error('Failed to start council session');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) {
          continue;
        }

        try {
          const parsed = JSON.parse(trimmed);
          onChunk(parsed);
        } catch (error) {
          console.error('Failed to parse streamed JSON line:', { line: trimmed, error });
        }
      }
    }

    const trailing = buffer.trim();
    if (trailing) {
      try {
        const parsed = JSON.parse(trailing);
        onChunk(parsed);
      } catch (error) {
        console.error('Failed to parse trailing JSON line:', { line: trailing, error });
      }
    }
  },

  /**
   * Start an async council session and receive an operation descriptor.
   * @param {object} request - The council request payload.
   * @returns {Promise<object>} - The async operation response.
   */
  async startAsyncSession(request) {
    const response = await fetch(`${API_BASE}/council/start`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error('Failed to start async council session');
    }

    return response.json();
  },

  /**
   * Fetch the latest status for an async council operation.
   * @param {string} operationId - The async operation identifier.
   * @returns {Promise<object>} - The operation status payload.
   */
  async getOperationStatus(operationId) {
    const response = await fetch(`${API_BASE}/council/operations/${operationId}`);

    if (!response.ok) {
      throw new Error('Failed to retrieve async operation status');
    }

    return response.json();
  },
};
