import { loginAction } from './actions';

export const metadata = {
  title: 'Sign in — JobLandAgent',
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | undefined }>;
}) {
  const params = await searchParams;
  const hasError = params.error === '1';

  return (
    <div
      className="flex items-center justify-center"
      style={{ minHeight: 'calc(100vh - 2.5rem)', background: 'var(--bg)' }}
    >
      <form
        action={loginAction}
        className="flex flex-col gap-4 w-full"
        style={{
          maxWidth: '20rem',
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: '0.75rem',
          padding: '1.75rem',
        }}
      >
        <div className="flex flex-col gap-1">
          <h1 className="text-lg logo-text font-data" style={{ fontWeight: 600 }}>
            JobLandAgent
          </h1>
          <p className="text-sm" style={{ color: 'var(--text-2)' }}>
            Sign in to continue
          </p>
        </div>

        {hasError ? (
          <div
            className="text-sm font-data"
            style={{
              color: 'var(--red)',
              background: 'var(--red-bg)',
              border: '1px solid var(--red-border)',
              borderRadius: '0.5rem',
              padding: '0.5rem 0.75rem',
            }}
          >
            Invalid email or password.
          </div>
        ) : null}

        <label className="flex flex-col gap-1 text-sm" style={{ color: 'var(--text-2)' }}>
          Email
          <input
            type="email"
            name="email"
            required
            autoComplete="username"
            autoFocus
            className="font-data text-sm outline-none"
            style={{
              background: 'var(--surface-hi)',
              border: '1px solid var(--border)',
              borderRadius: '0.5rem',
              padding: '0.5rem 0.75rem',
              color: 'var(--text-1)',
            }}
          />
        </label>

        <label className="flex flex-col gap-1 text-sm" style={{ color: 'var(--text-2)' }}>
          Password
          <input
            type="password"
            name="password"
            required
            autoComplete="current-password"
            className="font-data text-sm outline-none"
            style={{
              background: 'var(--surface-hi)',
              border: '1px solid var(--border)',
              borderRadius: '0.5rem',
              padding: '0.5rem 0.75rem',
              color: 'var(--text-1)',
            }}
          />
        </label>

        <button
          type="submit"
          className="text-sm font-data transition-colors"
          style={{
            background: 'var(--green-bg)',
            border: '1px solid var(--green-border)',
            color: 'var(--green)',
            borderRadius: '0.5rem',
            padding: '0.5rem 0.75rem',
            fontWeight: 500,
          }}
        >
          Sign in
        </button>
      </form>
    </div>
  );
}
