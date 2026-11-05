import { useEffect, useRef, useState, type FormEvent } from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
  faUser,
  faBuilding,
  faPen,
  faLock,
  faChevronRight,
} from '@fortawesome/free-solid-svg-icons';
import styles from './Profile.module.css';
import { BACKEND_URL, BACKEND_PORT } from '../../../constants';
import { clearAuth } from '../../utils/auth';

type User = {
  id: string;
  name: string;
  surname: string;
  email: string;
  organization: string;
  role: 'user' | 'admin';
  is_active: boolean;
  created_at: string;
};
type Draft = Pick<User, 'name' | 'surname' | 'email' | 'organization'>;
type Notice = { kind: 'success' | 'error'; text: string };
const button = styles.button;
const primary = styles.button + ' ' + styles.primary;
const input = styles.control;
const label = styles.fieldLabel;

async function profileRequest<T>(suffix = '', options?: RequestInit): Promise<T> {
  const token = sessionStorage.getItem('access_token');
  const response = await fetch(`${BACKEND_URL}:${BACKEND_PORT}/api/users/me${suffix}`, {
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
  if (!response.ok) {
    const detail = body.detail;
    throw new Error(
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail
              .map((entry: { msg: string }) => entry.msg.replace(/^Value error, /, ''))
              .join('. ')
          : 'The request could not be completed. Please try again.',
    );
  }
  return body as T;
}

function Detail({ title, value }: { title: string; value: string }) {
  return (
    <div className={styles.detail}>
      <dt>{title}</dt>
      <dd>{value}</dd>
    </div>
  );
}

export default function Profile() {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<{ attempt: number; user?: User; error?: string }>();
  const [section, setSection] = useState<'profile' | 'password' | null>(null);
  const [draft, setDraft] = useState<Draft>({ name: '', surname: '', email: '', organization: '' });
  const [passwords, setPasswords] = useState({ current: '', next: '', confirm: '' });
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice>();
  const firstField = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const controller = new AbortController();
    profileRequest<User>('', { signal: controller.signal })
      .then((user) => {
        if (!controller.signal.aborted) setState({ attempt, user });
      })
      .catch((e: Error) => {
        if (!controller.signal.aborted) setState({ attempt, error: e.message });
      });
    return () => controller.abort();
  }, [attempt]);
  useEffect(() => {
    firstField.current?.focus();
  }, [section]);
  const current = state?.attempt === attempt ? state : undefined;
  const user = current?.user;
  const registration = user
    ? new Date(
        user.created_at.endsWith('Z') || user.created_at.includes('+')
          ? user.created_at
          : user.created_at.replace(' ', 'T') + 'Z',
      ).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
    : '';
  function openSection(next: 'profile' | 'password') {
    if (!user) return;
    setDraft({
      name: user.name,
      surname: user.surname,
      email: user.email,
      organization: user.organization,
    });
    setPasswords({ current: '', next: '', confirm: '' });
    setNotice(undefined);
    setSection(next);
  }
  function cancel() {
    setSection(null);
    setNotice(undefined);
    setPasswords({ current: '', next: '', confirm: '' });
  }
  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setNotice(undefined);
    try {
      const updated = await profileRequest<User>('', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: draft.name.trim(),
          surname: draft.surname.trim(),
          email: draft.email.trim(),
          organization: draft.organization.trim(),
        }),
      });
      setState({ attempt, user: updated });
      setSection(null);
      setNotice({ kind: 'success', text: 'Profile updated successfully.' });
    } catch (e) {
      setNotice({ kind: 'error', text: (e as Error).message });
    } finally {
      setBusy(false);
    }
  }
  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    if (passwords.next !== passwords.confirm) {
      setNotice({ kind: 'error', text: 'New passwords do not match.' });
      return;
    }
    if (passwords.next === passwords.current) {
      setNotice({ kind: 'error', text: 'Choose a password different from your current password.' });
      return;
    }
    if (!(
      /[A-Z]/.test(passwords.next) &&
      /[a-z]/.test(passwords.next) &&
      /[0-9]/.test(passwords.next) &&
      /[^a-zA-Z0-9\s]/.test(passwords.next)
    )) {
      setNotice({ kind: 'error', text: 'Include uppercase, lowercase, a number and a symbol.' });
      return;
    }
    setBusy(true);
    setNotice(undefined);
    try {
      await profileRequest<void>('/password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          current_password: passwords.current,
          new_password: passwords.next,
          confirm_password: passwords.confirm,
        }),
      });
      setPasswords({ current: '', next: '', confirm: '' });
      setSection(null);
      setNotice({
        kind: 'success',
        text: 'Password changed successfully. Use your new password the next time you sign in.',
      });
    } catch (e) {
      setNotice({ kind: 'error', text: (e as Error).message });
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className={styles.page}>
      <div className={styles.breadcrumb}>
        <FontAwesomeIcon icon={faUser} />
        <span>Profile</span>
      </div>
      <header className={styles.heading}>
        <h1>Account Settings</h1>
        <p>Manage your personal information and security settings.</p>
      </header>
      {!current && (
        <p role="status" className={styles.panel + ' ' + styles.loading}>
          Loading account settings...
        </p>
      )}
      {current?.error && (
        <div role="alert" className={styles.notice + ' ' + styles.error}>
          {current.error}
          <button
            type="button"
            className={button + ' ml-3'}
            onClick={() => setAttempt(attempt + 1)}
          >
            Try again
          </button>
        </div>
      )}
      {notice && (
        <div
          role={notice.kind === 'error' ? 'alert' : 'status'}
          className={styles.notice + (notice.kind === 'error' ? ' ' + styles.error : '')}
        >
          {notice.text}
        </div>
      )}
      {user && (
        <>
          <section className={styles.panel + ' ' + styles.identity} aria-label="Account identity">
            <span aria-hidden="true" className={styles.avatar}>
              {user.name[0]}
              {user.surname[0]}
            </span>
            <div className={styles.identityText}>
              <h2>
                {user.name} {user.surname}
              </h2>
              <p className={styles.email}>{user.email}</p>
              <div className={styles.identityMeta}>
                <span>
                  <FontAwesomeIcon icon={faBuilding} />
                  {user.organization || 'No organization specified'}
                </span>
                <span className={styles.separator} aria-hidden="true">
                  &bull;
                </span>
                <span>
                  <FontAwesomeIcon icon={faUser} />
                  {user.role === 'admin' ? 'Admin' : 'User'}
                </span>
              </div>
            </div>
            <span className={styles.badge + (!user.is_active ? ' ' + styles.blocked : '')}>
              <span className={styles.dot} aria-hidden="true" />
              {user.is_active ? 'Active' : 'Blocked'}
            </span>
          </section>
          <div className={styles.grid}>
            <section
              className={styles.panel + ' ' + styles.personal}
              aria-labelledby="personal-information"
            >
              <div className={styles.sectionHeader}>
                <div>
                  <h2 id="personal-information" className={styles.sectionTitle}>
                    Personal Information
                  </h2>
                  <p className={styles.description}>Update your account details.</p>
                </div>
                {section !== 'profile' && (
                  <button
                    type="button"
                    className={button}
                    disabled={busy}
                    onClick={() => openSection('profile')}
                  >
                    <FontAwesomeIcon icon={faPen} />
                    Edit Profile
                  </button>
                )}
              </div>
              {section === 'profile' ? (
                <form onSubmit={saveProfile} aria-label="Edit profile" aria-busy={busy}>
                  <fieldset disabled={busy} className="grid min-w-0 gap-4 sm:grid-cols-2">
                    <label className={label}>
                      First name
                      <input
                        ref={firstField}
                        className={input}
                        name="name"
                        autoComplete="given-name"
                        required
                        maxLength={100}
                        value={draft.name}
                        onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                      />
                    </label>
                    <label className={label}>
                      Last name
                      <input
                        className={input}
                        name="surname"
                        autoComplete="family-name"
                        required
                        maxLength={100}
                        value={draft.surname}
                        onChange={(e) => setDraft({ ...draft, surname: e.target.value })}
                      />
                    </label>
                    <label className={label + ' sm:col-span-2'}>
                      Email address
                      <input
                        className={input}
                        name="email"
                        type="email"
                        autoComplete="email"
                        required
                        maxLength={254}
                        value={draft.email}
                        onChange={(e) => setDraft({ ...draft, email: e.target.value })}
                      />
                    </label>
                    <label className={label + ' sm:col-span-2'}>
                      Organization <span className="font-normal text-slate-500">(optional)</span>
                      <input
                        className={input}
                        name="organization"
                        autoComplete="organization"
                        maxLength={200}
                        value={draft.organization}
                        onChange={(e) => setDraft({ ...draft, organization: e.target.value })}
                      />
                    </label>
                  </fieldset>
                  <div className="mt-5 flex flex-wrap gap-2 border-t border-slate-700 pt-4">
                    <button type="submit" disabled={busy} className={primary}>
                      {busy ? 'Saving...' : 'Save changes'}
                    </button>
                    <button type="button" disabled={busy} className={button} onClick={cancel}>
                      Cancel
                    </button>
                  </div>
                </form>
              ) : (
                <dl className={styles.details}>
                  <Detail title="First Name" value={user.name} />
                  <Detail title="Last Name" value={user.surname} />
                  <Detail title="Email Address" value={user.email} />
                  <Detail title="Organization" value={user.organization || 'Not provided'} />
                  <Detail title="Account Role" value={user.role === 'admin' ? 'Admin' : 'User'} />
                  <Detail title="Member Since" value={registration} />
                </dl>
              )}
              {section === 'profile' && (
                <dl className={styles.details + ' mt-5 border-t border-slate-700 pt-4'}>
                  <Detail
                    title="Account Role (read-only)"
                    value={user.role === 'admin' ? 'Admin' : 'User'}
                  />
                  <Detail title="Member Since" value={registration} />
                </dl>
              )}
            </section>
            <div className={styles.side}>
              <section
                className={styles.panel + ' ' + styles.security}
                aria-labelledby="account-security"
              >
                <h2 id="account-security" className={styles.sectionTitle}>
                  Security
                </h2>
                <p className={styles.description}>Manage your password and account access.</p>
                {section !== 'password' ? (
                  <button
                    type="button"
                    className={button + ' ' + styles.passwordAction}
                    disabled={busy}
                    onClick={() => openSection('password')}
                  >
                    <FontAwesomeIcon icon={faLock} />
                    Change Password
                    <FontAwesomeIcon icon={faChevronRight} />
                  </button>
                ) : (
                  <form
                    onSubmit={changePassword}
                    className="mt-4"
                    aria-label="Change password"
                    aria-busy={busy}
                  >
                    <fieldset disabled={busy} className="min-w-0 space-y-4">
                      <label className={label}>
                        Current password
                        <input
                          ref={firstField}
                          className={input}
                          type="password"
                          name="current_password"
                          autoComplete="current-password"
                          required
                          maxLength={1024}
                          value={passwords.current}
                          onChange={(e) => setPasswords({ ...passwords, current: e.target.value })}
                        />
                      </label>
                      <label className={label}>
                        New password
                        <input
                          className={input}
                          type="password"
                          name="new_password"
                          autoComplete="new-password"
                          required
                          minLength={8}
                          maxLength={1024}
                          aria-describedby="new-password-help"
                          value={passwords.next}
                          onChange={(e) => setPasswords({ ...passwords, next: e.target.value })}
                        />
                      </label>
                      <p id="new-password-help" className="text-xs leading-relaxed text-slate-400">
                        At least 8 characters with uppercase, lowercase, a number and a symbol.
                      </p>
                      <label className={label}>
                        Confirm new password
                        <input
                          className={input}
                          type="password"
                          name="confirm_password"
                          autoComplete="new-password"
                          required
                          minLength={8}
                          maxLength={1024}
                          value={passwords.confirm}
                          onChange={(e) => setPasswords({ ...passwords, confirm: e.target.value })}
                        />
                      </label>
                    </fieldset>
                    <div className="mt-5 flex flex-wrap gap-2">
                      <button type="submit" disabled={busy} className={primary}>
                        {busy ? 'Updating...' : 'Update password'}
                      </button>
                      <button type="button" disabled={busy} className={button} onClick={cancel}>
                        Cancel
                      </button>
                    </div>
                  </form>
                )}
              </section>
              <section
                className={styles.panel + ' ' + styles.accountStatus}
                aria-labelledby="account-status"
              >
                <h2 id="account-status" className={styles.sectionTitle}>
                  Account Status
                </h2>
                <p
                  className={
                    styles.statusValue + (!user.is_active ? ' ' + styles.statusBlocked : '')
                  }
                >
                  <span className={styles.dot} aria-hidden="true" />
                  {user.is_active ? 'Active' : 'Blocked'}
                </p>
                <p className={styles.statusDescription}>
                  {user.is_active
                    ? 'Your account is active and can access the platform.'
                    : 'Your account is blocked. Contact your workspace administrator.'}
                </p>
              </section>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
