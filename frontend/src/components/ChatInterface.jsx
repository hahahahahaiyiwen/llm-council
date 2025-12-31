import { useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import './ChatInterface.css';

const formatTime = (value) => {
  if (!value) return '';
  try {
    return new Date(value).toLocaleString();
  } catch (error) {
    return '';
  }
};

const buildMetadata = (raw) => {
  return raw
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((entry) => {
      const [key, ...rest] = entry.split('=');
      if (!key || rest.length === 0) {
        return null;
      }
      return { key: key.trim(), value: rest.join('=').trim() };
    })
    .filter(Boolean);
};

export default function ChatInterface({
  session,
  onStartSession,
  isRunning,
  apiMode = 'stream',
  onApiModeChange,
}) {
  const [problem, setProblem] = useState('');
  const [context, setContext] = useState('');
  const [numMembers, setNumMembers] = useState(3);
  const [timeoutSeconds, setTimeoutSeconds] = useState(120);
  const [roomType, setRoomType] = useState('original');
  const [metadataInput, setMetadataInput] = useState('');
  const [activeTab, setActiveTab] = useState('messages');
  const [isTabCollapsed, setIsTabCollapsed] = useState(false);
  const [expandedReasonEvents, setExpandedReasonEvents] = useState(() => new Set());

  const eventStreamEndRef = useRef(null);

  useEffect(() => {
    eventStreamEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [session?.events?.length, session?.deliverable, session?.status]);

  useEffect(() => {
    if (!session) {
      setActiveTab('messages');
      setIsTabCollapsed(false);
      setExpandedReasonEvents(new Set());
      return;
    }

    if (session.status === 'running') {
      setActiveTab('messages');
      setIsTabCollapsed(false);
    }
  }, [session, session?.status]);

  useEffect(() => {
    if (session?.deliverable) {
      setActiveTab('deliverable');
      setIsTabCollapsed(false);
    }
  }, [session?.deliverable]);

  useEffect(() => {
    setExpandedReasonEvents(new Set());
  }, [session?.id, session?.startedAt]);

  const sessionMetadata = useMemo(() => session?.request?.metadata ?? [], [session]);
  const selectedApiMode = apiMode ?? 'stream';

  const handleTabClick = (tab) => {
    if (tab === 'deliverable' && !session?.deliverable) {
      return;
    }

    if (tab === activeTab) {
      setIsTabCollapsed((previous) => !previous);
    } else {
      setActiveTab(tab);
      setIsTabCollapsed(false);
    }
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    const trimmedProblem = problem.trim();
    if (!trimmedProblem || isRunning) {
      return;
    }

    const request = {
      problem: trimmedProblem,
      context: context.trim() || null,
      metadata: buildMetadata(metadataInput),
      num_members: Number(numMembers) || 3,
      timeout_seconds: Number(timeoutSeconds) || 120,
      room_type: roomType,
    };

    onStartSession(request, selectedApiMode);
    setProblem('');
    setContext('');
    setMetadataInput('');
  };

  if (!session) {
    return (
      <div className="chat-interface">
        <div className="session-form-wrapper">
          <h2>Start a New Session</h2>
          <p className="session-form-description">
            Provide a problem statement and optional context. The council session will
            stream live updates and a final deliverable.
          </p>
          <form className="session-form" onSubmit={handleSubmit}>
            <label htmlFor="problem">Problem *</label>
            <textarea
              id="problem"
              className="message-input"
              value={problem}
              onChange={(event) => setProblem(event.target.value)}
              placeholder="Describe the problem for the council to solve"
              rows={6}
              required
              disabled={isRunning}
            />

            <label htmlFor="context">Context</label>
            <textarea
              id="context"
              className="message-input"
              value={context}
              onChange={(event) => setContext(event.target.value)}
              placeholder="Optional additional context"
              rows={4}
              disabled={isRunning}
            />

            <div className="session-form-row">
              <label htmlFor="num-members">Members</label>
              <input
                id="num-members"
                type="number"
                min={1}
                max={10}
                value={numMembers}
                onChange={(event) => setNumMembers(event.target.value)}
                disabled={isRunning}
              />

              <label htmlFor="timeout-seconds">Timeout (s)</label>
              <input
                id="timeout-seconds"
                type="number"
                min={30}
                value={timeoutSeconds}
                onChange={(event) => setTimeoutSeconds(event.target.value)}
                disabled={isRunning}
              />

              <label htmlFor="room-type">Room</label>
              <select
                id="room-type"
                value={roomType}
                onChange={(event) => setRoomType(event.target.value)}
                disabled={isRunning}
              >
                <option value="original">Original</option>
                <option value="round_robin">Round Robin</option>
              </select>
            </div>

            <label htmlFor="metadata">Metadata (key=value per line)</label>
            <textarea
              id="metadata"
              className="message-input"
              value={metadataInput}
              onChange={(event) => setMetadataInput(event.target.value)}
              placeholder="priority=high\ndeployment=staging"
              rows={3}
              disabled={isRunning}
            />

            <label htmlFor="api-mode">API Endpoint</label>
            <select
              id="api-mode"
              value={selectedApiMode}
              onChange={(event) => onApiModeChange?.(event.target.value)}
              disabled={isRunning}
            >
              <option value="stream">Streaming (/council/run)</option>
              <option value="async">Async polling (/council/start)</option>
            </select>
            <p className="session-form-hint">
              Streaming keeps a single connection open, while async polling periodically fetches updates from the
              operation status endpoint.
            </p>

            <button
              type="submit"
              className="send-button"
              disabled={!problem.trim() || isRunning}
            >
              Start Session
            </button>
          </form>
        </div>
      </div>
    );
  }

  const eventItems = session.events ?? [];
  const isMessagesTabActive = activeTab === 'messages';
  const isDeliverableTabActive = activeTab === 'deliverable';
  const showTabContent = !isTabCollapsed;
  const sessionTransport = session.transport ?? 'stream';
  const isPollingSession = sessionTransport === 'async';
  const runningMessage = isPollingSession
    ? 'Polling async operation...'
    : 'Streaming council events...';
  const toggleReasoning = (eventKey) => {
    setExpandedReasonEvents((previous) => {
      const next = new Set(previous);
      if (next.has(eventKey)) {
        next.delete(eventKey);
      } else {
        next.add(eventKey);
      }
      return next;
    });
  };

  const renderEventPayload = (event, eventKey) => {
    const payload = event?.payload;
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
      return (
        <pre className="event-payload">
          {JSON.stringify(payload ?? {}, null, 2)}
        </pre>
      );
    }

    const knownKeys = new Set(['member', 'timestamp', 'response', 'reasoning', 'message']);
    const additionalEntries = Object.entries(payload).filter(([key]) => !knownKeys.has(key));
    const isReasoningExpanded = expandedReasonEvents.has(eventKey);

    return (
      <div className="event-content">
        {payload.member && (
          <div className="event-member">
            <span className="event-member-label">Member</span>
            <span className="event-member-name">{payload.member}</span>
          </div>
        )}

        {payload.response && (
          <div className="event-section">
            <div className="event-section-title">Response</div>
            <div className="event-section-body">
              <ReactMarkdown>{payload.response}</ReactMarkdown>
            </div>
          </div>
        )}

        {payload.reasoning && (
          <div className="event-section reasoning">
            <div className="event-section-header">
              <div className="event-section-title">Reasoning</div>
              <button
                type="button"
                className="event-section-toggle"
                onClick={() => toggleReasoning(eventKey)}
              >
                {isReasoningExpanded ? 'Hide' : 'Show'} reasoning
              </button>
            </div>
            {isReasoningExpanded && (
              <div className="event-section-body">
                <ReactMarkdown>{payload.reasoning}</ReactMarkdown>
              </div>
            )}
          </div>
        )}

        {payload.message && (
          <div className="event-section subtle">
            <div className="event-section-title">Message</div>
            <div className="event-section-body">
              <ReactMarkdown>{payload.message}</ReactMarkdown>
            </div>
          </div>
        )}

        {additionalEntries.length > 0 && (
          <div className="event-extra">
            <div className="event-section-title">Details</div>
            <ul>
              {additionalEntries.map(([key, value]) => (
                <li key={key}>
                  <span className="metadata-key">{key}</span>: {' '}
                  {typeof value === 'string' ? value : JSON.stringify(value)}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="chat-interface">
      <div className="session-overview">
        <h2>Session Overview</h2>
        <div className="session-meta-row">
          <span className={`session-status status-${session.status}`}>
            Status: {session.status}
          </span>
          <span>Started: {formatTime(session.startedAt)}</span>
          {session.error && (
            <span className="session-error">Error: {session.error}</span>
          )}
        </div>

        <div className="session-problem-block">
          <h3>Problem</h3>
          <div className="markdown-content">
            <ReactMarkdown>{session.request.problem}</ReactMarkdown>
          </div>
        </div>

        {session.request.context && (
          <div className="session-context-block">
            <h3>Context</h3>
            <div className="markdown-content">
              <ReactMarkdown>{session.request.context}</ReactMarkdown>
            </div>
          </div>
        )}

        <div className="session-parameters">
          <div>Room Type: {session.request.room_type}</div>
          <div>Members: {session.request.num_members}</div>
          <div>Timeout: {session.request.timeout_seconds}s</div>
          <div>
            API: {isPollingSession ? 'Async polling (/council/start)' : 'Streaming (/council/run)'}
          </div>
        </div>

        {session.operationId && (
          <div className="session-operation-id">
            Operation ID: <span className="operation-id-value">{session.operationId}</span>
          </div>
        )}

        {sessionMetadata.length > 0 && (
          <div className="session-metadata">
            <h4>Metadata</h4>
            <ul>
              {sessionMetadata.map((item, index) => (
                <li key={`${item.key}-${index}`}>
                  <span className="metadata-key">{item.key}</span>: {item.value}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="session-panels">
        <div className="session-tabs">
          <button
            type="button"
            className={`session-tab ${isMessagesTabActive ? 'active' : ''} ${isMessagesTabActive && isTabCollapsed ? 'collapsed' : ''}`}
            onClick={() => handleTabClick('messages')}
          >
            <span>Events</span>
            <span className="tab-indicator">{isMessagesTabActive && isTabCollapsed ? '▸' : '▾'}</span>
          </button>
          <button
            type="button"
            className={`session-tab ${isDeliverableTabActive ? 'active' : ''} ${isDeliverableTabActive && isTabCollapsed ? 'collapsed' : ''}`}
            onClick={() => handleTabClick('deliverable')}
            disabled={!session.deliverable}
          >
            <span>Deliverable</span>
            <span className="tab-indicator">
              {!session.deliverable ? '⏳' : isDeliverableTabActive && isTabCollapsed ? '▸' : '▾'}
            </span>
          </button>
        </div>

        {showTabContent && isMessagesTabActive && (
          <div className="tab-panel messages-panel">
            <div className="tab-panel-header">
              {session.status === 'running' && (
                <div className="loading-indicator">
                  <div className="spinner"></div>
                  <span>{runningMessage}</span>
                </div>
              )}
            </div>
            {eventItems.length === 0 ? (
              <div className="empty-state">
                <h3>No events yet</h3>
                <p>The council session is preparing responses.</p>
              </div>
            ) : (
              eventItems.map((event, index) => {
                const eventKey = `${event.type}-${event.receivedAt ?? index}`;
                return (
                  <div key={eventKey} className="event-item">
                  <div className="event-header">
                    <span className="event-type">{event.type}</span>
                    <span className="event-timestamp">{formatTime(event.receivedAt)}</span>
                  </div>
                  {renderEventPayload(event, eventKey)}
                </div>
                );
              })
            )}
            <div ref={eventStreamEndRef} />
          </div>
        )}

        {showTabContent && isDeliverableTabActive && session.deliverable && (
          <div className="tab-panel deliverable-panel">
            <div className="tab-panel-header">
            </div>
            <div className="markdown-content">
              <ReactMarkdown>{session.deliverable}</ReactMarkdown>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
