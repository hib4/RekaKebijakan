import { useEffect, useId, useState } from "react";
import type { FormEvent } from "react";
import { ApiError } from "../../api/client";
import { useAuth } from "../../auth/useAuth";
import { navigate, safeNext } from "../../auth/navigation";
import { Brand } from "../../components/Header/Header";
import "./AuthPage.css";

type AuthPageProps = {
  mode: "login" | "register";
};

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
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const errorId = useId();
  const isRegister = mode === "register";
  const params = new URLSearchParams(window.location.search);
  const next = safeNext(params.get("next"));

  useEffect(() => {
    if (!loading && user) navigate(next, true);
  }, [loading, next, user]);

  if (!loading && user) {
    return null;
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
      navigate(next, true);
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
          <a className="auth-back" href="/" onClick={(event) => { event.preventDefault(); navigate("/"); }}>
            ← Kembali ke beranda
          </a>
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
            <div className="field auth-password-field">
              <label htmlFor="auth-password">Kata sandi</label>
              <div className="auth-password-control">
                <input
                  id="auth-password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete={isRegister ? "new-password" : "current-password"}
                  required
                  minLength={6}
                  maxLength={128}
                  disabled={submitting}
                />
                <button type="button" aria-pressed={showPassword} onClick={() => setShowPassword((visible) => !visible)} disabled={submitting}>
                  {showPassword ? "Sembunyikan" : "Tampilkan"}
                </button>
              </div>
              {isRegister && <small>Gunakan minimal 6 karakter.</small>}
            </div>
            {isRegister && (
              <div className="field">
                <label htmlFor="auth-password-confirmation">Konfirmasi kata sandi</label>
                <input
                  id="auth-password-confirmation"
                  name="password-confirmation"
                  type={showPassword ? "text" : "password"}
                  autoComplete="new-password"
                  required
                  minLength={6}
                  maxLength={128}
                  disabled={submitting}
                />
              </div>
            )}
            {error && <p className="auth-error" id={errorId} role="alert">{error}</p>}
            <button className={`button primary auth-submit ${submitting ? "loading" : ""}`} type="submit" disabled={submitting || loading}>
              <span>{submitting ? "Memproses" : isRegister ? "Buat akun" : "Masuk"}</span>
              {!submitting && <b aria-hidden="true">→</b>}
            </button>
          </form>
          <p className="auth-switch">
            {isRegister ? "Sudah memiliki akun?" : "Belum memiliki akun?"}{" "}
            <a href={isRegister ? "/login" : "/register"} onClick={(event) => {
              event.preventDefault();
              const destination = isRegister ? "/login" : "/register";
              navigate(params.has("next") ? `${destination}?next=${encodeURIComponent(next)}` : destination);
            }}>
              {isRegister ? "Masuk" : "Daftar"}
            </a>
          </p>
        </div>
      </section>
    </main>
  );
}
