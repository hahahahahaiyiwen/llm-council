import './Sidebar.css';

const statusLabels = {
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
};

const getSessionTitle = (session) => {
  const problem = session?.request?.problem ?? '';
  const firstLine = problem.split('\n')[0].trim();
  return firstLine || 'Untitled Session';
};

export default function Sidebar({
  sessions,
  currentSessionId,
  onSelectSession,
  onNewSession,
  isRunning,
}) {
  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h1>LLM Council</h1>
        <button
          className="new-conversation-btn"
          onClick={onNewSession}
          disabled={isRunning}
        >
          + New Session
        </button>
      </div>

      <div className="conversation-list">
        {sessions.length === 0 ? (
          <div className="no-conversations">No sessions yet</div>
        ) : (
          sessions.map((session) => (
            <div
              key={session.id}
              className={`conversation-item ${
                session.id === currentSessionId ? 'active' : ''
              }`}
              onClick={() => onSelectSession(session.id)}
            >
              <div className="conversation-title">{getSessionTitle(session)}</div>
              <div className="conversation-meta">
                {statusLabels[session.status] || 'Unknown'} ·{' '}
                {new Date(session.startedAt).toLocaleTimeString()}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
