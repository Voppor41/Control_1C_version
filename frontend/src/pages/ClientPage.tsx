import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAccess } from "../auth/session";
import { formatDateTime } from "../lib/format";
import { useAsync } from "../lib/hooks";
import { useConfirm } from "../ui/confirm";
import { AddInstallation, InstallationCard } from "../ui/installations";
import { useToast } from "../ui/toast";
import { Button, Crumbs, EmptyState, ErrorState, PageHeader, SkeletonList } from "../ui/ui";
import { ClientForm } from "./ClientsPage";

const LIMIT = 20;

export function ClientPage() {
  const { clientId = "" } = useParams();
  const navigate = useNavigate();
  const { canWrite } = useAccess();
  const toast = useToast();
  const confirm = useConfirm();
  const [editing, setEditing] = useState(false);
  const [adding, setAdding] = useState(false);
  const [offset, setOffset] = useState(0);
  const client = useAsync(() => api.getClient(clientId), [clientId]);
  const installations = useAsync(
    () => api.listClientInstallations(clientId, { limit: LIMIT, offset }),
    [clientId, offset],
  );

  async function remove() {
    const ok = await confirm({
      title: "Удалить клиента?",
      body: "Компания исчезнет из реестра, если по ней нет истории обновлений.",
      confirmLabel: "Удалить",
      tone: "danger",
    });
    if (!ok || !client.data) return;
    try {
      await api.deleteClient(client.data.id);
      toast.success("Клиент удалён");
      navigate("/clients");
    } catch (error) {
      toast.error(error);
    }
  }

  if (client.status === "loading" && !client.data) return <SkeletonList rows={4} />;
  if (client.status === "error" && !client.data) {
    return <ErrorState message={client.error?.detail ?? "Клиент не найден"} onRetry={client.reload} />;
  }
  if (!client.data) return null;
  const row = client.data;

  return (
    <>
      <Crumbs items={[{ to: "/clients", label: "Организации" }, { label: row.company_name }]} />
      <PageHeader
        kicker="Клиент"
        title={row.company_name}
        lede={`${row.email} · ${row.phone}`}
        actions={
          canWrite ? (
            <>
              <Button tone="quiet" onClick={() => setEditing(true)}>
                Изменить
              </Button>
              <Button tone="danger" onClick={remove}>
                Удалить
              </Button>
            </>
          ) : null
        }
      />
      <section className="facts">
        <div>
          <span>Ответственный</span>
          <b>{row.responsible_employee_name || "Не назначен"}</b>
        </div>
        <div>
          <span>Телефон</span>
          <b>{row.phone}</b>
        </div>
        <div>
          <span>Почта</span>
          <b>{row.email}</b>
        </div>
        <div>
          <span>Обновлено</span>
          <b>{formatDateTime(row.updated_at)}</b>
        </div>
      </section>
      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>Установки</h2>
            <p className="lede">Конфигурации, которые стоят у клиента, и их версии.</p>
          </div>
          {canWrite ? <Button onClick={() => setAdding(true)}>Добавить базу</Button> : null}
        </div>
        {installations.status === "loading" && !installations.data ? <SkeletonList /> : null}
        {installations.status === "error" && !installations.data ? (
          <ErrorState message={installations.error?.detail ?? "Не удалось загрузить установки"} onRetry={installations.reload} />
        ) : null}
        {installations.data && installations.data.items.length === 0 ? (
          <EmptyState title="Баз ещё нет" text="Добавьте конфигурацию и версию, которая сейчас стоит у клиента." />
        ) : null}
        {installations.data && installations.data.items.length > 0 ? (
          <ul className="entries">
            {installations.data.items.map((item) => (
              <InstallationCard key={item.id} item={item} showClient={false} onChanged={installations.reload} />
            ))}
          </ul>
        ) : null}
        {(installations.data?.total ?? 0) > LIMIT ? (
          <div className="pager">
            <Button tone="quiet" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - LIMIT))}>
              Назад
            </Button>
            <Button
              tone="quiet"
              size="sm"
              disabled={offset + LIMIT >= (installations.data?.total ?? 0)}
              onClick={() => setOffset(offset + LIMIT)}
            >
              Дальше
            </Button>
          </div>
        ) : null}
      </section>
      <p className="meta">
        <Link to="/updates">Перейти к обновлениям</Link>
      </p>
      {editing ? (
        <ClientForm
          client={row}
          onClose={() => setEditing(false)}
          onSaved={() => {
            setEditing(false);
            client.reload();
          }}
        />
      ) : null}
      {adding ? (
        <AddInstallation
          clientId={row.id}
          onClose={() => setAdding(false)}
          onCreated={() => {
            setAdding(false);
            installations.reload();
          }}
        />
      ) : null}
    </>
  );
}
