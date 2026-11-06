import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { api } from "../api/client";
import type { RoleCode } from "../api/types";
import { useAuth } from "../auth/session";
import { initials } from "../lib/format";
import { useAsync } from "../lib/hooks";
import { roleLabel } from "../lib/labels";
import { Icon, Mark, type IconName } from "./icons";

type Item = {
  to: string;
  label: string;
  icon: IconName;
  end?: boolean;
  roles: RoleCode[];
};

const GROUPS: { label: string; items: Item[] }[] = [
  {
    label: "Сегодня",
    items: [{ to: "/", label: "Обзор", icon: "home", end: true, roles: ["admin", "specialist", "manager", "client"] }],
  },
  {
    label: "Клиенты",
    items: [
      { to: "/clients", label: "Организации", icon: "building", roles: ["admin", "specialist", "manager"] },
      { to: "/clients", label: "Моя организация", icon: "building", roles: ["client"] },
      { to: "/installations", label: "Установки", icon: "layers", roles: ["admin", "specialist", "manager"] },
      { to: "/installations", label: "Мои базы", icon: "layers", roles: ["client"] },
    ],
  },
  {
    label: "Каталог",
    items: [
      { to: "/configurations", label: "Конфигурации", icon: "book", roles: ["admin", "specialist", "manager", "client"] },
      { to: "/checks", label: "Проверки", icon: "pulse", roles: ["admin", "specialist", "manager"] },
    ],
  },
  {
    label: "План",
    items: [
      { to: "/notifications", label: "Уведомления", icon: "bell", roles: ["admin", "specialist", "manager", "client"] },
      { to: "/slots", label: "Окна записи", icon: "calendar", roles: ["admin", "specialist", "manager"] },
      { to: "/updates", label: "Обновления", icon: "refresh", roles: ["admin", "specialist", "manager", "client"] },
    ],
  },
  {
    label: "Руководителю",
    items: [{ to: "/reports", label: "Отчёты", icon: "chart", roles: ["admin", "manager"] }],
  },
  {
    label: "Доступ",
    items: [{ to: "/users", label: "Пользователи", icon: "users", roles: ["admin"] }],
  },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  const notes = useAsync(() => api.listNotifications({ limit: 1 }), [pathname]);
  const unread = notes.data?.unread ?? 0;

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  if (!user) return null;
  const role = user.role;

  return (
    <div className="app">
      <a className="skip" href="#content">
        К содержимому
      </a>
      <header className="mobile-bar">
        <button
          type="button"
          className="icon-btn"
          aria-label={open ? "Закрыть меню" : "Открыть меню"}
          aria-expanded={open}
          aria-controls="sidebar"
          onClick={() => setOpen((value) => !value)}
        >
          <svg viewBox="0 0 24 24" className="icon" aria-hidden="true">
            <path d="M4 7h16M4 12h16M4 17h16" />
          </svg>
        </button>
        <span className="mobile-brand">Норд</span>
      </header>
      {open ? (
        <button type="button" className="scrim" aria-label="Закрыть меню" onClick={() => setOpen(false)} />
      ) : null}
      <aside id="sidebar" className={open ? "sidebar is-open" : "sidebar"}>
        <NavLink to="/" className="brand" end>
          <Mark />
          <span>
            <strong>Норд</strong>
            <small>сопровождение 1С</small>
          </span>
        </NavLink>
        <nav className="nav-scroll" aria-label="Разделы">
          {GROUPS.map((group) => {
            const items = group.items.filter((item) => item.roles.includes(role));
            if (items.length === 0) return null;
            return (
              <div key={group.label}>
                <div className="nav-label">{group.label}</div>
                {items.map((item) => (
                  <NavLink key={item.label} to={item.to} end={item.end} className="nav-link">
                    <Icon name={item.icon} />
                    <span>{item.label}</span>
                    {item.to === "/notifications" && unread > 0 ? (
                      <span className="count">{unread > 99 ? "99+" : unread}</span>
                    ) : null}
                  </NavLink>
                ))}
              </div>
            );
          })}
        </nav>
        <div className="user-card">
          <div className="who">
            <div className="avatar" aria-hidden="true">
              {initials(user.full_name)}
            </div>
            <p title={user.full_name}>
              {user.full_name}
              <small>
                {roleLabel(role)}
                {user.client_name ? ` · ${user.client_name}` : ""}
              </small>
            </p>
          </div>
          <button type="button" className="btn btn-light" onClick={logout}>
            Выйти
          </button>
        </div>
      </aside>
      <div className="canvas">
        <div id="content" key={pathname} className="canvas-inner rise">
          {children}
        </div>
      </div>
    </div>
  );
}

export function BootScreen() {
  return (
    <div className="boot">
      <div>
        <Mark size={42} />
        <p>Открываем консоль…</p>
      </div>
    </div>
  );
}
