import { useState } from "react";
import { api } from "../api/client";
import { ApiError } from "../api/errors";
import type { RoleCode, UserRead } from "../api/types";
import { formatDateTime } from "../lib/format";
import { useAsync, useDebounced, useSubmit } from "../lib/hooks";
import { ROLE_ORDER, roleLabel, roleLabelLong } from "../lib/labels";
import { ClientSelect } from "../ui/pickers";
import { useToast } from "../ui/toast";
import {
  Banner,
  Button,
  EmptyState,
  Field,
  LoadBlock,
  Modal,
  PageHeader,
  Pager,
  Segmented,
  Select,
  TextInput,
} from "../ui/ui";

const LIMIT = 20;

type Draft = {
  full_name: string;
  email: string;
  password: string;
  phone: string;
  role: RoleCode;
  client_id: string;
  is_active: boolean;
};

const emptyDraft = (): Draft => ({
  full_name: "",
  email: "",
  password: "",
  phone: "",
  role: "specialist",
  client_id: "",
  is_active: true,
});

export function UsersPage() {
  const toast = useToast();
  const [q, setQ] = useState("");
  const debounced = useDebounced(q);
  const [role, setRole] = useState<RoleCode | "">("");
  const [active, setActive] = useState<"all" | "yes" | "no">("all");
  const [offset, setOffset] = useState(0);
  const [editor, setEditor] = useState<UserRead | "new" | null>(null);
  const filterKey = `${debounced}|${role}|${active}`;
  const [seen, setSeen] = useState(filterKey);
  if (seen !== filterKey) {
    setSeen(filterKey);
    setOffset(0);
  }

  const list = useAsync(
    () =>
      api.listUsers({
        q: debounced || undefined,
        role: role || undefined,
        is_active: active === "all" ? undefined : active === "yes",
        limit: LIMIT,
        offset,
      }),
    [debounced, role, active, offset],
  );

  return (
    <>
      <PageHeader
        kicker="Доступ"
        title="Пользователи"
        lede="Регистрация, роли и включение учёток. Почту после создания изменить нельзя."
        actions={<Button onClick={() => setEditor("new")}>Новый пользователь</Button>}
      />
      <div className="toolbar">
        <Field label="Поиск">
          <TextInput value={q} onChange={(event) => setQ(event.target.value)} placeholder="Имя или почта" />
        </Field>
        <Segmented
          label="Роль"
          value={role || "all"}
          onChange={(value) => setRole(value === "all" ? "" : (value as RoleCode))}
          options={[
            { value: "all", label: "Все роли" },
            ...ROLE_ORDER.map((code) => ({ value: code, label: roleLabel(code) })),
          ]}
        />
        <Segmented
          label="Активность"
          value={active}
          onChange={setActive}
          options={[
            { value: "all", label: "Все" },
            { value: "yes", label: "Активные" },
            { value: "no", label: "Отключённые" },
          ]}
        />
      </div>
      <section className="panel">
        <LoadBlock
          status={list.status}
          error={list.error}
          hasData={Boolean(list.data)}
          onRetry={list.reload}
          isEmpty={list.data?.items.length === 0}
          empty={
            <EmptyState
              title="Никого не нашлось"
              text={q ? "Попробуйте другое имя или почту." : "Зарегистрируйте первого пользователя."}
            />
          }
        >
          <ul className="entries">
            {list.data?.items.map((user) => (
              <li className="entry" key={user.id}>
                <div>
                  <h3>{user.full_name}</h3>
                  <p>
                    {user.email}
                    {user.phone ? ` · ${user.phone}` : ""}
                    {user.client_name ? ` · ${user.client_name}` : ""}
                  </p>
                </div>
                <div className="version-pair">
                  <span className={user.is_active ? "pill ok" : "pill muted"}>
                    {user.is_active ? "Активен" : "Отключён"}
                  </span>
                  <span className="pill info">{roleLabel(user.role)}</span>
                </div>
                <div className="entry-actions">
                  <Button size="sm" tone="quiet" onClick={() => setEditor(user)}>
                    Изменить
                  </Button>
                </div>
              </li>
            ))}
          </ul>
          <Pager total={list.data?.total ?? 0} limit={LIMIT} offset={offset} onOffset={setOffset} />
        </LoadBlock>
      </section>
      {editor ? (
        <UserDialog
          user={editor === "new" ? null : editor}
          onClose={() => setEditor(null)}
          onSaved={() => {
            setEditor(null);
            list.reload();
            toast.success(editor === "new" ? "Пользователь создан" : "Изменения сохранены");
          }}
        />
      ) : null}
    </>
  );
}

function UserDialog({
  user,
  onClose,
  onSaved,
}: {
  user: UserRead | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const submit = useSubmit();
  const roles = useAsync(() => api.listRoles(), []);
  const [form, setForm] = useState<Draft>(() =>
    user
      ? {
          full_name: user.full_name,
          email: user.email,
          password: "",
          phone: user.phone ?? "",
          role: user.role,
          client_id: user.client_id ?? "",
          is_active: user.is_active,
        }
      : emptyDraft(),
  );

  function set<K extends keyof Draft>(key: K, value: Draft[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function validate(): Record<string, string> {
    const errors: Record<string, string> = {};
    if (!form.full_name.trim()) errors.full_name = "Укажите имя";
    if (!user && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) errors.email = "Укажите почту";
    if (!user && form.password.length < 6) errors.password = "Минимум 6 символов";
    if (user && form.password && form.password.length < 6) errors.password = "Минимум 6 символов";
    if (form.role === "client" && !form.client_id) errors.client_id = "Выберите организацию";
    return errors;
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    const errors = validate();
    if (Object.keys(errors).length) {
      submit.setError(new ApiError(0, "Проверьте форму", errors));
      return;
    }
    const ok = await submit.run(async () => {
      if (!user) {
        await api.createUser({
          full_name: form.full_name.trim(),
          email: form.email.trim(),
          password: form.password,
          phone: form.phone.trim() || null,
          role: form.role,
          client_id: form.role === "client" ? form.client_id : null,
        });
        return;
      }
      await api.updateUser(user.id, {
        full_name: form.full_name.trim(),
        phone: form.phone.trim() || null,
        password: form.password ? form.password : undefined,
        is_active: form.is_active,
        role: form.role,
        client_id: form.role === "client" ? form.client_id : null,
      });
    });
    if (ok) onSaved();
  }

  const roleOptions = roles.data?.length
    ? roles.data
    : ROLE_ORDER.map((code) => ({ id: code, code, name: roleLabelLong(code) }));

  return (
    <Modal title={user ? "Учётная запись" : "Новый пользователь"} onClose={onClose} locked={submit.pending}>
      <form className="stack" onSubmit={onSubmit}>
        {submit.error && Object.keys(submit.error.fieldErrors).length === 0 ? <Banner>{submit.error.detail}</Banner> : null}
        <div className="form-grid">
          <Field label="Имя" error={submit.error?.fieldErrors.full_name} className="span-2">
            <TextInput value={form.full_name} maxLength={255} onChange={(event) => set("full_name", event.target.value)} />
          </Field>
          <Field label="Почта" hint={user ? "Почту нельзя изменить" : undefined} error={submit.error?.fieldErrors.email}>
            <TextInput
              type="email"
              value={form.email}
              disabled={Boolean(user)}
              autoComplete="off"
              onChange={(event) => set("email", event.target.value)}
            />
          </Field>
          <Field
            label={user ? "Новый пароль" : "Пароль"}
            hint={user ? "Оставьте пустым, чтобы не менять" : "Минимум 6 символов"}
            error={submit.error?.fieldErrors.password}
          >
            <TextInput
              type="password"
              autoComplete="new-password"
              value={form.password}
              maxLength={128}
              onChange={(event) => set("password", event.target.value)}
            />
          </Field>
          <Field label="Телефон" error={submit.error?.fieldErrors.phone}>
            <TextInput value={form.phone} maxLength={32} onChange={(event) => set("phone", event.target.value)} />
          </Field>
          <Field label="Роль" error={submit.error?.fieldErrors.role}>
            <Select value={form.role} onChange={(event) => set("role", event.target.value as RoleCode)}>
              {roleOptions.map((item) => (
                <option key={item.id} value={item.code}>
                  {item.name}
                </option>
              ))}
            </Select>
          </Field>
          {form.role === "client" ? (
            <div className="span-2">
              <ClientSelect
                value={form.client_id}
                onChange={(id) => set("client_id", id)}
                error={submit.error?.fieldErrors.client_id}
                selectedLabel={user?.client_name ?? undefined}
              />
            </div>
          ) : null}
          {user ? (
            <label className="check span-2">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(event) => set("is_active", event.target.checked)}
              />
              Учётная запись активна
            </label>
          ) : null}
        </div>
        {user ? <p className="field-hint">Создан {formatDateTime(user.created_at)}</p> : null}
        <div className="modal-actions">
          <Button tone="quiet" onClick={onClose} disabled={submit.pending}>
            Отмена
          </Button>
          <Button type="submit" disabled={submit.pending}>
            {submit.pending ? "Сохраняем…" : "Сохранить"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
