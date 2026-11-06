import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/session";
import { useAsync, useTitle } from "../lib/hooks";
import { Mark } from "../ui/icons";
import { Banner, Button, Field, TextInput } from "../ui/ui";

const DEMOS = [
  { role: "Администратор", email: "admin@example.com", password: "admin123", note: "пользователи и реестр" },
  { role: "Специалист", email: "specialist@example.com", password: "specialist123", note: "Мария Смирнова" },
  { role: "Руководитель", email: "manager@example.com", password: "manager123", note: "Алексей Орлов" },
  { role: "Клиент", email: "client@example.com", password: "client123", note: "ООО Ромашка" },
];

export function LoginPage() {
  useTitle("Вход");
  const navigate = useNavigate();
  const { login } = useAuth();
  const health = useAsync(() => api.health(), []);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!email.trim() || !password) {
      setError("Введите почту и пароль");
      return;
    }
    setPending(true);
    setError(null);
    try {
      await login(email, password);
      navigate("/", { replace: true });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось войти");
    } finally {
      setPending(false);
    }
  }

  const healthClass = health.status === "ready" && health.data?.database === "ok" ? "ok" : health.status === "error" ? "bad" : "";
  const healthText =
    health.status === "loading"
      ? "Проверяем API…"
      : health.status === "ready" && health.data?.database === "ok"
        ? "API на связи"
        : "API не отвечает на порту 8000";

  return (
    <div className="login">
      <a className="skip" href="#login-form">
        К форме входа
      </a>
      <div className="login-sheet">
        <header className="login-band">
          <Mark size={36} />
          <div className="login-brand">
            <p className="wordmark">Верконт</p>
            <p>Учёт версий и план обновлений конфигураций 1С</p>
          </div>
        </header>
        <div className="login-grid">
          <main className="login-main">
            <h1>Вход</h1>
            <p className="lede">Рабочая консоль: какая база отстала от релиза, кому уже сообщили и на какой день стоит обновление.</p>
            <form id="login-form" className="stack login-form" onSubmit={onSubmit}>
              {error ? <Banner>{error}</Banner> : null}
              <Field label="Почта">
                <TextInput
                  type="email"
                  autoComplete="username"
                  autoCapitalize="none"
                  spellCheck={false}
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                />
              </Field>
              <Field label="Пароль">
                <TextInput
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                />
              </Field>
              <label className="check">
                <input type="checkbox" checked={showPassword} onChange={(event) => setShowPassword(event.target.checked)} />
                Показать пароль
              </label>
              <Button type="submit" disabled={pending}>
                {pending ? "Входим…" : "Войти"}
              </Button>
            </form>
          </main>
          <aside className="login-side">
            <p className="demo-caption">
              Учебный стенд. Пароли ниже не для рабочей среды.
            </p>
            {DEMOS.map((demo) => (
              <button
                key={demo.email}
                type="button"
                className={email === demo.email ? "demo-row is-on" : "demo-row"}
                onClick={() => {
                  setEmail(demo.email);
                  setPassword(demo.password);
                  setError(null);
                }}
              >
                <span>
                  <b>{demo.role}</b>
                  <small>{demo.note}</small>
                </span>
                <span className="mono demo-pass">{demo.password}</span>
                <small className="demo-mail">{demo.email}</small>
              </button>
            ))}
            <p className="login-note">Сверка установленных версий с релизом, письмо клиенту и окно записи.</p>
            <p className={healthClass ? `health ${healthClass}` : "health"}>
              <i />
              {healthText}
            </p>
            <p className="login-foot">Control_1C_version · локальный контур</p>
          </aside>
        </div>
      </div>
    </div>
  );
}
