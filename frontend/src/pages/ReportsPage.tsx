import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { ApiError } from "../api/errors";
import { formatDate, formatDateTime, plural } from "../lib/format";
import { useAsync, useDebounced } from "../lib/hooks";
import { STATUS_ORDER, statusLabel } from "../lib/labels";
import { Banner, EmptyState, ErrorState, Field, PageHeader, SkeletonList, StatusPill, TextInput } from "../ui/ui";

export function ReportsPage() {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [q, setQ] = useState("");
  const debounced = useDebounced(q);
  const rangeError = Boolean(from && to && from > to);
  const state = useAsync(async () => {
    if (from && to && from > to) {
      throw new ApiError(0, "Дата начала позже даты окончания.", {});
    }
    const query = { date_from: from || undefined, date_to: to || undefined, q: debounced || undefined };
    const [updated, summary, outdated] = await Promise.all([
      api.reportUpdatedClients(query),
      api.reportUpdates(query),
      api.reportOutdated({ q: debounced || undefined }),
    ]);
    return { updated, summary, outdated };
  }, [from, to, debounced]);

  const total =
    (state.data?.summary.planned_count ?? 0) +
    (state.data?.summary.completed_count ?? 0) +
    (state.data?.summary.cancelled_count ?? 0);

  return (
    <>
      <PageHeader
        kicker="Руководителю"
        title="Отчёты"
        lede="Кого уже обновили, что ещё в плане и кто отстал от релиза. Период относится к обновлениям; список отстающих фильтруется только поиском."
      />
      <div className="toolbar">
        <Field label="С">
          <TextInput type="date" value={from} onChange={(event) => setFrom(event.target.value)} />
        </Field>
        <Field label="По">
          <TextInput type="date" value={to} onChange={(event) => setTo(event.target.value)} />
        </Field>
        <Field label="Поиск">
          <TextInput value={q} onChange={(event) => setQ(event.target.value)} placeholder="Организация" />
        </Field>
      </div>
      {rangeError ? <Banner>Дата «с» позже даты «по».</Banner> : null}
      {state.status === "loading" && !state.data ? <SkeletonList rows={4} /> : null}
      {state.status === "error" && !rangeError ? (
        <ErrorState message={state.error?.detail ?? "Не удалось собрать отчёт"} onRetry={state.reload} />
      ) : null}
      {state.data && !rangeError ? (
        <>
          <section className="metrics">
            <div className="metric">
              <span>В плане</span>
              <b>{state.data.summary.planned_count}</b>
              <small>запрошено, назначено, в работе</small>
            </div>
            <div className="metric">
              <span>Выполнено</span>
              <b>{state.data.summary.completed_count}</b>
              <small>{plural(state.data.summary.completed_count, "работа", "работы", "работ")}</small>
            </div>
            <div className="metric">
              <span>Отменено</span>
              <b>{state.data.summary.cancelled_count}</b>
              <small>снято с плана</small>
            </div>
            <div className="metric">
              <span>Отстают</span>
              <b>{state.data.outdated.total_clients}</b>
              <small>
                {state.data.outdated.total_configurations}{" "}
                {plural(state.data.outdated.total_configurations, "база", "базы", "баз")}
              </small>
            </div>
          </section>
          <section className="panel">
            <h2>План и факт</h2>
            {total > 0 ? (
              <div className="bar" aria-hidden="true">
                <span className="bar-planned" style={{ width: `${(state.data.summary.planned_count / total) * 100}%` }} />
                <span className="bar-done" style={{ width: `${(state.data.summary.completed_count / total) * 100}%` }} />
                <span className="bar-cancel" style={{ width: `${(state.data.summary.cancelled_count / total) * 100}%` }} />
              </div>
            ) : null}
            <p className="legend">
              <span><i className="swatch-planned" />В плане</span>
              <span><i className="swatch-done" />Выполнено</span>
              <span><i className="swatch-cancel" />Отменено</span>
            </p>
            <div className="facts dense">
              {STATUS_ORDER.map((status) => (
                <div key={status}>
                  <span>{statusLabel(status)}</span>
                  <b>{state.data?.summary.by_status[status] ?? 0}</b>
                </div>
              ))}
            </div>
            <div className="split">
              <div>
                <h3>В плане</h3>
                {state.data.summary.planned.length === 0 ? <p className="meta">Пусто.</p> : null}
                <ul className="entries">
                  {state.data.summary.planned.map((item) => (
                    <li className="entry" key={item.id}>
                      <div>
                        <h3>
                          <Link to={`/updates/${item.id}`}>{item.company_name}</Link>
                        </h3>
                        <p>
                          {item.configuration_name}
                          {item.slot_date ? ` · ${formatDate(item.slot_date)}` : ""}
                        </p>
                      </div>
                      <StatusPill status={item.status} />
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h3>Выполнено</h3>
                {state.data.summary.completed.length === 0 ? <p className="meta">Пусто.</p> : null}
                <ul className="entries">
                  {state.data.summary.completed.map((item) => (
                    <li className="entry" key={item.id}>
                      <div>
                        <h3>
                          <Link to={`/updates/${item.id}`}>{item.company_name}</Link>
                        </h3>
                        <p>
                          {item.configuration_name}
                          {item.completed_at ? ` · ${formatDateTime(item.completed_at)}` : ""}
                        </p>
                      </div>
                      <StatusPill status={item.status} />
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </section>
          <section className="panel">
            <h2>Кого уже обновили</h2>
            <p className="lede">
              {state.data.updated.total_clients}{" "}
              {plural(state.data.updated.total_clients, "клиент", "клиента", "клиентов")},{" "}
              {state.data.updated.total_updates}{" "}
              {plural(state.data.updated.total_updates, "обновление", "обновления", "обновлений")}.
            </p>
            {state.data.updated.clients.length === 0 ? (
              <EmptyState title="За период пусто" text="Завершённых обновлений с этими фильтрами нет." />
            ) : (
              state.data.updated.clients.map((client) => (
                <article key={client.client_id}>
                  <h3>
                    <Link to={`/clients/${client.client_id}`}>{client.company_name}</Link>
                  </h3>
                  <ul className="entries">
                    {client.updates.map((update) => (
                      <li className="entry" key={update.scheduled_update_id}>
                        <div>
                          <h3>
                            <Link to={`/updates/${update.scheduled_update_id}`}>{update.configuration_name}</Link>
                          </h3>
                          <p>
                            {update.assigned_specialist_name || "Специалист не указан"}
                            {update.completed_at ? ` · ${formatDateTime(update.completed_at)}` : ""}
                          </p>
                        </div>
                        <p className="mono">
                          {update.source_version ?? "—"} → {update.target_version ?? "—"}
                        </p>
                      </li>
                    ))}
                  </ul>
                </article>
              ))
            )}
          </section>
          <section className="panel">
            <h2>Кто отстал от релиза</h2>
            {state.data.outdated.clients.length === 0 ? (
              <EmptyState title="Отстающих нет" text="Все учтённые базы на текущем релизе." />
            ) : (
              state.data.outdated.clients.map((client) => (
                <article key={client.client_id}>
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
                      </li>
                    ))}
                  </ul>
                </article>
              ))
            )}
          </section>
        </>
      ) : null}
    </>
  );
}
