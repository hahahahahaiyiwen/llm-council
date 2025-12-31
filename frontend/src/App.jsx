import { useEffect, useMemo, useRef, useState } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import { api } from './api';
import './App.css';

const POLL_INTERVAL_MS = 2000;

function App() {
  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [isRunning, setIsRunning] = useState(false);
  const [apiMode, setApiMode] = useState('stream');
  const pollersRef = useRef(new Map());

  const currentSession = useMemo(
    () => sessions.find((session) => session.id === currentSessionId) ?? null,
    [sessions, currentSessionId]
  );

  useEffect(() => {
    return () => {
      pollersRef.current.forEach((timeoutId) => clearTimeout(timeoutId));
      pollersRef.current.clear();
    };
  }, []);

  const updateSession = (sessionId, updater) => {
    setSessions((prev) =>
      prev.map((session) =>
        session.id === sessionId ? updater(session) : session
      )
    );
  };

  const stopPollingOperation = (operationId) => {
    const timeoutId = pollersRef.current.get(operationId);
    if (timeoutId) {
      clearTimeout(timeoutId);
      pollersRef.current.delete(operationId);
    }
  };

  // Polls backend async operations and mirrors their state into the UI.
  const startPollingOperation = (sessionId, operationId) => {
    const poll = async () => {
      try {
        const operation = await api.getOperationStatus(operationId);

        updateSession(sessionId, (session) => {
          if (!session) {
            return session;
          }

          const existingEvents = session.events ?? [];
          const incomingEvents = operation.events ?? [];
          let nextEvents = existingEvents;

          if (incomingEvents.length > existingEvents.length) {
            const appended = incomingEvents
              .slice(existingEvents.length)
              .map((event) => ({
                ...event,
                receivedAt:
                  event.payload?.timestamp ?? new Date().toISOString(),
              }));
            nextEvents = [...existingEvents, ...appended];
          } else if (incomingEvents.length < existingEvents.length) {
            nextEvents = incomingEvents.map((event, index) => ({
              ...event,
              receivedAt:
                event.payload?.timestamp ?? existingEvents[index]?.receivedAt ?? new Date().toISOString(),
            }));
          } else if (
            incomingEvents.length === existingEvents.length &&
            incomingEvents.some((event, index) => {
              const existing = existingEvents[index];
              return (
                !existing ||
                existing.type !== event.type ||
                JSON.stringify(existing.payload) !== JSON.stringify(event.payload)
              );
            })
          ) {
            nextEvents = incomingEvents.map((event, index) => ({
              ...event,
              receivedAt:
                existingEvents[index]?.receivedAt ??
                event.payload?.timestamp ??
                new Date().toISOString(),
            }));
          }

          return {
            ...session,
            events: nextEvents,
            deliverable: operation.deliverable ?? session.deliverable,
            status: operation.status ?? session.status,
            error: operation.error ?? session.error,
            operationId,
          };
        });

        if (operation.status === 'running') {
          const timeoutId = setTimeout(poll, POLL_INTERVAL_MS);
          pollersRef.current.set(operationId, timeoutId);
        } else {
          stopPollingOperation(operationId);
          setIsRunning(false);
        }
      } catch (error) {
        console.error('Failed to poll async operation:', error);
        updateSession(sessionId, (session) => ({
          ...session,
          status: 'failed',
          error: error?.message ?? 'Failed to poll async operation.',
        }));
        stopPollingOperation(operationId);
        setIsRunning(false);
      }
    };

    stopPollingOperation(operationId);
    poll();
  };

  const handleStartSession = async (request, mode = 'stream') => {
    if (!request?.problem?.trim()) {
      return;
    }

    const sessionId = (typeof crypto !== 'undefined' && 'randomUUID' in crypto)
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;

    const newSession = {
      id: sessionId,
      request,
      startedAt: new Date().toISOString(),
      events: [],
      deliverable: null,
      status: 'running',
      error: null,
      transport: mode,
      operationId: null,
    };

    setSessions((prev) => [newSession, ...prev]);
    setCurrentSessionId(sessionId);
    setIsRunning(true);

    if (mode === 'async') {
      try {
        const operation = await api.startAsyncSession(request);
        if (!operation?.id) {
          throw new Error('Async API did not return an operation id.');
        }

        updateSession(sessionId, (session) => ({
          ...session,
          operationId: operation.id,
          status: operation.status ?? session.status,
        }));

        startPollingOperation(sessionId, operation.id);
      } catch (error) {
        console.error('Failed to start async council session:', error);
        updateSession(sessionId, (session) => ({
          ...session,
          status: 'failed',
          error: error?.message ?? 'Failed to start async session.',
        }));
        setIsRunning(false);
      }
      return;
    }

    try {
      await api.runSessionStream(request, (chunk) => {
        if (!chunk || typeof chunk !== 'object') {
          return;
        }

        if (chunk.kind === 'room_event' && chunk.event) {
          updateSession(sessionId, (session) => ({
            ...session,
            events: [
              ...session.events,
              {
                ...chunk.event,
                receivedAt: new Date().toISOString(),
              },
            ],
          }));
          return;
        }

        if (chunk.kind === 'deliverable') {
          updateSession(sessionId, (session) => ({
            ...session,
            deliverable: chunk.deliverable ?? null,
            status: 'completed',
          }));
          return;
        }

        if (chunk.kind === 'error') {
          updateSession(sessionId, (session) => ({
            ...session,
            status: 'failed',
            error: chunk.detail ?? 'Session failed with an unknown error.',
          }));
        }
      });

      updateSession(sessionId, (session) => ({
        ...session,
        status: session.status === 'running' ? 'completed' : session.status,
      }));
    } catch (error) {
      console.error('Failed to run council session:', error);
      updateSession(sessionId, (session) => ({
        ...session,
        status: 'failed',
        error: error?.message ?? 'Failed to run session.',
      }));
    } finally {
      setIsRunning(false);
    }
  };

  const handleSelectSession = (sessionId) => {
    setCurrentSessionId(sessionId);
  };

  const handleShowNewSessionForm = () => {
    setCurrentSessionId(null);
  };

  return (
    <div className="app">
      <Sidebar
        sessions={sessions}
        currentSessionId={currentSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleShowNewSessionForm}
        isRunning={isRunning}
      />
      <ChatInterface
        session={currentSession}
        onStartSession={handleStartSession}
        isRunning={isRunning}
        apiMode={apiMode}
        onApiModeChange={setApiMode}
      />
    </div>
  );
}

export default App;
