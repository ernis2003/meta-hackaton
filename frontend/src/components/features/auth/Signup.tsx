import { Button, Label, TextInput } from 'flowbite-react';
import AuthLayout from '../../shared/AuthLayout';
import Alert from '../../shared/Alert';
import { useNavigate } from 'react-router-dom';
import { userSignUpAuth } from '../../../utils/auth';
import { useState, type FormEvent } from 'react';

const SignUp = ({ onAuthenticated }: { onAuthenticated: (isAdmin: boolean) => void }) => {
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const passwordsMatch = password.length > 0 && password === confirmPassword;
  const [showPasswordHelp, setShowPasswordHelp] = useState(false);
  const passwordRequirements = [
    { label: 'At least 8 characters', met: Array.from(password).length >= 8 },
    { label: 'An uppercase letter (e.g. A)', met: /\p{Lu}/u.test(password) },
    { label: 'A lowercase letter (e.g. a)', met: /\p{Ll}/u.test(password) },
    { label: 'A number (e.g. 1)', met: /[0-9]/.test(password) },
    { label: 'A special character (e.g. !, @, #)', met: /[\p{P}\p{S}]/u.test(password) },
  ];
  const fulfilledRequirements = passwordRequirements.filter(
    (requirement) => requirement.met,
  ).length;
  const isPasswordValid = fulfilledRequirements === passwordRequirements.length;
  const passwordBorderColors = [
    '[&_input]:border-b-red-500! [&_input:focus]:border-b-red-500!',
    '[&_input]:border-b-orange-600! [&_input:focus]:border-b-orange-600!',
    '[&_input]:border-b-orange-400! [&_input:focus]:border-b-orange-400!',
    '[&_input]:border-b-yellow-400! [&_input:focus]:border-b-yellow-400!',
    '[&_input]:border-b-lime-400! [&_input:focus]:border-b-lime-400!',
    '[&_input]:border-b-green-500! [&_input:focus]:border-b-green-500!',
  ];

  function showLoginPage() {
    navigate('/');
  }

  async function handleSignUp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting) return;
    setError('');
    const form = new FormData(event.currentTarget);
    const password = String(form.get('password'));
    if (!isPasswordValid) {
      setError(
        'Use at least 8 characters, an uppercase letter, a lowercase letter, a number and a special character.',
      );
      return;
    }
    if (password !== form.get('confirmPassword')) {
      setError('Passwords do not match.');
      return;
    }
    setIsSubmitting(true);
    try {
      await userSignUpAuth({
        name: String(form.get('name')),
        surname: String(form.get('surname')),
        email: String(form.get('email')),
        organization: String(form.get('organization')),
        password,
      });
      onAuthenticated(false);
      navigate('/user/dashboard', { replace: true });
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Registration failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  }
  return (
    <AuthLayout title="Let's secure future!" isloginAdmin={false} subtitle="Sign up as a user!">
      <form
        onSubmit={handleSignUp}
        className="ms-auto me-auto max-w-md w-[100%] flex flex-col gap-6"
      >
        {error && (
          <Alert
            alertType="danger"
            alertTitle="Registration failed"
            alertInfo={error}
            onClose={() => setError('')}
          />
        )}
        <div className="flex flex-col gap-4 sm:flex-row">
          <div className="w-full sm:flex-1 sm:min-w-0">
            <div className="mb-2 block">
              <Label htmlFor="name1">Name</Label>
            </div>
            <TextInput
              id="name1"
              name="name"
              autoComplete="given-name"
              type="text"
              placeholder="John"
              maxLength={100}
              required
            />
          </div>
          <div className="w-full sm:flex-1 sm:min-w-0">
            <div className="mb-2 block">
              <Label htmlFor="surname1">Surname</Label>
            </div>
            <TextInput
              id="surname1"
              name="surname"
              autoComplete="family-name"
              type="text"
              placeholder="Doe"
              maxLength={100}
              required
            />
          </div>
        </div>
        <div>
          <div className="mb-2 block">
            <Label htmlFor="email1">Your email</Label>
          </div>
          <TextInput
            id="email1"
            name="email"
            autoComplete="email"
            type="email"
            placeholder="name@flowbite.com"
            maxLength={254}
            required
          />
        </div>
        <div>
          <div className="mb-2 block">
            <Label htmlFor="organization">
              Organization <span className="!text-[grey]">(optional)</span>
            </Label>
          </div>
          <TextInput
            id="organization"
            name="organization"
            autoComplete="organization"
            type="text"
            placeholder="Walmart"
            maxLength={200}
          />
        </div>
        <div>
          <div className="mb-2 block">
            <div
              className="relative flex items-center gap-1"
              onKeyDown={(event) => {
                if (event.key === 'Escape') setShowPasswordHelp(false);
              }}
            >
              <Label htmlFor="password1">Your password</Label>
              <button
                type="button"
                aria-label="Password requirements"
                aria-expanded={showPasswordHelp}
                aria-controls="password-requirements"
                className="flex min-h-11 min-w-11 items-center justify-center rounded text-gray-400 hover:text-white focus-visible:outline-2 focus-visible:outline-blue-500"
                onMouseEnter={() => setShowPasswordHelp(true)}
                onMouseLeave={() => setShowPasswordHelp(false)}
                onBlur={() => setShowPasswordHelp(false)}
                onClick={() => setShowPasswordHelp(!showPasswordHelp)}
              >
                <span
                  aria-hidden="true"
                  className="flex h-5 w-5 items-center justify-center rounded-full border text-xs font-bold"
                >
                  ?
                </span>
              </button>
              <div
                id="password-requirements"
                hidden={!showPasswordHelp}
                className="absolute left-0 top-full z-10 w-full rounded-lg border border-gray-600 bg-gray-800 p-4 text-sm text-white shadow-lg"
              >
                <p className="mb-2 font-semibold">Your password must contain:</p>
                <ul className="space-y-1">
                  {passwordRequirements.map(({ label, met }) => (
                    <li key={label} className={met ? 'text-green-400' : 'text-gray-300'}>
                      <span aria-hidden="true">{met ? '\u2713' : '\u2022'} </span>
                      {label}
                      <span className="sr-only">{met ? ' (met)' : ' (not met)'}</span>
                    </li>
                  ))}
                </ul>
                <p className="mt-3 text-gray-300">
                  Example: <code>MysteryKey123!</code>
                </p>
              </div>
            </div>
          </div>
          <TextInput
            id="password1"
            name="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            aria-describedby="password-requirements password-status"
            aria-invalid={password.length > 0 && !isPasswordValid}
            className={`[&_input]:border-b-2 [&_input]:transition-colors [&_input]:duration-200 ${passwordBorderColors[fulfilledRequirements]}`}
            autoComplete="new-password"
            type="password"
            minLength={8}
            maxLength={1024}
            required
          />
          <p id="password-status" className="sr-only">
            {isPasswordValid
              ? 'Password meets all requirements.'
              : `${fulfilledRequirements} of ${passwordRequirements.length} password requirements met.`}
          </p>
        </div>
        <div>
          <div className="mb-2 block">
            <Label htmlFor="confirmPassword">Confirm password</Label>
          </div>
          <TextInput
            id="confirmPassword"
            name="confirmPassword"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            aria-invalid={confirmPassword.length > 0 && !passwordsMatch}
            className={`[&_input]:border-b-2 [&_input]:transition-colors [&_input]:duration-200 ${
              passwordsMatch
                ? '[&_input]:border-b-green-500! [&_input:focus]:border-b-green-500!'
                : '[&_input]:border-b-red-500! [&_input:focus]:border-b-red-500!'
            }`}
            autoComplete="new-password"
            type="password"
            minLength={8}
            maxLength={1024}
            required
          />
        </div>
        <div className="flex flex-col sm:flex-row gap-3 w-full mt-2">
          <Button
            type="submit"
            disabled={isSubmitting}
            className="w-full sm:flex-1 hover:cursor-pointer !bg-[#3FDDBB] hover:bg-[#2FC9A8]!"
          >
            {isSubmitting ? 'Creating account...' : 'Create account'}
          </Button>
          <Button
            type="button"
            onClick={() => {
              showLoginPage();
            }}
            className="w-full sm:flex-1 border border-[#3FDDBB] !bg-transparent hover:cursor-pointer hover:!bg-[#2FC9A8]"
          >
            Log in
          </Button>
        </div>
      </form>
    </AuthLayout>
  );
};
export default SignUp;
