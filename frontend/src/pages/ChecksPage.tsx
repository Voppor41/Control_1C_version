import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { RunChecksResponse } from "../api/types";
import { useAccess } from "../auth/session";
import { translateDetail } from "../api/errors";
import { formatDateTime } from "../lib/format";
import { useAsync, useDebounced, useSubmit } from "../lib/hooks";
import { NotifyDialog } from "../ui/notify";
import { useToast } from "../ui/toast";
import {
  Banner,
  Button,
  EmptyState,
  Field,
  LoadBlock,
  PageHeader,
  Pager,
  Segmented,
  TextInput,
} from "../ui/ui";

const LIMIT = 20;

export function ChecksPage() {
  const { canWrite } = useAccess();
  const toast = useToast();
  const submit = useSubmit();
  const [q, setQ] = useState("");
  const debounced = useDebounced(q);
  const [outdated, setOutdated] = useState<"all" | "yes" | "no">("all");
  const [offset, setOffset] = useState(0);
  const [clientId, setClientId] = useState("");
  const [lastRun, setLastRun] = useState<RunChecksResponse | null>(null);
  const [notice, setNotice] = useState<{ clientId: string; clientName: string; installationId: string } | null>(null);
  const clients = useAsync(() => (canWrite ? api.listClients({ limit: 100 }) : Promise.resolve(null)), [canWrite]);
  const filterKey = `${outdated}|${debounced}`;
  const [seen, setSeen] = useState(filterKey);
  if (seen !== filterKey) {
    setSeen(filterKey);
    setOffset(0);
  }

  const report = useAsync(() => api.outdated({ q: debounced || undefined }), [debounced]);
  const history = useAsync(
    () =>
      api.listChecks({
        is_outdated: outdated === "all" ? undefined : outdated === "yes",
        limit: LIMIT,
        offset,
      }),
    [outdated, offset],
  );

  async function run(target?: string) {
    const ok = await submit.run(async () => {
      const result = await api.runChecks(target ? { client_id: target } : {});
      setLastRun(result);
      toast.success(`Проверено: ${result.created.length}, пропущено: ${result.skipped.length}`);
    });
    if (ok) {
      report.reload();
      history.reload();
    }
  }

  return (
    <>
      <PageHeader
        kicker="Актуальность"
        title="Проверки"
        lede="Сравнение установленной версии с текущим релизом. История сохраняется."
      />
      {canWrite ? (
        <section className="panel">
          <div className="panel-head">
            <h2>Запустить</h2>
          </div>
          {submit.error ? <Banner>{submit.error.detail}</Banner> : null}
          <div className="toolbar">
            <Field label="Клиент">
              <select className="control" value={clientId} onChange={(event) => setClientId(event.target.value)}>
                <option value="">Все клиенты</option>
                {(clients.data?.items ?? []).map((client) => (
                  <option key={client.id} value={client.id}>
                    {client.company_name}
                  </option>
                ))}
              </select>
            </Field>
            <Button onClick={() => run(clientId || undefined)} disabled={submit.pending}>
              {submit.pending ? "Сверяем…" : clientId ? "Проверить клиента" : "Проверить все"}
            </Button>
          </div>
          {lastRun ? (
            <p className="meta">
              Создано записей: {lastRun.created.length}. Пропущено: {lastRun.skipped.length}
              {lastRun.skipped.length
                ? `. ${lastRun.skipped.map((item) => translateDetail(item.reason)).join("; ")}`
                : ""}
            </p>
          ) : null}
        </section>
      ) : (
        <Banner tone="info">Запуск проверки доступен специалисту и администратору. Ниже — уже посчитанный список.</Banner>
      )}

      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>Нужно обновление</h2>
            <p className="lede">
              {report.data
                ? `${report.data.total_clients} клиентов, ${report.data.total_configurations} баз`
                : "Считаем…"}
            </p>
          </div>
        </div>
        <div className="toolbar">
          <Field label="Поиск">
            <TextInput value={q} onChange={(event) => setQ(event.target.value)} placeholder="Клиент или конфигурация" />
          </Field>
        </div>
        {report.status === "loading" && !report.data ? <p className="meta">Загрузка…</p> : null}
        {report.status === "error" ? <Banner>{report.error?.detail ?? "Не удалось загрузить список"}</Banner> : null}
        {report.data && report.data.clients.length === 0 ? (
          <EmptyState title="Отстающих нет" text="Все установки с текущим релизом совпадают." />
        ) : null}
        {report.data?.clients.map((client) => (
          <article key={client.client_id} style={{ marginTop: 12 }}>
            <h3>
              <Link to={`/clients/${client.client_id}`}>{client.company_name}</Link>
            </h3>
            <p className="meta">
              {client.email} · {client.phone}
            </p>
            <ul className="entries">
              {client.configurations.map((row) => (
                <li className="entry" key={row.client_configuration_id}>
                  <div>
                    <h3>{row.configuration_name}</h3>
                    <p>{row.infobase_name || "База не названа"}</p>
                  </div>
                  <p className="mono">
                    {row.installed_version} → {row.current_version}
                  </p>
                  {canWrite ? (
                    <div className="entry-actions">
                      <Button
                        size="sm"
                        onClick={() =>
                          setNotice({
                            clientId: client.client_id,
                            clientName: client.company_name,
                            installationId: row.client_configuration_id,
                          })
                        }
                      >
                        Сообщить
                      </Button>
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          </article>
        ))}
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>История</h2>
        </div>
        <div className="toolbar">
          <Segmented
            label="Результат"
            value={outdated}
            onChange={setOutdated}
            options={[
              { value: "all", label: "Все" },
              { value: "yes", label: "Устарели" },
              { value: "no", label: "Совпали" },
            ]}
          />
        </div>
        <LoadBlock
          status={history.status}
          error={history.error}
          hasData={Boolean(history.data)}
          onRetry={history.reload}
          isEmpty={history.data?.items.length === 0}
          empty={<EmptyState title="Проверок ещё не было" text="Запустите сверку — запись появится здесь." />}
        >
          <ul className="entries">
            {history.data?.items.map((check) => (
              <li className="entry" key={check.id}>
                <div>
                  <h3>
                    <Link to={`/clients/${check.client_id}`}>{check.company_name}</Link>
                  </h3>
                  <p>
                    {check.configuration_name} · {formatDateTime(check.checked_at)} · {check.checked_by_name}
                  </p>
                </div>
                <p className="mono">
                  {check.installed_version} → {check.actual_version}
                </p>
                <span className={check.is_outdated ? "pill bad" : "pill ok"}>
                  {check.is_outdated ? "Устарела" : "Совпала"}
                </span>
              </li>
            ))}
          </ul>
          <Pager total={history.data?.total ?? 0} limit={LIMIT} offset={offset} onOffset={setOffset} />
        </LoadBlock>
      </section>
      {notice ? (
        <NotifyDialog
          clientId={notice.clientId}
          clientName={notice.clientName}
          installationId={notice.installationId}
          onClose={() => setNotice(null)}
        />
      ) : null}
    </>
  );
}
