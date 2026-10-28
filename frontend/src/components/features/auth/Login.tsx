import { Button, Checkbox, Label, TextInput } from 'flowbite-react';
import AuthLayout from '../../shared/AuthLayout';
import Alert from '../../shared/Alert';
import ModalView from '../../shared/Modal';
import ForgotPasswordUI from '../../business/ForgotPasswordUI';

import { userLoginAuth } from '../../../utils/auth';
import { useNavigate } from 'react-router-dom';
import { useState, type FormEvent } from 'react';

type LoginType = {
  loginAdmin: boolean;
  setloginAdmin: React.Dispatch<React.SetStateAction<boolean>>;
};

const Login = ({ loginAdmin, setloginAdmin }: LoginType) => {
  const navigate = useNavigate();
  const [isModalOpen, setisModalOpen] = useState(false);
  const [isActiveUser, setisActiveUser] = useState(true);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting) return;
    setError('');
    setIsSubmitting(true);
    const data = new FormData(event.currentTarget);
    try {
      const result = await userLoginAuth(String(data.get('email')), String(data.get('password')));
      setloginAdmin(result.user.role === 'admin');
      navigate(result.user.role === 'admin' ? '/admin/getUsers' : '/user/dashboard', {
        replace: true,
      });
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Login failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  }

  function showSignUpPage() {
    navigate('/signup');
  }

  return (
    <AuthLayout title="Welcome back!" isloginAdmin={loginAdmin}>
      {isModalOpen && (
        <ModalView
          modalSize="lg"
          modalTitle="We'll help you to restore your password"
          subText="Enter your details to get a restore link"
          onClose={() => {
            setisModalOpen(false);
          }}
        >
          <ForgotPasswordUI
            onClose={() => {
              setisModalOpen(false);
            }}
          />
        </ModalView>
      )}
      <form
        onSubmit={handleLogin}
        className="ms-auto me-auto max-w-md w-[100%] flex flex-col gap-6"
      >
        {error && (
          <Alert
            alertType="danger"
            alertTitle="Login failed"
            alertInfo={error}
            onClose={() => setError('')}
          />
        )}
        <div className="w-full flex pb-3">
          <div className="ms-auto me-auto w-[10rem] flex justify-between text-lg text-gray-600">
            <label
              className={`hover:text-gray-300 hover:cursor-pointer ${isActiveUser ? '!text-white' : ''}`}
              onClick={() => {
                setloginAdmin(false);
                setisActiveUser(true);
              }}
            >
              User
            </label>
            <label
              className={`hover:text-gray-300 hover:cursor-pointer ${!isActiveUser ? '!text-white' : ''}`}
              onClick={() => {
                setloginAdmin(true);
                setisActiveUser(false);
              }}
            >
              Admin
            </label>
          </div>
        </div>
        <div>
          <div className="mb-2 block">
            <Label htmlFor="email_">Your email</Label>
          </div>
          <TextInput
            id="email_"
            name="email"
            autoComplete="username"
            type="email"
            placeholder="name@flowbite.com"
            required
          />
        </div>
        <div>
          <div className="mb-2 block">
            <Label htmlFor="password_">Your password</Label>
          </div>
          <TextInput
            id="password_"
            name="password"
            autoComplete="current-password"
            type="password"
            required
          />
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 w-full">
          <div className="min-h-11 text-start flex items-center gap-2">
            <Checkbox id="remember" />
            <Label htmlFor="remember">Remember me</Label>
          </div>
          <div className="min-h-11 flex items-center text-[#1C64F2]">
            <a
              className="cursor-pointer text-[#3FDDBB] hover:text-[#2FC9A8]!"
              onClick={() => {
                setisModalOpen(true);
              }}
            >
              Forgot password?
            </a>
          </div>
        </div>
        <div className="flex flex-col sm:flex-row gap-3 w-full">
          <Button
            type="submit"
            disabled={isSubmitting}
            className="w-full sm:flex-1 hover:cursor-pointer !bg-[#3FDDBB] hover:bg-[#2FC9A8]!"
          >
            {isSubmitting ? 'Signing in...' : 'Submit'}
          </Button>
          <Button
            type="button"
            onClick={() => {
              showSignUpPage();
            }}
            className="w-full sm:flex-1 border border-[#3FDDBB] !bg-transparent hover:cursor-pointer hover:!bg-[#2FC9A8]"
          >
            Sign up
          </Button>
        </div>
      </form>
    </AuthLayout>
  );
};

export default Login;
