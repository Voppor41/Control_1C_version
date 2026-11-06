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
      <aside className="login-aside">
        <div>
          <div className="brand-lockup">
            <Mark size={28} />
            <span>Консоль сопровождения</span>
          </div>
          <h1 className="wordmark">Норд</h1>
          <hr className="rule" />
          <p className="login-lead">
            Видно, какая база отстала от релиза, кому уже сообщили и на какой день стоит обновление.
          </p>
          <ul className="login-points">
            <li>
              <span>01</span>Сверка установленных и текущих версий
            </li>
            <li>
              <span>02</span>Уведомление клиенту в один шаг
            </li>
            <li>
              <span>03</span>Окна записи и статусы работ
            </li>
          </ul>
        </div>
        <p className="login-foot">Control_1C_version · локальный контур</p>
      </aside>
      <main className="login-main">
        <div className="login-card">
          <h2>Вход</h2>
          <p className="lede">Рабочая консоль фирмы, которая сопровождает конфигурации 1С.</p>
          <form id="login-form" className="stack" style={{ marginTop: 22 }} onSubmit={onSubmit}>
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
          <div className="demo">
            <p className="demo-caption">
              Демонстрационные входы. Пароли на этой карточке — только для учебного стенда, не для рабочей среды.
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
                  <small style={{ display: "block" }}>{demo.note}</small>
                </span>
                <small>{demo.email}</small>
                <span className="mono">{demo.password}</span>
              </button>
            ))}
            <p className={healthClass ? `health ${healthClass}` : "health"}>
              <i />
              {healthText}
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
