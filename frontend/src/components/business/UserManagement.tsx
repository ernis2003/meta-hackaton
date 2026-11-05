import { useEffect, useRef, useState, type FormEvent } from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
  faUserGear,
  faUsers,
  faUser,
  faBan,
  faShieldHalved,
  faPlus,
  faMagnifyingGlass,
  faRotateLeft,
  faEye,
  faPen,
  faEllipsis,
  faChevronLeft,
  faChevronRight,
  faXmark,
} from '@fortawesome/free-solid-svg-icons';
import { BACKEND_URL, BACKEND_PORT } from '../../../constants';
import { clearAuth } from '../../utils/auth';
import styles from './UserManagement.module.css';

type User = {
  id: string;
  name: string;
  surname: string;
  email: string;
  organization: string;
  role: 'user' | 'admin';
  is_active: boolean;
  created_at: string;
  analysis_count: number;
};
type Notice = { kind: 'success' | 'error'; text: string };
type Dialog = {
  kind: 'create' | 'edit' | 'view' | 'manage' | 'block' | 'unblock' | 'delete';
  users: User[];
};
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = sessionStorage.getItem('access_token');
  const response = await fetch(`${BACKEND_URL}:${BACKEND_PORT}/api${path}`, {
    ...options,
    headers: { Authorization: `Bearer ${token}`, ...options?.headers },
  });
  if (response.status === 401 && sessionStorage.getItem('access_token') === token) {
    clearAuth();
    window.location.replace('/?session=expired');
    throw new Error('Your session expired. Please sign in again.');
  }
  if (response.status === 204) return undefined as T;
  const body = await response.json();
  if (!response.ok)
    throw new Error(
      typeof body.detail === 'string'
        ? body.detail
        : Array.isArray(body.detail)
          ? body.detail
              .map((item: { msg: string }) => item.msg.replace(/^Value error, /, ''))
              .join('. ')
          : 'Request failed. Please try again.',
    );
  return body as T;
}
async function readUsers(signal: AbortSignal) {
  const users: User[] = [];
  for (let offset = 0; ; offset += 100) {
    const page = await request<User[]>(`/users?limit=100&offset=${offset}`, { signal });
    users.push(...page);
    if (page.length < 100) return users;
  }
}
function registered(value: string) {
  const date = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : value.replace(' ', 'T') + 'Z');
  return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}
function Role({ value }: { value: User['role'] }) {
  return (
    <span className={styles.role} data-admin={value === 'admin'}>
      {value === 'admin' ? 'Administrator' : 'User'}
    </span>
  );
}
function Status({ active }: { active: boolean }) {
  return (
    <span className={styles.status} data-active={active}>
      <span aria-hidden="true" />
      {active ? 'Active' : 'Blocked'}
    </span>
  );
}
function SelectAll({
  checked,
  mixed,
  disabled,
  onChange,
}: {
  checked: boolean;
  mixed: boolean;
  disabled: boolean;
  onChange: () => void;
}) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = mixed;
  }, [mixed]);
  return (
    <input
      ref={ref}
      type="checkbox"
      aria-label="Select users on this page"
      checked={checked}
      disabled={disabled}
      onChange={onChange}
    />
  );
}
export default function UserManagement() {
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState<{
    revision: number;
    users: User[];
    me: User;
    error?: string;
  }>();
  const [loadError, setLoadError] = useState<{ revision: number; text: string }>();
  const [search, setSearch] = useState('');
  const [role, setRole] = useState('all');
  const [status, setStatus] = useState('all');
  const [sort, setSort] = useState<'name' | 'registered'>('registered');
  const [ascending, setAscending] = useState(false);
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [dialog, setDialog] = useState<Dialog>();
  const [notice, setNotice] = useState<Notice>();
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      readUsers(controller.signal),
      request<User>('/users/me', { signal: controller.signal }),
    ])
      .then(([users, me]) => {
        if (!controller.signal.aborted) setState({ revision, users, me });
      })
      .catch((error: Error) => {
        if (!controller.signal.aborted) setLoadError({ revision, text: error.message });
      });
    return () => controller.abort();
  }, [revision]);
  const users = state?.users || [];
  const error = loadError?.revision === revision ? loadError.text : '';
  const loading = state?.revision !== revision && !error;
  const query = search.toLowerCase().trim();
  const filtered = users
    .filter(
      (user) =>
        (!query ||
          [user.name, user.surname, user.email, user.organization]
            .join(' ')
            .toLowerCase()
            .includes(query)) &&
        (role === 'all' || user.role === role) &&
        (status === 'all' || user.is_active === (status === 'active')),
    )
    .sort((a, b) => {
      const result =
        sort === 'name'
          ? `${a.name} ${a.surname}`.localeCompare(`${b.name} ${b.surname}`)
          : a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id);
      return ascending ? result : -result;
    });
  const pages = Math.ceil(filtered.length / 5);
  const currentPage = Math.min(page, Math.max(0, pages - 1));
  const visible = filtered.slice(currentPage * 5, currentPage * 5 + 5);
  const selectable = visible.filter((user) => user.id !== state?.me.id);
  const selectedOnPage = selectable.filter((user) => selected.has(user.id)).length;
  function changeFilter(update: () => void) {
    update();
    setPage(0);
    setSelected(new Set());
  }
  function reset() {
    changeFilter(() => {
      setSearch('');
      setRole('all');
      setStatus('all');
    });
  }
  function toggle(id: string) {
    setSelected((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }
  function selectPage() {
    setSelected((previous) => {
      const next = new Set(previous);
      for (const user of selectable) {
        if (selectedOnPage === selectable.length) next.delete(user.id);
        else next.add(user.id);
      }
      return next;
    });
  }
  function order(key: 'name' | 'registered') {
    if (sort === key) setAscending(!ascending);
    else {
      setSort(key);
      setAscending(true);
    }
    setPage(0);
  }
  function saved(message: Notice) {
    setDialog(undefined);
    setNotice(message);
    setSelected(new Set());
    setRevision((value) => value + 1);
  }
  const metrics = [
    { title: 'Total users', value: users.length, icon: faUsers, tone: 'neutral' },
    {
      title: 'Active users',
      value: users.filter((user) => user.is_active).length,
      icon: faUser,
      tone: 'teal',
    },
    {
      title: 'Blocked users',
      value: users.filter((user) => !user.is_active).length,
      icon: faBan,
      tone: 'red',
    },
    {
      title: 'Administrators',
      value: users.filter((user) => user.role === 'admin').length,
      icon: faShieldHalved,
      tone: 'blue',
    },
  ];
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <span className={styles.headerIcon}>
          <FontAwesomeIcon icon={faUserGear} />
        </span>
        <div className={styles.headerText}>
          <h1>User management</h1>
          <p>
            Review registered accounts, manage user roles, and control access to the analysis
            platform.
          </p>
        </div>
        <button
          type="button"
          className={styles.button + ' ' + styles.primary}
          onClick={() => setDialog({ kind: 'create', users: [] })}
        >
          <FontAwesomeIcon icon={faPlus} />
          Create user
        </button>
      </header>
      <section className={styles.metrics} aria-label="User statistics">
        {metrics.map((metric) => (
          <div className={styles.metric} key={metric.title} data-tone={metric.tone}>
            <span className={styles.metricIcon}>
              <FontAwesomeIcon icon={metric.icon} />
            </span>
            <div>
              <p>{metric.title}</p>
              <strong>{state ? metric.value : '\u2014'}</strong>
            </div>
          </div>
        ))}
      </section>
      <div className={styles.filters}>
        <label className={styles.search}>
          <FontAwesomeIcon icon={faMagnifyingGlass} />
          <input
            aria-label="Search users"
            placeholder="Search by name, email or organization..."
            value={search}
            onChange={(e) => changeFilter(() => setSearch(e.target.value))}
          />
        </label>
        <label className={styles.filter}>
          <span>Role:</span>
          <select
            aria-label="Filter by role"
            value={role}
            onChange={(e) => changeFilter(() => setRole(e.target.value))}
          >
            <option value="all">All</option>
            <option value="user">User</option>
            <option value="admin">Administrator</option>
          </select>
        </label>
        <label className={styles.filter}>
          <span>Status:</span>
          <select
            aria-label="Filter by status"
            value={status}
            onChange={(e) => changeFilter(() => setStatus(e.target.value))}
          >
            <option value="all">All</option>
            <option value="active">Active</option>
            <option value="blocked">Blocked</option>
          </select>
        </label>
        <button type="button" className={styles.button + ' ' + styles.reset} onClick={reset}>
          <FontAwesomeIcon icon={faRotateLeft} />
          Reset
        </button>
      </div>
      {notice && (
        <p
          role={notice.kind === 'error' ? 'alert' : 'status'}
          className={styles.notice + (notice.kind === 'error' ? ' ' + styles.error : '')}
        >
          {notice.text}
        </p>
      )}
      {error && (
        <div role="alert" className={styles.notice + ' ' + styles.error}>
          {error}
          <button
            type="button"
            className={styles.button}
            onClick={() => setRevision((value) => value + 1)}
          >
            Try again
          </button>
        </div>
      )}
      {selected.size > 0 && (
        <div className={styles.bulk}>
          <span>{selected.size} users selected</span>
          <button
            type="button"
            className={styles.button}
            onClick={() =>
              setDialog({
                kind: 'block',
                users: users.filter((user) => selected.has(user.id) && user.is_active),
              })
            }
            disabled={!users.some((user) => selected.has(user.id) && user.is_active)}
          >
            Block selected
          </button>
          <button
            type="button"
            className={styles.button}
            onClick={() =>
              setDialog({
                kind: 'unblock',
                users: users.filter((user) => selected.has(user.id) && !user.is_active),
              })
            }
            disabled={!users.some((user) => selected.has(user.id) && !user.is_active)}
          >
            Unblock selected
          </button>
          <button type="button" className={styles.button} onClick={() => setSelected(new Set())}>
            Clear selection
          </button>
        </div>
      )}
      {loading && (
        <p role="status" className={styles.loading}>
          Loading users...
        </p>
      )}
      <section className={styles.tablePanel} aria-label="Registered users" aria-busy={loading}>
        <div className={styles.tableScroll}>
          <table className={styles.table}>
            <caption className="sr-only">Registered user accounts and management actions</caption>
            <thead>
              <tr>
                <th>
                  <SelectAll
                    checked={selectable.length > 0 && selectedOnPage === selectable.length}
                    mixed={selectedOnPage > 0 && selectedOnPage < selectable.length}
                    disabled={!selectable.length}
                    onChange={selectPage}
                  />
                </th>
                <th aria-sort={sort === 'name' ? (ascending ? 'ascending' : 'descending') : 'none'}>
                  <button type="button" onClick={() => order('name')}>
                    Name <span aria-hidden="true">↕</span>
                  </button>
                </th>
                <th>Email</th>
                <th>Organization</th>
                <th>Role</th>
                <th>Status</th>
                <th>Analyses</th>
                <th
                  aria-sort={
                    sort === 'registered' ? (ascending ? 'ascending' : 'descending') : 'none'
                  }
                >
                  <button type="button" onClick={() => order('registered')}>
                    Registered <span aria-hidden="true">↕</span>
                  </button>
                </th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((user) => (
                <tr key={user.id} data-selected={selected.has(user.id)}>
                  <td>
                    <input
                      type="checkbox"
                      aria-label={`Select ${user.name} ${user.surname}`}
                      checked={selected.has(user.id)}
                      disabled={user.id === state?.me.id}
                      onChange={() => toggle(user.id)}
                      title={
                        user.id === state?.me.id
                          ? 'Your administrator account cannot be blocked'
                          : undefined
                      }
                    />
                  </td>
                  <td>
                    <div className={styles.person}>
                      <span className={styles.avatar} aria-hidden="true">
                        {user.name[0]}
                        {user.surname[0]}
                      </span>
                      <span>
                        {user.name} {user.surname}
                        {user.id === state?.me.id && <small className={styles.you}>You</small>}
                      </span>
                    </div>
                  </td>
                  <td className={styles.email}>{user.email}</td>
                  <td>{user.organization || '\u2014'}</td>
                  <td>
                    <Role value={user.role} />
                  </td>
                  <td>
                    <Status active={user.is_active} />
                  </td>
                  <td className={styles.numeric}>{user.analysis_count ?? 0}</td>
                  <td className={styles.date}>{registered(user.created_at)}</td>
                  <td>
                    <div className={styles.actions}>
                      {(
                        [
                          { kind: 'view', icon: faEye, title: 'View' },
                          { kind: 'edit', icon: faPen, title: 'Edit' },
                          { kind: 'manage', icon: faEllipsis, title: 'More actions for' },
                        ] as const
                      ).map((action) => (
                        <button
                          key={action.kind}
                          type="button"
                          title={`${action.title} ${user.name} ${user.surname}`}
                          aria-label={`${action.title} ${user.name} ${user.surname}`}
                          onClick={() => setDialog({ kind: action.kind, users: [user] })}
                        >
                          <FontAwesomeIcon icon={action.icon} />
                        </button>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!loading && !error && !filtered.length && (
          <div className={styles.empty}>
            <FontAwesomeIcon icon={faUsers} />
            <h2>{users.length ? 'No matching users' : 'No users found'}</h2>
            <p>
              {users.length
                ? 'Try another search or reset the filters.'
                : 'Create an account to get started.'}
            </p>
            {users.length > 0 && (
              <button className={styles.button} onClick={reset}>
                Reset filters
              </button>
            )}
          </div>
        )}
        <footer className={styles.pagination}>
          <span>
            {filtered.length
              ? `Showing ${currentPage * 5 + 1}\u2013${Math.min(currentPage * 5 + 5, filtered.length)} of ${filtered.length} users`
              : 'Showing 0 users'}
          </span>
          <nav aria-label="User pages">
            <button
              type="button"
              aria-label="Previous page"
              disabled={!currentPage}
              onClick={() => setPage(currentPage - 1)}
            >
              <FontAwesomeIcon icon={faChevronLeft} />
            </button>
            {Array.from(
              { length: Math.min(5, pages) },
              (_, i) => Math.min(Math.max(0, currentPage - 2), Math.max(0, pages - 5)) + i,
            ).map((index) => (
              <button
                key={index}
                type="button"
                aria-label={`Page ${index + 1}`}
                aria-current={index === currentPage ? 'page' : undefined}
                onClick={() => setPage(index)}
              >
                {index + 1}
              </button>
            ))}
            <button
              type="button"
              aria-label="Next page"
              disabled={currentPage + 1 >= pages}
              onClick={() => setPage(currentPage + 1)}
            >
              <FontAwesomeIcon icon={faChevronRight} />
            </button>
          </nav>
        </footer>
      </section>
      {dialog && state && (
        <AccountDialog
          key={dialog.kind + dialog.users.map((user) => user.id).join(',')}
          dialog={dialog}
          currentUserId={state.me.id}
          onClose={() => setDialog(undefined)}
          onSaved={saved}
          onSwitch={(kind) => setDialog({ kind, users: dialog.users })}
        />
      )}
    </div>
  );
}

function AccountDialog({
  dialog,
  currentUserId,
  onClose,
  onSaved,
  onSwitch,
}: {
  dialog: Dialog;
  currentUserId: string;
  onClose: () => void;
  onSaved: (notice: Notice) => void;
  onSwitch: (kind: Dialog['kind']) => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const user = dialog.users[0];
  const self = user?.id === currentUserId;
  const [draft, setDraft] = useState({
    name: user?.name || '',
    surname: user?.surname || '',
    email: user?.email || '',
    organization: user?.organization || '',
    password: '',
    role: user?.role || 'user',
    is_active: user?.is_active ?? true,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    const element = ref.current;
    element?.showModal();
    return () => element?.close();
  }, []);
  const editing = dialog.kind === 'create' || dialog.kind === 'edit';
  const titles = {
    create: 'Create user',
    edit: 'Edit user',
    view: 'User details',
    manage: 'Manage account',
    block: 'Block account access',
    unblock: 'Restore account access',
    delete: 'Delete account',
  };
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      if (editing) {
        const payload = {
          name: draft.name.trim(),
          surname: draft.surname.trim(),
          email: draft.email.trim(),
          organization: draft.organization.trim(),
          ...(!self ? { role: draft.role, is_active: draft.is_active } : {}),
          ...(dialog.kind === 'create' ? { password: draft.password } : {}),
        };
        await request<User>(dialog.kind === 'create' ? '/users' : `/users/${user.id}`, {
          method: dialog.kind === 'create' ? 'POST' : 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        onSaved({
          kind: 'success',
          text:
            dialog.kind === 'create' ? 'User created successfully.' : 'User updated successfully.',
        });
      } else if (dialog.kind === 'delete') {
        await request<void>(`/users/${user.id}`, { method: 'DELETE' });
        onSaved({ kind: 'success', text: 'Account and its associated analyses were deleted.' });
      } else {
        const failures: string[] = [];
        let count = 0;
        for (const target of dialog.users) {
          try {
            await request<User>(`/users/${target.id}`, {
              method: 'PATCH',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ is_active: dialog.kind === 'unblock' }),
            });
            count++;
          } catch (e) {
            failures.push((e as Error).message);
          }
        }
        onSaved({
          kind: failures.length ? 'error' : 'success',
          text: `${count} of ${dialog.users.length} accounts ${dialog.kind === 'unblock' ? 'unblocked' : 'blocked'}.${failures.length ? ' ' + [...new Set(failures)].join(' ') : ''}`,
        });
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <dialog
      ref={ref}
      className={styles.dialog}
      aria-labelledby="managed-account-title"
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
    >
      <header className={styles.dialogHeader}>
        <h2 id="managed-account-title">{titles[dialog.kind]}</h2>
        <button type="button" aria-label="Close dialog" disabled={busy} onClick={onClose}>
          <FontAwesomeIcon icon={faXmark} />
        </button>
      </header>
      <div className={styles.dialogBody}>
        {error && (
          <p role="alert" className={styles.notice + ' ' + styles.error}>
            {error}
          </p>
        )}
        {editing ? (
          <form onSubmit={submit} aria-label={titles[dialog.kind]} aria-busy={busy}>
            <fieldset disabled={busy} className={styles.form}>
              <label>
                First name
                <input
                  name="name"
                  autoComplete="off"
                  required
                  maxLength={100}
                  value={draft.name}
                  onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                />
              </label>
              <label>
                Last name
                <input
                  name="surname"
                  autoComplete="off"
                  required
                  maxLength={100}
                  value={draft.surname}
                  onChange={(e) => setDraft({ ...draft, surname: e.target.value })}
                />
              </label>
              <label className={styles.full}>
                Email
                <input
                  name="email"
                  type="email"
                  autoComplete="off"
                  required
                  maxLength={254}
                  value={draft.email}
                  onChange={(e) => setDraft({ ...draft, email: e.target.value })}
                />
              </label>
              <label className={styles.full}>
                Organization <span>(optional)</span>
                <input
                  name="organization"
                  autoComplete="off"
                  maxLength={200}
                  value={draft.organization}
                  onChange={(e) => setDraft({ ...draft, organization: e.target.value })}
                />
              </label>
              {dialog.kind === 'create' && (
                <label className={styles.full}>
                  Initial password
                  <input
                    name="password"
                    type="password"
                    autoComplete="new-password"
                    required
                    minLength={8}
                    maxLength={1024}
                    value={draft.password}
                    onChange={(e) => setDraft({ ...draft, password: e.target.value })}
                  />
                  <small>At least 8 characters.</small>
                </label>
              )}
              <label>
                Role
                <select
                  name="role"
                  value={draft.role}
                  disabled={self}
                  onChange={(e) => setDraft({ ...draft, role: e.target.value as User['role'] })}
                >
                  <option value="user">User</option>
                  <option value="admin">Administrator</option>
                </select>
              </label>
              <label>
                Status
                <select
                  name="status"
                  value={draft.is_active ? 'active' : 'blocked'}
                  disabled={self}
                  onChange={(e) => setDraft({ ...draft, is_active: e.target.value === 'active' })}
                >
                  <option value="active">Active</option>
                  <option value="blocked">Blocked</option>
                </select>
              </label>
              {self && (
                <p className={styles.help + ' ' + styles.full}>
                  Your own administrator role and account access are protected.
                </p>
              )}
            </fieldset>
            <footer className={styles.dialogFooter}>
              <button type="button" className={styles.button} disabled={busy} onClick={onClose}>
                Cancel
              </button>
              <button
                type="submit"
                className={styles.button + ' ' + styles.primary}
                disabled={busy}
              >
                {busy ? 'Saving...' : dialog.kind === 'create' ? 'Create user' : 'Save changes'}
              </button>
            </footer>
          </form>
        ) : dialog.kind === 'view' || dialog.kind === 'manage' ? (
          <>
            <div className={styles.dialogIdentity}>
              <span className={styles.avatar}>
                {user.name[0]}
                {user.surname[0]}
              </span>
              <div>
                <h3>
                  {user.name} {user.surname}
                </h3>
                <p>{user.email}</p>
              </div>
            </div>
            <dl className={styles.details}>
              {[
                ['Organization', user.organization || 'Not provided'],
                ['Role', user.role === 'admin' ? 'Administrator' : 'User'],
                ['Status', user.is_active ? 'Active' : 'Blocked'],
                ['Registered', registered(user.created_at)],
                ['Analyses', String(user.analysis_count ?? 0)],
              ].map(([label, value]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
            <footer className={styles.dialogFooter}>
              <button type="button" className={styles.button} onClick={() => onSwitch('edit')}>
                Edit user
              </button>
              {dialog.kind === 'manage' && (
                <>
                  <button
                    className={styles.button}
                    disabled={self}
                    onClick={() => onSwitch(user.is_active ? 'block' : 'unblock')}
                  >
                    {user.is_active ? 'Block access' : 'Unblock access'}
                  </button>
                  <button
                    className={styles.button + ' ' + styles.danger}
                    disabled={self}
                    onClick={() => onSwitch('delete')}
                  >
                    Delete account
                  </button>
                </>
              )}
            </footer>
            {self && dialog.kind === 'manage' && (
              <p className={styles.help}>
                You cannot block or delete your own administrator account.
              </p>
            )}
          </>
        ) : (
          <form onSubmit={submit} aria-busy={busy}>
            <p className={styles.confirm}>
              {dialog.kind === 'delete'
                ? `Permanently delete ${user.name} ${user.surname} and all their analyses, evidence and AI reports? This cannot be undone.`
                : `${dialog.kind === 'unblock' ? 'Restore' : 'Block'} access for ${dialog.users.length === 1 ? user.name + ' ' + user.surname : dialog.users.length + ' selected accounts'}?`}
            </p>
            {dialog.kind === 'block' && (
              <p className={styles.help}>
                Blocked accounts cannot sign in or continue using existing sessions. Their data is
                retained.
              </p>
            )}
            <footer className={styles.dialogFooter}>
              <button type="button" className={styles.button} disabled={busy} onClick={onClose}>
                Cancel
              </button>
              <button
                type="submit"
                className={
                  styles.button + ' ' + (dialog.kind === 'delete' ? styles.danger : styles.primary)
                }
                disabled={busy}
              >
                {busy
                  ? 'Updating...'
                  : dialog.kind === 'delete'
                    ? 'Delete account permanently'
                    : dialog.kind === 'unblock'
                      ? 'Unblock access'
                      : 'Block access'}
              </button>
            </footer>
          </form>
        )}
      </div>
    </dialog>
  );
}
