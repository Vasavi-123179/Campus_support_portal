import { useEffect, useState } from 'react';
import { api } from './api';

import {
  AlertTriangle,
  Bell,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Download,
  Filter,
  Gauge,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquare,
  Paperclip,
  Plus,
  Search,
  Settings,
  ShieldCheck,
  Ticket,
  UserRound,
  Users,
  X,
  Zap,
} from 'lucide-react';

type User = {
  userId: string;
  name: string;
  department: string;
  role: string;
  teamName?: string;
};
type TicketRow = Record<string, any>;

const statuses = [
  'New',
  'Assigned',
  'In Progress',
  'Pending',
  'Resolved',
  'Closed',
  'Escalated',
];
const priorities = ['Low', 'Medium', 'High', 'Critical'];

function App() {
  const [sessionToken, setSessionToken] = useState(
    () => sessionStorage.getItem('facultyhelp_session') || ''
  );
  const [user, setUser] = useState<User | null>(null);
  const [page, setPage] = useState('dashboard');
  const [login, setLogin] = useState({ userId: '', password: '' });
  const [loginError, setLoginError] = useState('');
  const [loading, setLoading] = useState(false);
  const [bootstrap, setBootstrap] = useState<any>(null);
  const [tickets, setTickets] = useState<TicketRow[]>([]);
  const [selected, setSelected] = useState<TicketRow | null>(null);
  const [toast, setToast] = useState('');
  const [mobileNav, setMobileNav] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  const call = async (path: string, data: any = {}) => {
    const res = await api.post(path, { ...data, sessionToken });
    if (res.data?.message && res.data?.statusCode >= 400)
      throw new Error(res.data.message);
    return res.data;
  };

  const load = async (u = user) => {
    if (!sessionToken || !u) return;
    try {
      const data = await call('/api/bootstrap');
      setBootstrap(data);
      const list = await call('/api/tickets/list');
      setTickets(list.tickets || []);
    } catch (e: any) {
      if (String(e.message).toLowerCase().includes('unauthorized')) logout();
      else setToast(e.message || 'Unable to load data');
    }
  };

  useEffect(() => {
    if (!sessionToken) return;
    (async () => {
      try {
        const data = await api.post('/api/bootstrap', { sessionToken });
        setUser(data.data.user);
        setBootstrap(data.data);
        const list = await api.post('/api/tickets/list', { sessionToken });
        setTickets(list.data.tickets || []);
      } catch {
        sessionStorage.removeItem('facultyhelp_session');
        setSessionToken('');
      }
    })();
  }, [sessionToken]);

  useEffect(() => {
    if (!sessionToken) return;
    api.post('/api/notifications/list', { sessionToken }).then((res) => {
      setUnreadCount((res.data.notifications || []).filter((n: any) => !n.read).length);
    }).catch(() => setUnreadCount(0));
  }, [sessionToken, page]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(''), 3200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const logout = async () => {
    try {
      if (sessionToken) await api.post('/api/auth/logout', { sessionToken });
    } catch {}
    sessionStorage.removeItem('facultyhelp_session');
    setSessionToken('');
    setUser(null);
    setBootstrap(null);
    setTickets([]);
    setPage('dashboard');
  };

  const signIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError('');
    setLoading(true);
    try {
      const res = await api.post('/api/auth/login', login);
      if (!res.data?.sessionToken)
        throw new Error(res.data?.message || 'Sign in failed');
      sessionStorage.setItem('facultyhelp_session', res.data.sessionToken);
      setSessionToken(res.data.sessionToken);
      setUser(res.data.user);
      setLogin({ userId: '', password: '' });
    } catch (e: any) {
      setLoginError(e.message || 'Invalid credentials');
    } finally {
      setLoading(false);
    }
  };

  if (!user)
    return (
      <Login
        login={login}
        setLogin={setLogin}
        error={loginError}
        loading={loading}
        onSubmit={signIn}
      />
    );

  const refresh = async () => {
    await load();
    setToast('Data refreshed');
  };

  const openTicket = async (token: string) => {
    try {
      const data = await call('/api/tickets/detail', { token });
      setSelected(data.ticket);
      setPage('ticket-detail');
    } catch (e: any) {
      setToast(e.message || 'Unable to open ticket');
    }
  };

  const nav =
    user.role === 'Faculty'
      ? [
          ['dashboard', 'Dashboard', LayoutDashboard],
          ['tickets', 'My Tickets', Ticket],
          ['shared-issues', 'Campus Issues', Users],
          ['new', 'New Ticket', Plus],
          ['notifications', 'Notifications', Bell],
          ['profile', 'Profile', UserRound],
        ]
      : user.role === 'Team Member'
        ? [
            ['dashboard', 'Dashboard', LayoutDashboard],
            ['team-queue', 'Team Queue', Ticket],
            ['assigned', 'Assigned to Me', UserRound],
            ['escalated', 'Escalated', AlertTriangle],
            ['reports', 'Reports', Gauge],
            ['profile', 'Profile', UserRound],
          ]
        : [
            ['dashboard', 'Dashboard', LayoutDashboard],
            ['admin-tickets', 'Tickets', Ticket],
            ['users', 'Users', Users],
            ['teams', 'Teams', Users],
            ['categories', 'Categories', Settings],
            ['routing', 'Routing Rules', Zap],
            ['sla', 'SLA Settings', Clock3],
            ['locations', 'Locations', Settings],
            ['access-requests', 'Access Requests', Users],
            ['reports', 'Reports', Gauge],
            ['notifications', 'Notifications', Bell],
            ['profile', 'Profile', UserRound],
          ];

  return (
    <div className="shell">
      <header className="topbar">
        <button
          className="mobile-menu"
          onClick={() => setMobileNav(!mobileNav)}
        >
          <Menu size={20} />
        </button>
        <div className="brand">
          <div className="brand-mark">F</div>
          <div>
            <strong>FacultyHelp</strong>
            <span>Faculty Ticketing System</span>
          </div>
        </div>
        <div className="top-actions">
          <button
            className="icon-btn"
            onClick={() => setPage('notifications')}
            aria-label="Notifications"
          >
            <Bell size={19} />
            <span className="dot">{unreadCount}</span>
          </button>
          <div className="identity">
            <div className="avatar">{user.name.slice(0, 1)}</div>
            <div>
              <b>{user.name}</b>
              <span>
                {user.role}
                {user.teamName ? ` · ${user.teamName}` : ''}
              </span>
            </div>
          </div>
          <button className="logout" onClick={logout}>
            <LogOut size={17} /> Logout
          </button>
        </div>
      </header>
      <div className="body">
        <aside className={`sidebar ${mobileNav ? 'open' : ''}`}>
          <div className="side-role">
            <ShieldCheck size={16} />
            <span>{user.role}</span>
          </div>
          {nav.map(([key, label, Icon]: any) => (
            <button
              key={key}
              className={page === key ? 'nav active' : 'nav'}
              onClick={() => {
                setPage(key);
                setMobileNav(false);
              }}
            >
              <Icon size={18} />
              <span>{label}</span>
              {key === 'notifications' && unreadCount > 0 && (
                <em>{unreadCount}</em>
              )}
            </button>
          ))}
        </aside>
        <main className="main">
          {page === 'dashboard' && (
            <Dashboard
              user={user}
              data={bootstrap}
              tickets={tickets}
              openTicket={openTicket}
              refresh={refresh}
            />
          )}
          {page === 'tickets' && (
            <TicketList tickets={tickets.filter(t => t.facultyId === user.userId)} openTicket={openTicket} faculty />
          )}
          {page === 'shared-issues' && (
            <SharedIssues
              tickets={tickets.filter(t => t.shared !== false && t.facultyId !== user.userId)}
              openTicket={openTicket}
              call={call}
              refresh={load}
            />
          )}
          {page === 'team-queue' && (
            <TicketList tickets={tickets} openTicket={openTicket} team />
          )}
          {page === 'assigned' && (
            <TicketList
              tickets={tickets.filter(t => t.assignedTo === user.userId)}
              openTicket={openTicket}
              team
            />
          )}
          {page === 'escalated' && (
            <TicketList
              tickets={tickets.filter(t => t.status === 'Escalated')}
              openTicket={openTicket}
              team
            />
          )}
          {page === 'admin-tickets' && (
            <TicketList tickets={tickets} openTicket={openTicket} admin />
          )}
          {page === 'new' && (
            <NewTicket
              bootstrap={bootstrap}
              call={call}
              onCreated={async (token: string) => {
                await load();
                await openTicket(token);
              }}
            />
          )}
          {page === 'ticket-detail' && selected && (
            <TicketDetail
              ticket={selected}
              user={user}
              call={call}
              onBack={() =>
                setPage(
                  user.role === 'Faculty'
                    ? 'tickets'
                    : user.role === 'Team Member'
                      ? 'team-queue'
                      : 'admin-tickets'
                )
              }
              onChanged={async () => {
                await load();
                if (selected) {
                  const d = await call('/api/tickets/detail', {
                    token: selected.token,
                  });
                  setSelected(d.ticket);
                }
              }}
            />
          )}
          {page === 'notifications' && <Notifications call={call} />}
          {page === 'profile' && <Profile user={user} tickets={tickets} onNavigate={setPage} />}
          {page === 'access-requests' && <AccessRequests call={call} />}
          {[
            'users',
            'teams',
            'categories',
            'routing',
            'sla',
            'locations',
          ].includes(page) && <AdminResource page={page} call={call} />}
          {page === 'reports' && <Reports call={call} user={user} />}
        </main>
      </div>
      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}

function Login({ login, setLogin, error, loading, onSubmit }: any) {
  const [role, setRole] = useState<'Faculty' | 'Team Member' | 'Administrator'>('Faculty');
  const [options, setOptions] = useState<any>({ faculty: [], teams: [] });
  const [showSignup, setShowSignup] = useState(false);
  const [optionsError, setOptionsError] = useState('');

  useEffect(() => {
    api.post('/api/auth/options')
      .then((res: any) => setOptions(res.data || { faculty: [], teams: [] }))
      .catch(() => setOptionsError('Unable to load account list.'));
  }, []);

  const chooseRole = (next: 'Faculty' | 'Team Member' | 'Administrator') => {
    setRole(next);
    setLogin({ userId: '', password: '' });
  };

  const selectAccount = (userId: string) => {
    setLogin({ ...login, userId });
  };

  const roleCards = [
    {
      key: 'Faculty' as const,
      title: 'Faculty',
      Icon: UserRound,
    },
    {
      key: 'Team Member' as const,
      title: 'Team Member',
      Icon: Users,
    },
    {
      key: 'Administrator' as const,
      title: 'Administrator',
      Icon: ShieldCheck,
    },
  ];

  return (
    <div className="login-page">
      <header className="login-topbar">
        <div className="login-topbar-inner">
          <div className="login-header-brand">
            <div className="login-header-mark">F</div>
            <div>
              <strong>FacultyHelp</strong>
              <span>Faculty Ticketing System</span>
            </div>
          </div>
          <div className="login-campus-badge">@Ashokacollege.in</div>
        </div>
      </header>

      <main className="login-content">
        <section className="login-intro">
          <span className="login-eyebrow">CAMPUS SUPPORT PORTAL</span>
        </section>

        <section className="login-role-cards" aria-label="Sign in options">
          {roleCards.map(({ key, title, Icon }) => (
            <button
              key={key}
              type="button"
              className={role === key ? 'login-role-card selected' : 'login-role-card'}
              onClick={() => chooseRole(key)}
              aria-pressed={role === key}
            >
              <span className="login-role-icon"><Icon size={22} /></span>
              <span className="login-role-copy">
                <strong>{title}</strong>
              </span>
              {role === key && <CheckCircle2 className="login-role-check" size={19} />}
            </button>
          ))}
        </section>

        <section className="login-form-card">
          <div className="login-form-heading">
            <div>
              <span className="login-form-kicker">SECURE SIGN IN</span>
              <h2>{role} sign in</h2>
              <p>
                {role === 'Faculty'
                  ? 'Select your faculty account and enter your password.'
                  : role === 'Team Member'
                    ? 'Select your team account and enter your password.'
                    : 'Enter the administrator account ID and password.'}
              </p>
            </div>
            <div className="login-secure-mark"><ShieldCheck size={20} /></div>
          </div>

          {role === 'Faculty' && (
            <label className="account-picker">
              Select Faculty ID
              <select value={login.userId} onChange={e => selectAccount(e.target.value)}>
                <option value="">Select faculty ID</option>
                {options.faculty.map((u: any) => (
                  <option key={u.userId} value={u.userId}>{u.userId} — {u.name}</option>
                ))}
              </select>
            </label>
          )}

          {role === 'Team Member' && (
            <label className="account-picker">
              Select Team Member
              <select value={login.userId} onChange={e => selectAccount(e.target.value)}>
                <option value="">Select team member</option>
                {options.teams.map((u: any) => (
                  <option key={u.userId} value={u.userId}>{u.userId} — {u.name} · {u.teamName}</option>
                ))}
              </select>
            </label>
          )}

          {role === 'Administrator' && (
            <div className="admin-signin-note">
              <ShieldCheck size={18} />
              <span>Administrator access is protected. Enter the account ID and password manually.</span>
            </div>
          )}

          {optionsError && <div className="form-error">{optionsError}</div>}

          <form onSubmit={onSubmit}>
            <label>
              {role === 'Faculty' ? 'Faculty ID' : 'User ID'}
              <input
                value={login.userId}
                onChange={e => setLogin({ ...login, userId: e.target.value })}
                autoComplete="username"
                readOnly={role !== 'Administrator' && !!login.userId}
                placeholder={role === 'Administrator' ? 'Enter administrator ID' : 'Select an account above'}
              />
            </label>

            <label>
              Password
              <input
                type="password"
                value={login.password}
                onChange={e => setLogin({ ...login, password: e.target.value })}
                autoComplete="current-password"
                placeholder="Enter password"
              />
            </label>

            {error && <div className="form-error">{error}</div>}

            <button className="primary wide login-submit" disabled={loading || !login.userId}>
              {loading ? 'Signing in…' : 'Sign In'}
            </button>
          </form>

          {role === 'Faculty' && (
            <div className="signup-area login-signup">
              <div>
                <strong>New faculty?</strong>
                <small>Request access from the administrator.</small>
              </div>
              <button type="button" className="secondary login-signup-button" onClick={() => setShowSignup(true)}>
                Sign Up
              </button>
            </div>
          )}
        </section>
      </main>

      <footer className="login-footer">
        <span>FacultyHelp · Faculty Ticketing System</span>
        <span>Secure campus support access</span>
      </footer>

      {showSignup && <SignupModal onClose={() => setShowSignup(false)} />}
    </div>
  );
}

function SignupModal({ onClose }: any) {
  const [form, setForm] = useState({ facultyId: '', name: '', department: '', designation: 'Faculty', phone: '', password: '' });
  const [message, setMessage] = useState('');
  const [saving, setSaving] = useState(false);
  const submit = async (e: any) => {
    e.preventDefault(); setSaving(true); setMessage('');
    try {
      const res = await api.post('/api/auth/signup-request', form);
      setMessage(res.data?.message || 'Access request submitted.');
      setForm({ facultyId: '', name: '', department: '', designation: 'Faculty', phone: '', password: '' });
    } catch (e: any) {
      setMessage(e.message || 'Unable to submit request.');
    } finally { setSaving(false); }
  };
  return (
    <div className="modal-backdrop">
      <div className="modal-card">
        <div className="panel-head"><div><h3>Faculty Sign Up</h3><p>Request access to FacultyHelp.</p></div><button className="icon-btn" onClick={onClose}><X size={18}/></button></div>
        <form onSubmit={submit}>
          <label>Faculty ID *<input required value={form.facultyId} onChange={e => setForm({...form, facultyId:e.target.value.toUpperCase()})} placeholder="e.g. FAC009" /></label>
          <label>Full Name *<input required value={form.name} onChange={e => setForm({...form, name:e.target.value})} /></label>
          <label>Department *<select required value={form.department} onChange={e => setForm({...form, department:e.target.value})}><option value="">Select department</option>{['CSE','CSE-AI','ECE','EEE','Mechanical','Civil','Science','Mathematics','Physics','Chemistry','English','Management'].map(d=><option key={d}>{d}</option>)}</select></label>
          <label>Designation<input value={form.designation} onChange={e => setForm({...form, designation:e.target.value})} /></label>
          <label>Phone<input value={form.phone} onChange={e => setForm({...form, phone:e.target.value})} /></label>
          <label>Password *<input required type="password" minLength={6} value={form.password} onChange={e => setForm({...form, password:e.target.value})} placeholder="Create password" /></label>
          {message && <div className="form-error">{message}</div>}
          <button className="primary wide" disabled={saving}>{saving ? 'Submitting…' : 'Request Access'}</button>
        </form>
      </div>
    </div>
  );
}

function Dashboard({ user, data, tickets, openTicket, refresh }: any) {
  const counts = data?.dashboard?.counts || {};
  const cards = [
    'New',
    'Assigned',
    'In Progress',
    'Pending',
    'Resolved',
    'Closed',
    'Escalated',
  ].map(s => ({
    label: s,
    value: counts[s] || 0,
    tone: s.toLowerCase().replace(/ /g, '-'),
  }));
  if (user.role !== 'Faculty')
    cards.push({
      label: 'SLA Breached',
      value: counts.slaBreached || 0,
      tone: 'sla',
    });

  const [chartFilter, setChartFilter] = useState('All');
  const visibleTickets = chartFilter === 'All'
    ? tickets
    : tickets.filter((t: any) => t.status === chartFilter || t.priority === chartFilter || t.teamName === chartFilter);
  const statusData = statuses.map(status => ({
    label: status,
    value: tickets.filter((t: any) => t.status === status).length,
  }));
  const priorityData = priorities.map(priority => ({
    label: priority,
    value: tickets.filter((t: any) => t.priority === priority).length,
  }));
  const teamMap = tickets.reduce((acc: any, t: any) => {
    acc[t.teamName] = (acc[t.teamName] || 0) + 1;
    return acc;
  }, {});
  const teamData = Object.entries(teamMap)
    .map(([label, value]: any) => ({ label, value: Number(value) }))
    .sort((a: any, b: any) => b.value - a.value)
    .slice(0, 8);
  const slaData = [
    { label: 'On Track', value: tickets.filter((t: any) => (t.slaStatus || getSla(t)) === 'On Track').length },
    { label: 'At Risk', value: tickets.filter((t: any) => (t.slaStatus || getSla(t)) === 'At Risk').length },
    { label: 'Breached', value: tickets.filter((t: any) => (t.slaStatus || getSla(t)) === 'Breached').length },
  ];
  const activityData = getActivityData(tickets);

  return (
    <div>
      <PageTitle
        title={
          user.role === 'Faculty'
            ? `Welcome back, ${user.name}`
            : `${user.teamName || 'Administrator'} Dashboard`
        }
        subtitle={
          user.role === 'Faculty'
            ? `Department · ${user.department}`
            : 'Operational ticket visibility and workload'
        }
        action={
          <button className="secondary" onClick={refresh}>
            Refresh
          </button>
        }
      />
      <div className="stat-grid">
        {cards.map(c => (
          <div className={`stat-card ${c.tone}`} key={c.label}>
            <span>{c.label}</span>
            <strong>{c.value}</strong>
          </div>
        ))}
      </div>

      <section className="dashboard-charts">
        <ChartPanel
          title="Ticket activity"
          subtitle="Tickets created across the latest seven-day window"
        >
          <ActivityLineChart data={activityData} />
        </ChartPanel>
        <ChartPanel
          title="Status distribution"
          subtitle="Click a segment to filter the ticket list"
        >
          <DonutChart data={statusData} selected={chartFilter} onSelect={setChartFilter} />
        </ChartPanel>
        <ChartPanel
          title="Priority mix"
          subtitle="Current workload by priority"
        >
          <DonutChart data={priorityData} selected={chartFilter} onSelect={setChartFilter} />
        </ChartPanel>
        <ChartPanel
          title="Tickets by support team"
          subtitle="Click a team to filter the ticket list"
          wide
        >
          <HorizontalBarChart data={teamData} selected={chartFilter} onSelect={setChartFilter} />
        </ChartPanel>
        <ChartPanel
          title="SLA health"
          subtitle="Current SLA state across visible tickets"
        >
          <DonutChart data={slaData} selected={chartFilter} onSelect={setChartFilter} />
        </ChartPanel>
        <ChartPanel
          title="Status workload"
          subtitle="Live count by workflow stage"
        >
          <HorizontalBarChart data={statusData} selected={chartFilter} onSelect={setChartFilter} />
        </ChartPanel>
      </section>

      <section className="panel">
        <div className="panel-head">
          <div>
            <h3>
              {user.role === 'Faculty' ? 'My Recent Tickets' : 'Recent Queue'}
            </h3>
            <p>{chartFilter === 'All' ? 'Live values from stored tickets' : `Filtered by · ${chartFilter}`}</p>
          </div>
          <div className="chart-actions">
            {chartFilter !== 'All' && (
              <button className="secondary" onClick={() => setChartFilter('All')}>
                Clear chart filter
              </button>
            )}
            <button className="text-btn" onClick={refresh}>Updated now</button>
          </div>
        </div>
        <TicketTable tickets={visibleTickets.slice(0, 8)} openTicket={openTicket} />
      </section>
    </div>
  );
}

function ChartPanel({ title, subtitle, children, wide = false }: any) {
  return (
    <section className={wide ? 'chart-panel chart-wide' : 'chart-panel'}>
      <div className="chart-head">
        <div>
          <h3>{title}</h3>
          <p>{subtitle}</p>
        </div>
      </div>
      {children}
    </section>
  );
}

function HorizontalBarChart({ data, selected, onSelect }: any) {
  const max = Math.max(1, ...data.map((d: any) => d.value));
  return (
    <div className="hbar-chart">
      {data.length ? data.map((d: any) => (
        <button
          type="button"
          className={`hbar-row ${selected === d.label ? 'selected' : ''}`}
          key={d.label}
          onClick={() => onSelect(selected === d.label ? 'All' : d.label)}
          title={`${d.label}: ${d.value} tickets`}
        >
          <span>{d.label}</span>
          <i><b style={{ width: `${(d.value / max) * 100}%` }} /></i>
          <strong>{d.value}</strong>
        </button>
      )) : <div className="chart-empty">No ticket data available.</div>}
    </div>
  );
}

function DonutChart({ data, selected, onSelect }: any) {
  const total = data.reduce((sum: number, d: any) => sum + d.value, 0);
  const gradient = makeConicGradient(data, selected);
  return (
    <div className="donut-wrap">
      <button
        type="button"
        className="donut"
        style={{ background: gradient }}
        onClick={() => onSelect('All')}
        aria-label="Clear chart selection"
        title="Click to clear selection"
      >
        <span>
          <strong>{total}</strong>
          <small>tickets</small>
        </span>
      </button>
      <div className="donut-legend">
        {data.map((d: any) => (
          <button
            type="button"
            key={d.label}
            className={selected === d.label ? 'legend-item selected' : 'legend-item'}
            onClick={() => onSelect(selected === d.label ? 'All' : d.label)}
          >
            <i className={`legend-dot ${d.label.toLowerCase().replaceAll(' ', '-')}`} />
            <span>{d.label}</span>
            <strong>{d.value}</strong>
          </button>
        ))}
      </div>
    </div>
  );
}

function ActivityLineChart({ data }: any) {
  const width = 620;
  const height = 220;
  const pad = { left: 34, right: 18, top: 18, bottom: 34 };
  const max = Math.max(1, ...data.map((d: any) => d.value));
  const points = data.map((d: any, i: number) => ({
    ...d,
    x: pad.left + (i * (width - pad.left - pad.right)) / Math.max(1, data.length - 1),
    y: height - pad.bottom - (d.value / max) * (height - pad.top - pad.bottom),
  }));
  return (
    <div className="line-chart-wrap">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Ticket activity line chart">
        <line x1={pad.left} y1={height - pad.bottom} x2={width - pad.right} y2={height - pad.bottom} className="chart-axis" />
        <line x1={pad.left} y1={pad.top} x2={pad.left} y2={height - pad.bottom} className="chart-axis" />
        <polyline points={points.map((p: any) => `${p.x},${p.y}`).join(' ')} className="chart-line" />
        {points.map((p: any) => (
          <g key={p.label}>
            <title>{`${p.label}: ${p.value} tickets`}</title>
            <circle cx={p.x} cy={p.y} r="5" className="chart-point" />
            <text x={p.x} y={height - 12} textAnchor="middle" className="chart-label">{p.label}</text>
            <text x={p.x} y={p.y - 10} textAnchor="middle" className="chart-value">{p.value}</text>
          </g>
        ))}
      </svg>
    </div>
  );
}

function makeConicGradient(data: any[], selected: string) {
  const colors = ['#2388e8', '#7b59d6', '#e19a28', '#1ea46a', '#df5148', '#71817a', '#14a6a0'];
  const total = Math.max(1, data.reduce((sum, d) => sum + d.value, 0));
  let cursor = 0;
  const stops = data.map((d, i) => {
    const start = cursor;
    cursor += (d.value / total) * 360;
    const end = cursor;
    const alpha = selected !== 'All' && selected !== d.label ? '55' : 'ff';
    return `${colors[i % colors.length]}${alpha} ${start}deg ${end}deg`;
  });
  return `conic-gradient(${stops.join(', ')})`;
}

function getActivityData(tickets: any[]) {
  if (!tickets.length) return [];
  const dates = tickets.map(t => new Date(t.createdAt).getTime()).filter(Number.isFinite);
  const anchor = new Date(Math.max(...dates));
  anchor.setHours(0, 0, 0, 0);
  return Array.from({ length: 7 }, (_, index) => {
    const d = new Date(anchor);
    d.setDate(anchor.getDate() - (6 - index));
    const key = d.toISOString().slice(0, 10);
    return {
      label: d.toLocaleDateString([], { month: 'short', day: 'numeric' }),
      value: tickets.filter(t => String(t.createdAt).slice(0, 10) === key).length,
    };
  });
}

function PageTitle({ title, subtitle, action }: any) {
  return (
    <div className="page-title">
      <div>
        <h2>{title}</h2>
        <p>{subtitle}</p>
      </div>
      {action}
    </div>
  );
}

function SharedIssues({ tickets, openTicket, call, refresh }: any) {
  return (
    <div>
      <PageTitle title="Campus Issues" subtitle="Shared issues reported by other faculty" />
      <section className="panel">
        <div className="panel-head">
          <div><h3>Shared Issues</h3><p>Join an existing issue if you are facing the same problem.</p></div>
        </div>
        <TicketTable tickets={tickets} openTicket={openTicket} faculty call={call} refresh={refresh} />
      </section>
    </div>
  );
}

function TicketList({ tickets, openTicket, faculty, team }: any) {
  const [q, setQ] = useState('');
  const [status, setStatus] = useState('All');
  const [priority, setPriority] = useState('All');
  const filtered = tickets.filter(
    (t: any) =>
      (!q ||
        [
          t.token,
          t.subject,
          t.facultyName,
          t.category,
          t.subcategory,
          t.teamName,
        ]
          .join(' ')
          .toLowerCase()
          .includes(q.toLowerCase())) &&
      (status === 'All' || t.status === status) &&
      (priority === 'All' || t.priority === priority)
  );
  return (
    <div>
      <PageTitle
        title={faculty ? 'My Tickets' : team ? 'Team Queue' : 'All Tickets'}
        subtitle={
          faculty
            ? 'Tickets raised by your account'
            : 'Tickets routed to your support scope'
        }
      />
      <div className="toolbar">
        <div className="search">
          <Search size={17} />
          <input
            placeholder="Search tickets…"
            value={q}
            onChange={e => setQ(e.target.value)}
          />
        </div>
        <select value={status} onChange={e => setStatus(e.target.value)}>
          <option>All</option>
          {statuses.map(s => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <select value={priority} onChange={e => setPriority(e.target.value)}>
          <option>All</option>
          {priorities.map(s => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <Filter size={18} />
      </div>
      <section className="panel">
        <TicketTable tickets={filtered} openTicket={openTicket} />
      </section>
    </div>
  );
}

function TicketTable({ tickets, openTicket, faculty, call, refresh }: any) {
  const [joining, setJoining] = useState('');
  const joinIssue = async (token: string) => {
    setJoining(token);
    try {
      await call('/api/tickets/join', { token });
      await refresh();
    } finally {
      setJoining('');
    }
  };
  if (!tickets.length)
    return (
      <div className="empty">
        <Ticket size={30} />
        <h3>No tickets found.</h3>
        <p>There are no tickets matching the current view.</p>
      </div>
    );
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Ticket</th>
            <th>Subject</th>
            <th>Category</th>
            <th>Team</th>
            <th>Status</th>
            <th>Priority</th>
            <th>SLA</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {tickets.map((t: any) => (
            <tr key={t.token}>
              <td>
                <b className="ticket-id">{t.token}</b>
                <small>{formatDate(t.createdAt)}</small>
              </td>
              <td>
                <b>{t.subject}</b>
                <small>{t.location}</small>
              </td>
              <td>
                {t.category}
                <small>{t.subcategory}</small>
              </td>
              <td>{t.teamName}</td>
              <td>
                <Badge text={t.status} />
              </td>
              <td>
                <Badge text={t.priority} />
              </td>
              <td>
                <Badge text={t.slaStatus || getSla(t)} />
              </td>
              <td>
                <div className="row-actions">
                  <button className="row-btn" onClick={() => openTicket(t.token)} title="Open ticket">
                    <ChevronRight size={18} />
                  </button>
                  {faculty && t.shared !== false && (
                    <button className="secondary compact" disabled={joining === t.token} onClick={() => joinIssue(t.token)}>
                      {joining === t.token ? 'Joining…' : 'Facing this too'}
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Badge({ text }: { text: string }) {
  const className = text.toLowerCase().replace(/ /g, '-');

  return (
    <span className={`badge ${className}`}>
      {text}
    </span>
  );
}

function NewTicket({ bootstrap, call, onCreated }: any) {
  const [form, setForm] = useState({
    category: '',
    subcategory: '',
    subject: '',
    description: '',
    location: '',
    peopleAffected: 1,
    urgency: 'Normal',
    priority: 'Medium',
    suggestedPriority: 'Medium',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [voice, setVoice] = useState('Ready');
  const [file, setFile] = useState<any>(null);
  const cats = bootstrap?.categories?.filter((c: any) => c.active) || [];
  const subs =
    bootstrap?.subcategories?.filter(
      (s: any) => s.active && s.category === form.category
    ) || [];
  const rule = bootstrap?.routingRules?.find(
    (r: any) =>
      r.active &&
      r.category === form.category &&
      r.subcategory === form.subcategory
  );
  const set = (k: string, v: any) => setForm((f: any) => ({ ...f, [k]: v }));
  const startVoice = () => {
    const SpeechRecognition =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setVoice('Unavailable');
      return;
    }
    const rec = new SpeechRecognition();
    rec.onstart = () => setVoice('Listening');
    rec.onresult = (e: any) => {
      set('description', e.results[0][0].transcript);
      setVoice('Completed');
    };
    rec.onerror = () => setVoice('Unavailable');
    rec.onend = () => setVoice(v => (v === 'Listening' ? 'Processing' : v));
    rec.start();
  };
  const submit = async (e: any) => {
    e.preventDefault();
    setError('');
    if (
      !form.category ||
      !form.subcategory ||
      !form.subject ||
      !form.description ||
      !form.location
    ) {
      setError('Complete all required fields.');
      return;
    }
    setSaving(true);
    try {
      const res = await call('/api/tickets', form);
      if (file) {
        const reader = new FileReader();
        reader.onload = async () => {
          const base64 = String(reader.result).split(',')[1];
          await call('/api/upload', {
            token: res.ticket.token,
            fileName: file.name,
            contentType: file.type,
            base64,
          });
          onCreated(res.ticket.token);
        };
        reader.readAsDataURL(file);
      } else onCreated(res.ticket.token);
    } catch (e: any) {
      setError(e.message || 'Unable to create ticket');
      setSaving(false);
    }
  };
  return (
    <div>
      <PageTitle
        title="New Ticket"
        subtitle="Report a faculty support issue or request."
      />
      <form className="form-panel" onSubmit={submit}>
        <div className="form-grid">
          <label>
            Category *
            <select
              value={form.category}
              onChange={e => {
                set('category', e.target.value);
                set('subcategory', '');
              }}
            >
              <option value="">Select category</option>
              {cats.map((c: any) => (
                <option key={c.id}>{c.name}</option>
              ))}
            </select>
          </label>
          <label>
            Subcategory *
            <select
              value={form.subcategory}
              onChange={e => set('subcategory', e.target.value)}
              disabled={!form.category}
            >
              <option value="">Select subcategory</option>
              {subs.map((s: any) => (
                <option key={s.id}>{s.name}</option>
              ))}
            </select>
          </label>
          <label className="span-2">
            Subject *
            <input
              value={form.subject}
              onChange={e => set('subject', e.target.value)}
              placeholder="Briefly describe the issue"
            />
          </label>
          <label className="span-2">
            Description *
            <textarea
              rows={5}
              value={form.description}
              onChange={e => set('description', e.target.value)}
              placeholder="Describe what happened and any relevant details"
            />
          </label>
          <label>
            Location *
            <select
              value={form.location}
              onChange={e => set('location', e.target.value)}
            >
              <option value="">Select location</option>
              {(bootstrap?.locations || [])
                .filter((l: any) => l.active)
                .map((l: any) => (
                  <option key={l.id}>{l.name}</option>
                ))}
            </select>
          </label>
          <label>
            People Affected
            <input
              type="number"
              min="1"
              value={form.peopleAffected}
              onChange={e => set('peopleAffected', Number(e.target.value))}
            />
          </label>
          <label>
            Urgency
            <select
              value={form.urgency}
              onChange={e => set('urgency', e.target.value)}
            >
              <option>Low</option>
              <option>Normal</option>
              <option>Urgent</option>
            </select>
          </label>
          <label>
            Priority
            <select
              value={form.priority}
              onChange={e => set('priority', e.target.value)}
            >
              {priorities.map(p => (
                <option key={p}>{p}</option>
              ))}
            </select>
          </label>
          <div className="route-box span-2">
            <Zap size={18} />
            <div>
              <b>Automatically routed to</b>
              <span>{rule?.teamName || 'Select category and subcategory'}</span>
            </div>
          </div>
          <label className="upload span-2">
            <span>
              <Paperclip size={17} /> Evidence Upload
            </span>
            <input
              type="file"
              accept=".jpg,.jpeg,.png,.webp,.pdf"
              onChange={e => setFile(e.target.files?.[0] || null)}
            />
            {file && <small>{file.name}</small>}
          </label>
          <div className="voice-box span-2">
            <div>
              <b>Voice-to-Ticket</b>
              <span>{voice}</span>
            </div>
            <button type="button" className="secondary" onClick={startVoice}>
              Start voice input
            </button>
          </div>
        </div>
        {error && <div className="form-error">{error}</div>}
        <div className="form-actions">
          <button type="submit" className="primary" disabled={saving}>
            {saving ? 'Creating…' : 'Create Ticket'}
          </button>
        </div>
      </form>
    </div>
  );
}

function TicketDetail({ ticket, user, call, onBack, onChanged }: any) {
  const [comment, setComment] = useState('');
  const [working, setWorking] = useState(false);
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    (async () => {
      try {
        setData(await call('/api/tickets/detail', { token: ticket.token }));
      } catch {}
    })();
  }, [ticket.token]);
  const t = data?.ticket || ticket;
  const act = async (action: string, extra: any = {}) => {
    setWorking(true);
    try {
      await call('/api/tickets/action', { token: t.token, action, ...extra });
      await onChanged();
      setData(await call('/api/tickets/detail', { token: t.token }));
    } catch (e: any) {
    } finally {
      setWorking(false);
    }
  };
  const addComment = async () => {
    if (!comment.trim()) return;
    await call('/api/comments', { token: t.token, comment });
    setComment('');
    setData(await call('/api/tickets/detail', { token: t.token }));
  };
  return (
    <div>
      <button className="back" onClick={onBack}>
        ← Back
      </button>
      <PageTitle title={t.token} subtitle={t.subject} />
      <div className="detail-grid">
        <section className="panel">
          <div className="detail-hero">
            <div>
              <span className="ticket-id">{t.token}</span>
              <h3>{t.subject}</h3>
            </div>
            <div className="detail-badges">
              <Badge text={t.status} />
              <Badge text={t.priority} />
              <Badge text={t.slaStatus || getSla(t)} />
            </div>
          </div>
          <div className="detail-fields">
            {[
              ['Category', t.category],
              ['Subcategory', t.subcategory],
              ['Location', t.location],
              ['People Affected', t.peopleAffected],
              ['Urgency', t.urgency],
              ['Priority', t.priority],
              ['Support Team', t.teamName],
              ['Assigned Team Member', t.assignedTo || 'Unassigned'],
              ['Created', formatDate(t.createdAt)],
              ['Updated', formatDate(t.updatedAt)],
              ['Response SLA', formatDate(t.responseDeadline)],
              ['Resolution SLA', formatDate(t.resolutionDeadline)],
            ].map(([a, b]) => (
              <div key={a as string}>
                <span>{a}</span>
                <b>{b}</b>
              </div>
            ))}
          </div>
          <div className="description">
            <h4>Description</h4>
            <p>{t.description}</p>
          </div>
          {t.attachment && (
            <a
              className="attachment"
              href={t.attachment.url}
              target="_blank"
              rel="noreferrer"
            >
              <Paperclip size={17} /> {t.attachment.fileName}
            </a>
          )}
          {t.shared !== false && (
            <div className="shared-issue-box">
              <Users size={17} />
              <div><b>{t.affectedCount || 1} faculty affected</b><span>Faculty experiencing the same issue can join this ticket instead of creating duplicates.</span></div>
              {user.role === 'Faculty' && t.facultyId !== user.userId && (
                <button className="secondary" onClick={async () => { await call('/api/tickets/join', { token: t.token }); await onChanged(); setData(await call('/api/tickets/detail', { token: t.token })); }}>I'm Facing This Too</button>
              )}
            </div>
          )}
          {user.role !== 'Faculty' && (
            <div className="action-row">
              <button
                className="secondary"
                disabled={working}
                onClick={() => act('accept')}
              >
                Accept
              </button>
              <select
                defaultValue=""
                onChange={e =>
                  e.target.value && act('status', { status: e.target.value })
                }
              >
                <option value="">Change status…</option>
                {statuses.map(s => (
                  <option key={s}>{s}</option>
                ))}
              </select>
              <button
                className="danger"
                disabled={working}
                onClick={() => act('escalate')}
              >
                Escalate
              </button>
            </div>
          )}
          {user.role === 'Faculty' && t.status === 'Resolved' && (
            <button className="primary" onClick={() => act('close')}>
              Close Ticket
            </button>
          )}
        </section>
        <section className="panel">
          <div className="panel-head">
            <h3>Comments</h3>
            <MessageSquare size={18} />
          </div>
          <div className="comments">
            {(data?.comments || []).map((c: any) => (
              <div className="comment" key={c.id}>
                <div className="avatar small">{c.authorName.slice(0, 1)}</div>
                <div>
                  <b>{c.authorName}</b>
                  <small>{formatDate(c.createdAt)}</small>
                  <p>{c.comment}</p>
                </div>
              </div>
            ))}
          </div>
          <div className="comment-box">
            <textarea
              value={comment}
              onChange={e => setComment(e.target.value)}
              placeholder="Add a comment…"
            />
            <button className="primary" onClick={addComment}>
              Add Comment
            </button>
          </div>
        </section>
        <section className="panel history-panel">
          <div className="panel-head">
            <h3>Ticket History</h3>
            <History size={18} />
          </div>
          {(data?.history || []).map((h: any) => (
            <div className="history" key={h.id}>
              <div className="history-dot"></div>
              <div>
                <b>{h.action}</b>
                <p>{h.detail}</p>
                <small>
                  {h.actorName} · {formatDate(h.createdAt)}
                </small>
              </div>
            </div>
          ))}
        </section>
      </div>
    </div>
  );
}

function Notifications({ call }: any) {
  const [items, setItems] = useState<any[]>([]);
  const markRead = async (item: any) => {
    if (item.read) return;
    await call('/api/notifications/read', { id: item.id });
    setItems((current: any[]) => current.map(existing => existing.id === item.id ? { ...existing, read: true } : existing));
  };
  useEffect(() => {
    call('/api/notifications/list').then((d: any) =>
      setItems(d.notifications || [])
    );
  }, []);
  return (
    <div>
      <PageTitle
        title="Notifications"
        subtitle="Ticket activity and SLA alerts"
      />
      <section className="panel">
        {items.length ? (
          items.map(n => (
            <div className={`notification ${n.read ? 'read' : ''}`} key={n.id} onClick={() => markRead(n)} role="button" tabIndex={0}>
              <div className="notify-icon">
                <Bell size={17} />
              </div>
              <div>
                <b>{n.title}</b>
                <p>{n.body}</p>
                <small>{formatDate(n.createdAt)}</small>
              </div>
            </div>
          ))
        ) : (
          <div className="empty">
            <Bell size={30} />
            <h3>No notifications</h3>
            <p>You are all caught up.</p>
          </div>
        )}
      </section>
    </div>
  );
}

function Profile({ user, tickets, onNavigate }: any) {
  const total = tickets.length;
  const resolved = tickets.filter((ticket: any) => ['Resolved', 'Closed'].includes(ticket.status)).length;
  const open = total - resolved;
  const critical = tickets.filter((ticket: any) => ticket.priority === 'Critical').length;
  const completion = total ? Math.round((resolved / total) * 100) : 0;
  return (
    <div>
      <PageTitle title="Profile" subtitle="Your FacultyHelp account" />
      <section className="panel profile-card">
        <div className="profile-avatar">{user.name.slice(0, 1)}</div>
        <div>
          <h3>{user.name}</h3>
          <p>{user.department}{user.teamName ? ` · ${user.teamName}` : ''}</p>
          <div className="profile-actions">
            <button className="secondary" onClick={() => onNavigate(user.role === 'Faculty' ? 'tickets' : user.role === 'Team Member' ? 'assigned' : 'admin-tickets')}><Ticket size={15} /> My Work</button>
            <button className="secondary" onClick={() => onNavigate('notifications')}><Bell size={15} /> Notifications</button>
          </div>
        </div>
        <div className="profile-stats">
          <div><span>Total Tickets</span><strong>{total}</strong></div>
          <div><span>Open</span><strong>{open}</strong></div>
          <div><span>Resolved / Closed</span><strong>{resolved}</strong></div>
          <div><span>Critical</span><strong>{critical}</strong></div>
        </div>
        <div className="profile-grid">
          <div>
            <span>User ID</span>
            <b>{user.userId}</b>
          </div>
          <div>
            <span>Department</span>
            <b>{user.department}</b>
          </div>
          <div>
            <span>Role</span>
            <b>{user.role}</b>
          </div>
          <div><span>Resolved</span><b>{completion}%</b></div>
          {user.teamName && (
            <div>
              <span>Team</span>
              <b>{user.teamName}</b>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function AccessRequests({ call }: any) {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState('');
  const load = async () => {
    setLoading(true);
    try {
      const d = await call('/api/admin/data');
      setItems(d.access_requests || []);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);
  const action = async (id: string, type: 'approve' | 'reject') => {
    setWorking(id);
    try {
      await call('/api/admin/mutate', { kind: 'access_requests', action: type, id });
      await load();
    } finally { setWorking(''); }
  };
  return (
    <div>
      <PageTitle title="Faculty Access Requests" subtitle="Review new faculty account requests before granting access." />
      <section className="panel">
        <div className="panel-head">
          <div><h3>Access Requests</h3><p>{items.filter(r => r.status === 'Pending').length} pending request(s)</p></div>
          <button className="secondary" onClick={load}>Refresh</button>
        </div>
        {loading ? <div className="empty"><p>Loading requests…</p></div> : items.length === 0 ? (
          <div className="empty"><Users size={30}/><h3>No access requests</h3><p>New faculty sign-up requests will appear here.</p></div>
        ) : (
          <div className="table-wrap"><table><thead><tr><th>Faculty ID</th><th>Name</th><th>Department</th><th>Designation</th><th>Requested</th><th>Status</th><th>Action</th></tr></thead>
          <tbody>{items.sort((a,b)=>new Date(b.createdAt).getTime()-new Date(a.createdAt).getTime()).map(r=>(
            <tr key={r.id}><td><b className="ticket-id">{r.facultyId}</b></td><td>{r.name}</td><td>{r.department}</td><td>{r.designation}</td><td>{formatDate(r.createdAt)}</td><td><Badge text={r.status}/></td>
            <td>{r.status === 'Pending' ? <div className="request-actions"><button className="primary" disabled={working===r.id} onClick={()=>action(r.id,'approve')}>Accept</button><button className="danger" disabled={working===r.id} onClick={()=>action(r.id,'reject')}>Reject</button></div> : <span>Reviewed</span>}</td></tr>
          ))}</tbody></table></div>
        )}
      </section>
    </div>
  );
}

function AdminResource({ page, call }: any) {
  const [data, setData] = useState<any>({});
  const [editing, setEditing] = useState<any>(null);
  const [form, setForm] = useState<any>({});
  const [error, setError] = useState('');
  const kind = page === 'routing' ? 'routing_rules' : page === 'sla' ? 'sla_settings' : page;
  const load = async () => setData(await call('/api/admin/data'));
  useEffect(() => { load(); setEditing(null); }, [page]);
  const rows = data[kind] || [];
  const fields: Record<string, { name: string; label: string; type?: string }[]> = {
    users: [
      { name: 'userId', label: 'User ID' }, { name: 'name', label: 'Name' },
      { name: 'department', label: 'Department' }, { name: 'designation', label: 'Designation' },
      { name: 'phone', label: 'Phone' }, { name: 'role', label: 'Role' },
      { name: 'teamName', label: 'Team' }, { name: 'password', label: 'Password', type: 'password' },
      { name: 'active', label: 'Active', type: 'checkbox' },
    ],
    teams: [{ name: 'name', label: 'Team name' }, { name: 'active', label: 'Active', type: 'checkbox' }],
    categories: [{ name: 'name', label: 'Category name' }, { name: 'active', label: 'Active', type: 'checkbox' }],
    locations: [{ name: 'name', label: 'Location name' }, { name: 'active', label: 'Active', type: 'checkbox' }],
    routing_rules: [
      { name: 'category', label: 'Category' }, { name: 'subcategory', label: 'Subcategory' },
      { name: 'teamName', label: 'Support team' }, { name: 'active', label: 'Active', type: 'checkbox' },
    ],
    sla_settings: [
      { name: 'priority', label: 'Priority' }, { name: 'responseMinutes', label: 'Response minutes', type: 'number' },
      { name: 'resolutionMinutes', label: 'Resolution minutes', type: 'number' }, { name: 'active', label: 'Active', type: 'checkbox' },
    ],
  };
  const edit = (record: any = {}) => {
    const next: any = {};
    fields[kind].forEach(field => { next[field.name] = record[field.name] ?? (field.name === 'active' ? true : ''); });
    if (kind === 'sla_settings') {
      next.responseMinutes ||= 120;
      next.resolutionMinutes ||= 1440;
    }
    setForm(next);
    setError('');
    setEditing(record.id || 'new');
  };
  const save = async () => {
    const required = fields[kind].filter(field => !['active', 'password', 'phone', 'designation', 'teamName'].includes(field.name));
    if (required.some(field => String(form[field.name] ?? '').trim() === '')) {
      setError('Complete the required fields.');
      return;
    }
    const record = { ...form };
    if (kind === 'users' && !record.password) delete record.password;
    try {
      await call('/api/admin/mutate', { kind, action: editing === 'new' ? 'create' : 'update', id: editing, record });
      setEditing(null);
      await load();
    } catch (e: any) {
      setError(e.message || 'Unable to save this record.');
    }
  };
  const deactivate = async (id: string) => {
    if (!window.confirm('Deactivate this record?')) return;
    try {
      await call('/api/admin/mutate', { kind, action: 'delete', id });
      await load();
    } catch (e: any) {
      setError(e.message || 'Unable to deactivate this record.');
    }
  };
  const columns = fields[kind].filter(field => field.name !== 'password');
  const options: Record<string, string[]> = {
    role: ['Faculty', 'Team Member', 'Administrator'],
    department: (data.departments || []).map((item: any) => item.name),
    teamName: (data.teams || []).map((item: any) => item.name),
    category: (data.categories || []).map((item: any) => item.name),
    priority: priorities,
  };
  return (
    <div>
      <PageTitle
        title={label(page)}
        subtitle="Administration and configuration"
      />
      <section className="panel">
        <div className="panel-head">
          <h3>{label(page)}</h3>
          <button className="secondary" onClick={() => edit()}>
            <Plus size={16} /> Add
          </button>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {columns.map(field => <th key={field.name}>{field.label}</th>)}
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r: any) => (
                <tr key={r.id}>
                    {columns.map(field => <td key={field.name}>{field.name === 'active' ? (r.active ? 'Active' : 'Inactive') : String(r[field.name] ?? '—')}</td>)}
                    <td><div className="row-actions"><button className="secondary compact" onClick={() => edit(r)}>Edit</button><button className="danger compact" onClick={() => deactivate(r.id)}>Deactivate</button></div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      {editing !== null && (
        <div className="modal-backdrop">
          <section className="modal-card">
            <div className="panel-head"><div><h3>{editing === 'new' ? `Add ${label(page)}` : `Edit ${label(page)}`}</h3></div><button className="icon-btn" onClick={() => setEditing(null)} aria-label="Close">×</button></div>
            <div className="form-grid">
              {fields[kind].map(field => (
                <label key={field.name}>
                  {field.label}
                  {field.type === 'checkbox' ? <input type="checkbox" checked={Boolean(form[field.name])} onChange={event => setForm({ ...form, [field.name]: event.target.checked })} />
                    : options[field.name] ? <select value={form[field.name]} onChange={event => setForm({ ...form, [field.name]: event.target.value })}><option value="">Select {field.label.toLowerCase()}</option>{options[field.name].map(value => <option key={value}>{value}</option>)}</select>
                      : <input type={field.type || 'text'} min={field.type === 'number' ? 1 : undefined} value={form[field.name]} readOnly={kind === 'users' && field.name === 'userId' && editing !== 'new'} onChange={event => setForm({ ...form, [field.name]: field.type === 'number' ? Number(event.target.value) : event.target.value })} />}
                </label>
              ))}
            </div>
            {error && <div className="form-error">{error}</div>}
            <div className="form-actions"><button className="primary" onClick={save}>Save</button><button className="secondary" onClick={() => setEditing(null)}>Cancel</button></div>
          </section>
        </div>
      )}
    </div>
  );
}

function Reports({ call }: any) {
  const [r, setR] = useState<any>(null);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('All');
  const [category, setCategory] = useState('All');
  useEffect(() => {
    call('/api/reports').then(setR);
  }, []);
  const tickets = (r?.tickets || []).filter((ticket: any) =>
    (status === 'All' || ticket.status === status) &&
    (category === 'All' || ticket.category === category) &&
    (!search || [ticket.token, ticket.subject, ticket.facultyName, ticket.teamName].join(' ').toLowerCase().includes(search.toLowerCase()))
  );
  const categoryData = Object.entries(tickets.reduce((counts: Record<string, number>, ticket: any) => {
    counts[ticket.category] = (counts[ticket.category] || 0) + 1;
    return counts;
  }, {})).map(([label, value]) => ({ label, value: Number(value) }));
  const download = () => {
    const columns = ['token', 'subject', 'category', 'subcategory', 'facultyName', 'department', 'teamName', 'status', 'priority', 'location', 'createdAt', 'resolutionDeadline', 'slaStatus'];
    const escape = (value: any) => `"${String(value ?? '').replace(/"/g, '""')}"`;
    const csv = [columns.join(','), ...tickets.map((ticket: any) => columns.map(column => escape(ticket[column])).join(','))].join('\r\n');
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    link.download = 'facultyhelp-report.csv';
    link.click();
    URL.revokeObjectURL(link.href);
  };
  return (
    <div>
      <PageTitle
        title="Reports"
        subtitle="Operational reporting from stored ticket data"
        action={<button className="secondary" onClick={download}><Download size={16} /> Download Report</button>}
      />
      <div className="report-grid">
        <ReportCard title="By Status" data={r?.byStatus} />
        <ReportCard title="By Priority" data={r?.byPriority} />
        <ReportCard title="By Team" data={r?.byTeam} />
      </div>
      <ChartPanel title="Issues by category" subtitle="Current filtered report distribution">
        <DonutChart data={categoryData} selected="All" onSelect={() => {}} />
      </ChartPanel>
      <section className="panel">
        <div className="panel-head">
          <div><h3>Complete issue list</h3><p>{tickets.length} of {r?.total || 0} tickets</p></div>
          <div className="compliance"><strong>{r?.total ? Math.round(((r.total - (r.breached || 0)) / r.total) * 100) : 0}%</strong><span>within SLA</span></div>
        </div>
        <div className="toolbar"><div className="search"><Search size={17} /><input placeholder="Search reports" value={search} onChange={event => setSearch(event.target.value)} /></div><select value={status} onChange={event => setStatus(event.target.value)}><option>All</option>{statuses.map(value => <option key={value}>{value}</option>)}</select><select value={category} onChange={event => setCategory(event.target.value)}><option>All</option>{Object.keys(r?.byCategory || {}).map(value => <option key={value}>{value}</option>)}</select></div>
        <TicketTable tickets={tickets} openTicket={(token: string) => { window.location.href = `/tickets/${token}`; }} />
      </section>
    </div>
  );
}

function ReportCard({ title, data }: any) {
  return (
    <section className="panel report-card">
      <h3>{title}</h3>
      {Object.entries(data || {}).map(([k, v]: any) => (
        <div className="bar-row" key={k}>
          <span>{k}</span>
          <div>
            <i
              style={{
                width: `${Math.min(100, (Number(v) / Math.max(1, ...Object.values(data || {}).map(Number))) * 100)}%`,
              }}
            ></i>
          </div>
          <b>{v}</b>
        </div>
      ))}
    </section>
  );
}

function label(p: string) {
  return p.replace(/-/g, ' ').replace(/\b\w/g, m => m.toUpperCase());
}
function formatDate(v: any) {
  return v
    ? new Date(v).toLocaleString([], {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    : '—';
}
function getSla(t: any) {
  if (t.status === 'Closed') return 'On Track';
  const left = new Date(t.resolutionDeadline).getTime() - Date.now();
  if (left < 0) return 'Breached';
  if (left < 3600000) return 'At Risk';
  return 'On Track';
}

export default App;

