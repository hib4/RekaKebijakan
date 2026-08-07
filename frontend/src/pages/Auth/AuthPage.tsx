import { useId, useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "../../api/client";
import { useAuth } from "../../auth/useAuth";
import { safeNext } from "../../auth/navigation";
import { Brand } from "../../components/Header/Header";
import "./AuthPage.css";

type AuthPageProps = {
  mode: "login" | "register";
};

type PasswordFieldProps = {
  id: string;
  name: string;
  label: string;
  autoComplete: string;
  disabled: boolean;
  hint?: string;
};

function PasswordVisibilityIcon({ visible }: { visible: boolean }) {
  return (
    <svg className="password-eye-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      {visible ? (
        <>
          <path d="M3 3l18 18" />
          <path d="M10.6 10.7a2 2 0 0 0 2.7 2.7" />
          <path d="M9.2 5.4A9.6 9.6 0 0 1 12 5c5.5 0 8.5 5 9 7-.3 1.1-1.4 3-3.3 4.5" />
          <path d="M6.4 6.9C4.5 8.2 3.4 10.5 3 12c.5 2 3.5 7 9 7 1.5 0 2.8-.4 4-1" />
        </>
      ) : (
        <>
          <path d="M3 12s3.2-7 9-7 9 7 9 7-3.2 7-9 7-9-7-9-7Z" />
          <path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" />
        </>
      )}
    </svg>
  );
}

function PasswordField({ id, name, label, autoComplete, disabled, hint }: PasswordFieldProps) {
  const [visible, setVisible] = useState(false);
  const toggleLabel = visible ? `Sembunyikan ${label.toLowerCase()}` : `Tampilkan ${label.toLowerCase()}`;

  return (
    <div className="field auth-password-field">
      <label htmlFor={id}>{label}</label>
      <div className="auth-password-control">
        <input
          id={id}
          name={name}
          type={visible ? "text" : "password"}
          autoComplete={autoComplete}
          required
          minLength={6}
          maxLength={128}
          disabled={disabled}
        />
        <button
          type="button"
          aria-label={toggleLabel}
          aria-pressed={visible}
          title={toggleLabel}
          onClick={() => setVisible((current) => !current)}
          disabled={disabled}
        >
          <PasswordVisibilityIcon visible={visible} />
        </button>
      </div>
      {hint && <small>{hint}</small>}
    </div>
  );
}

function errorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Email atau kata sandi tidak sesuai.";
    if (error.status === 409) return "Email tersebut sudah terdaftar.";
    if (error.status === 422) return "Periksa kembali data yang Anda masukkan.";
    return error.message;
  }
  return "Layanan autentikasi tidak dapat dihubungi. Silakan coba lagi.";
}

export default function AuthPage({ mode }: AuthPageProps) {
  const { loading, user, login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const errorId = useId();
  const isRegister = mode === "register";
  const params = new URLSearchParams(location.search);
  const next = safeNext(params.get("next"));

  if (!loading && user) {
    return <Navigate to={next} replace />;
  }

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    const data = new FormData(event.currentTarget);
    const email = String(data.get("email") ?? "").trim();
    const password = String(data.get("password") ?? "");
    const passwordConfirmation = String(data.get("password-confirmation") ?? "");
    if (isRegister && password !== passwordConfirmation) {
      setError("Konfirmasi kata sandi tidak sama.");
      setSubmitting(false);
      return;
    }
    try {
      if (isRegister) {
        await register({ name: String(data.get("name") ?? "").trim(), email, password });
      } else {
        await login({ email, password });
      }
      navigate(next, { replace: true });
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="auth-page">
      <section className="auth-context" aria-labelledby="auth-context-title">
        <Brand />
        <div>
          <p className="auth-kicker">Ruang kerja simulasi kebijakan</p>
          <h1 id="auth-context-title">Uji asumsi sebelum kebijakan diterapkan.</h1>
          <p>
            Susun skenario, telusuri respons stakeholder sintetis, dan simpan
            setiap temuan dalam ruang kerja institusi Anda.
          </p>
        </div>
        <p className="auth-responsibility">Keputusan tetap di tangan manusia.</p>
      </section>
      <section className="auth-form-panel" aria-labelledby="auth-title">
        <div className="auth-form-wrap">
          <Link className="auth-back" to="/">
            ← Kembali ke beranda
          </Link>
          <p className="eyebrow">{isRegister ? "Buat akun" : "Akses ruang kerja"}</p>
          <h2 id="auth-title">{isRegister ? "Daftar ke RekaKebijakan" : "Masuk ke RekaKebijakan"}</h2>
          <p className="auth-intro">
            {isRegister
              ? "Gunakan email kerja untuk membuat ruang kerja Anda."
              : "Masukkan kredensial akun untuk melanjutkan."}
          </p>
          <form onSubmit={submit} aria-describedby={error ? errorId : undefined}>
            {isRegister && (
              <div className="field">
                <label htmlFor="auth-name">Nama lengkap</label>
                <input id="auth-name" name="name" autoComplete="name" required minLength={2} disabled={submitting} />
              </div>
            )}
            <div className="field">
              <label htmlFor="auth-email">Email</label>
              <input id="auth-email" name="email" type="email" autoComplete="email" inputMode="email" required disabled={submitting} />
            </div>
            <PasswordField
              id="auth-password"
              name="password"
              label="Kata sandi"
              autoComplete={isRegister ? "new-password" : "current-password"}
              disabled={submitting}
              hint={isRegister ? "Gunakan minimal 6 karakter." : undefined}
            />
            {isRegister && (
              <PasswordField
                id="auth-password-confirmation"
                name="password-confirmation"
                label="Konfirmasi kata sandi"
                autoComplete="new-password"
                disabled={submitting}
              />
            )}
            {error && <p className="auth-error" id={errorId} role="alert">{error}</p>}
            <button className={`button primary auth-submit ${submitting ? "loading" : ""}`} type="submit" disabled={submitting || loading}>
              <span>{submitting ? "Memproses" : isRegister ? "Buat akun" : "Masuk"}</span>
              {!submitting && <b aria-hidden="true">→</b>}
            </button>
          </form>
          <p className="auth-switch">
            {isRegister ? "Sudah memiliki akun?" : "Belum memiliki akun?"}{" "}
            <Link to={`${isRegister ? "/login" : "/register"}${params.has("next") ? `?next=${encodeURIComponent(next)}` : ""}`}>
              {isRegister ? "Masuk" : "Daftar"}
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}
