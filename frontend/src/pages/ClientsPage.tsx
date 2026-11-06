import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { ApiError } from "../api/errors";
import { useAccess } from "../auth/session";
import { useAsync, useDebounced, useSubmit } from "../lib/hooks";
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
  Select,
  TextInput,
} from "../ui/ui";

const LIMIT = 20;

export function ClientsPage() {
  const { canWrite, isClient } = useAccess();
  const [q, setQ] = useState("");
  const debounced = useDebounced(q);
  const [offset, setOffset] = useState(0);
  const [creating, setCreating] = useState(false);
  const filterKey = debounced;
  const [seen, setSeen] = useState(filterKey);
  if (seen !== filterKey) {
    setSeen(filterKey);
    setOffset(0);
  }
  const list = useAsync(
    () => api.listClients({ q: debounced || undefined, limit: LIMIT, offset }),
    [debounced, offset],
  );

  return (
    <>
      <PageHeader
        kicker="Клиенты"
        title={isClient ? "Моя организация" : "Организации"}
        lede={
          isClient
            ? "Карточка компании, к которой привязана ваша учётная запись."
            : "Реестр компаний, их почта и ответственный специалист."
        }
        actions={canWrite ? <Button onClick={() => setCreating(true)}>Новый клиент</Button> : null}
      />
      {isClient ? null : (
        <div className="toolbar">
          <Field label="Поиск">
            <TextInput
              value={q}
              onChange={(event) => setQ(event.target.value)}
              placeholder="Название, почта или телефон"
            />
          </Field>
        </div>
      )}
      <section className="panel">
        <LoadBlock
          status={list.status}
          error={list.error}
          hasData={Boolean(list.data)}
          onRetry={list.reload}
          isEmpty={list.data?.items.length === 0}
          empty={
            <EmptyState
              title={q ? "Никого не нашлось" : "Клиентов пока нет"}
              text={
                isClient
                  ? "Учётная запись не привязана к организации. Обратитесь к администратору."
                  : "Зарегистрируйте компанию, затем создайте для неё пользователя с ролью «Клиент»."
              }
            />
          }
        >
          <ul className="entries">
            {list.data?.items.map((client) => (
              <li className="entry" key={client.id}>
                <div>
                  <h3>
                    <Link to={`/clients/${client.id}`}>{client.company_name}</Link>
                  </h3>
                  <p>
                    {client.email} · {client.phone}
                  </p>
                </div>
                <p className="meta">{client.responsible_employee_name || "Ответственный не назначен"}</p>
                <div className="entry-actions">
                  <Link className="btn btn-quiet btn-sm" to={`/clients/${client.id}`}>
                    Карточка
                  </Link>
                </div>
              </li>
            ))}
          </ul>
          <Pager total={list.data?.total ?? 0} limit={LIMIT} offset={offset} onOffset={setOffset} />
        </LoadBlock>
      </section>
      {creating ? (
        <ClientForm
          onClose={() => setCreating(false)}
          onSaved={() => {
            setCreating(false);
            list.reload();
          }}
        />
      ) : null}
    </>
  );
}

export function ClientForm({
  client,
  onClose,
  onSaved,
}: {
  client?: {
    id: string;
    company_name: string;
    phone: string;
    email: string;
    responsible_employee_id: string | null;
    responsible_employee_name: string | null;
  };
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const submit = useSubmit();
  const staff = useAsync(() => api.listUsers({ is_active: true, limit: 200 }), []);
  const [company, setCompany] = useState(client?.company_name ?? "");
  const [phone, setPhone] = useState(client?.phone ?? "");
  const [email, setEmail] = useState(client?.email ?? "");
  const [responsible, setResponsible] = useState(client?.responsible_employee_id ?? "");

  const people = (staff.data?.items ?? []).filter((user) => user.role !== "client");
  const known = new Map<string, string>(people.map((user) => [user.id, user.full_name]));
  if (client?.responsible_employee_id && client.responsible_employee_name && !known.has(client.responsible_employee_id)) {
    known.set(client.responsible_employee_id, client.responsible_employee_name);
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    const errors: Record<string, string> = {};
    if (!company.trim()) errors.company_name = "Укажите название";
    if (!phone.trim()) errors.phone = "Укажите телефон";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) errors.email = "Укажите почту";
    if (Object.keys(errors).length) {
      submit.setError(new ApiError(0, "Проверьте форму", errors));
      return;
    }
    const ok = await submit.run(async () => {
      const payload = {
        company_name: company.trim(),
        phone: phone.trim(),
        email: email.trim(),
        responsible_employee_id: responsible || null,
      };
      if (client) await api.updateClient(client.id, payload);
      else await api.createClient(payload);
    });
    if (ok) {
      toast.success(client ? "Карточка сохранена" : "Клиент зарегистрирован");
      onSaved();
    }
  }

  return (
    <Modal title={client ? "Карточка клиента" : "Новый клиент"} onClose={onClose} locked={submit.pending}>
      <form className="stack" onSubmit={onSubmit}>
        {submit.error && Object.keys(submit.error.fieldErrors).length === 0 ? <Banner>{submit.error.detail}</Banner> : null}
        <Field label="Организация" error={submit.error?.fieldErrors.company_name}>
          <TextInput value={company} maxLength={255} onChange={(event) => setCompany(event.target.value)} />
        </Field>
        <div className="form-grid">
          <Field label="Телефон" error={submit.error?.fieldErrors.phone}>
            <TextInput value={phone} maxLength={32} onChange={(event) => setPhone(event.target.value)} />
          </Field>
          <Field label="Почта" error={submit.error?.fieldErrors.email}>
            <TextInput type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
          </Field>
        </div>
        <Field
          label="Ответственный"
          hint="Активный сотрудник, не клиент."
          error={submit.error?.fieldErrors.responsible_employee_id}
        >
          <Select value={responsible} onChange={(event) => setResponsible(event.target.value)}>
            <option value="">Не назначен</option>
            {[...known.entries()].map(([id, name]) => (
              <option key={id} value={id}>
                {name}
              </option>
            ))}
          </Select>
        </Field>
        {staff.status === "error" ? <Banner>{staff.error?.detail ?? "Не удалось загрузить сотрудников"}</Banner> : null}
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
