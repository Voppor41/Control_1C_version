import { Link } from "react-router-dom";
import { api } from "../api/client";
import type {
  ClientConfigurationRead,
  NotificationList,
  OutdatedReport,
  Page,
  ScheduledUpdateRead,
  UpdatesReport,
  UpdatedClientsReport,
} from "../api/types";
import { useAuth } from "../auth/session";
import { firstName, formatSlot, formatToday, greeting, plural } from "../lib/format";
import { useAsync } from "../lib/hooks";
import { EmptyState, ErrorState, PageHeader, SkeletonList, StatusPill, VersionPair } from "../ui/ui";

type HomeData =
  | {
      kind: "staff";
      clientsTotal: number;
      configTotal: number;
      outdated: Page<ClientConfigurationRead>;
      notes: NotificationList;
      updates: Page<ScheduledUpdateRead>;
    }
  | {
      kind: "manager";
      summary: UpdatesReport;
      outdated: OutdatedReport;
      updated: UpdatedClientsReport;
    }
  | {
      kind: "client";
      installations: Page<ClientConfigurationRead>;
      notes: NotificationList;
      updates: Page<ScheduledUpdateRead>;
    };

export function HomePage() {
  const { user } = useAuth();
  const role = user?.role;
  const state = useAsync(async (): Promise<HomeData> => {
    if (role === "manager") {
      const [summary, outdated, updated] = await Promise.all([
        api.reportUpdates(),
        api.reportOutdated(),
        api.reportUpdatedClients(),
      ]);
      return { kind: "manager", summary, outdated, updated };
    }
    if (role === "client") {
      const [installations, notes, updates] = await Promise.all([
        api.listInstallations({ limit: 12 }),
        api.listNotifications({ limit: 4 }),
        api.listUpdates({ limit: 4 }),
      ]);
      return { kind: "client", installations, notes, updates };
    }
    const [clients, configurations, outdated, notes, updates] = await Promise.all([
      api.listClients({ limit: 1 }),
      api.listConfigurations({ limit: 1 }),
      api.listInstallations({ outdated: true, limit: 6 }),
      api.listNotifications({ limit: 1 }),
      api.listUpdates({ limit: 6 }),
    ]);
    return {
      kind: "staff",
      clientsTotal: clients.total,
      configTotal: configurations.total,
      outdated,
      notes,
      updates,
    };
  }, [role]);

  const name = user ? firstName(user.full_name) : "";
  const lede =
    role === "client"
      ? "Ваши базы, уведомления и запись на обновление."
      : role === "manager"
        ? "Сводка: кого уже обновили, что в плане и кто отстал от релиза."
        : role === "admin"
          ? "Реестр клиентов, релизы и очередь работ."
          : "Проверьте актуальность, сообщите клиенту и назначьте окно.";

  return (
    <>
      <PageHeader kicker={formatToday()} title={`${greeting()}, ${name}`} lede={lede} />
      {state.status === "loading" && !state.data ? <SkeletonList rows={4} /> : null}
      {state.status === "error" && !state.data ? (
        <ErrorState message={state.error?.detail ?? "Не удалось собрать обзор"} onRetry={state.reload} />
      ) : null}
      {state.data?.kind === "staff" ? <StaffHome data={state.data} /> : null}
      {state.data?.kind === "manager" ? <ManagerHome data={state.data} /> : null}
      {state.data?.kind === "client" ? <ClientHome data={state.data} company={user?.client_name} /> : null}
    </>
  );
}

function StaffHome({ data }: { data: Extract<HomeData, { kind: "staff" }> }) {
  return (
    <>
      <section className="metrics">
        <Link className="metric" to="/clients">
          <span>Клиенты</span>
          <b>{data.clientsTotal}</b>
          <small>в реестре</small>
        </Link>
        <Link className="metric" to="/installations?outdated=1">
          <span>Ждут релиза</span>
          <b>{data.outdated.total}</b>
          <small>{plural(data.outdated.total, "установка", "установки", "установок")}</small>
        </Link>
        <Link className="metric" to="/notifications">
          <span>Непрочитанные</span>
          <b>{data.notes.unread}</b>
          <small>уведомления</small>
        </Link>
        <Link className="metric" to="/configurations">
          <span>Конфигурации</span>
          <b>{data.configTotal}</b>
          <small>в каталоге</small>
        </Link>
      </section>
      <div className="split">
        <section className="panel">
          <div className="panel-head">
            <h2>Отстают от релиза</h2>
            <Link to="/checks">Все проверки</Link>
          </div>
          {data.outdated.items.length === 0 ? (
            <EmptyState title="Всё актуально" text="Среди установок нет баз старше текущего релиза." />
          ) : (
            <ul className="entries">
              {data.outdated.items.map((item) => (
                <li className="entry" key={item.id}>
                  <div>
                    <h3>
                      <Link to={`/clients/${item.client_id}`}>{item.company_name}</Link>
                    </h3>
                    <p>
                      {item.configuration_name}
                      {item.infobase_name ? ` · ${item.infobase_name}` : ""}
                    </p>
                  </div>
                  <VersionPair
                    installed={item.installed_version}
                    current={item.current_version}
                    outdated={item.is_outdated}
                  />
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="panel">
          <div className="panel-head">
            <h2>Последние обновления</h2>
            <Link to="/updates">Очередь</Link>
          </div>
          {data.updates.items.length === 0 ? (
            <EmptyState title="Очередь пуста" text="Запросов и назначенных работ пока нет." />
          ) : (
            <ul className="entries">
              {data.updates.items.map((item) => (
                <UpdateRow key={item.id} item={item} />
              ))}
            </ul>
          )}
        </section>
      </div>
    </>
  );
}

function ManagerHome({ data }: { data: Extract<HomeData, { kind: "manager" }> }) {
  return (
    <>
      <section className="metrics">
        <Link className="metric" to="/reports">
          <span>В плане</span>
          <b>{data.summary.planned_count}</b>
          <small>запрошено, назначено, в работе</small>
        </Link>
        <Link className="metric" to="/reports">
          <span>Выполнено</span>
          <b>{data.summary.completed_count}</b>
          <small>{plural(data.updated.total_updates, "обновление", "обновления", "обновлений")} в истории</small>
        </Link>
        <Link className="metric" to="/reports">
          <span>Отстают</span>
          <b>{data.outdated.total_clients}</b>
          <small>
            {data.outdated.total_configurations}{" "}
            {plural(data.outdated.total_configurations, "база", "базы", "баз")}
          </small>
        </Link>
        <Link className="metric" to="/reports">
          <span>Отменено</span>
          <b>{data.summary.cancelled_count}</b>
          <small>не дошли до релиза</small>
        </Link>
      </section>
      <div className="split">
        <section className="panel">
          <div className="panel-head">
            <h2>Кто в плане</h2>
            <Link to="/reports">Отчёт</Link>
          </div>
          {data.summary.planned.length === 0 ? (
            <EmptyState title="План пуст" text="Нет запрошенных, назначенных или идущих обновлений." />
          ) : (
            <ul className="entries">
              {data.summary.planned.slice(0, 6).map((item) => (
                <li className="entry" key={item.id}>
                  <div>
                    <h3>
                      <Link to={`/updates/${item.id}`}>{item.company_name}</Link>
                    </h3>
                    <p>
                      {item.configuration_name}
                      {item.slot_date ? ` · ${formatSlot(item.slot_date, null, null)}` : ""}
                    </p>
                  </div>
                  <StatusPill status={item.status} />
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="panel">
          <div className="panel-head">
            <h2>Нужен релиз</h2>
          </div>
          {data.outdated.clients.length === 0 ? (
            <EmptyState title="Отстающих нет" text="Все учтённые базы на текущем релизе." />
          ) : (
            <ul className="entries">
              {data.outdated.clients.slice(0, 6).map((client) => (
                <li className="entry" key={client.client_id}>
                  <div>
                    <h3>
                      <Link to={`/clients/${client.client_id}`}>{client.company_name}</Link>
                    </h3>
                    <p>
                      {client.configurations.map((row) => `${row.configuration_name} ${row.installed_version}`).join(", ")}
                    </p>
                  </div>
                  <span className="pill bad">{client.configurations.length}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </>
  );
}

function ClientHome({
  data,
  company,
}: {
  data: Extract<HomeData, { kind: "client" }>;
  company?: string | null;
}) {
  const outdated = data.installations.items.filter((item) => item.is_outdated);
  return (
    <>
      {outdated.length > 0 ? (
        <div className="callout">
          <div>
            <h2>Есть что обновить</h2>
            <p className="lede">
              {company ? `${company}: ` : ""}
              {outdated.length} {plural(outdated.length, "база отстала", "базы отстали", "баз отстали")} от текущего релиза.
            </p>
          </div>
          <Link className="btn btn-primary" to={`/updates?installation=${outdated[0]?.id ?? ""}`}>
            Выбрать дату
          </Link>
        </div>
      ) : (
        <div className="callout calm">
          <div>
            <h2>Релизы на месте</h2>
            <p className="lede">Среди ваших баз нет устаревших установок.</p>
          </div>
        </div>
      )}
      <div className="split">
        <section className="panel">
          <div className="panel-head">
            <h2>Базы</h2>
            <Link to="/installations">Все</Link>
          </div>
          {data.installations.items.length === 0 ? (
            <EmptyState
              title="Баз пока нет"
              text="Когда специалист зарегистрирует установку, она появится здесь."
            />
          ) : (
            <ul className="entries">
              {data.installations.items.map((item) => (
                <li className="entry" key={item.id}>
                  <div>
                    <h3>{item.configuration_name}</h3>
                    <p>{item.infobase_name || "Информационная база не указана"}</p>
                  </div>
                  <VersionPair
                    installed={item.installed_version}
                    current={item.current_version}
                    outdated={item.is_outdated}
                  />
                </li>
              ))}
            </ul>
          )}
        </section>
        <div>
          <section className="panel">
            <div className="panel-head">
              <h2>Уведомления</h2>
              <Link to="/notifications">{data.notes.unread ? `${data.notes.unread} новых` : "Все"}</Link>
            </div>
            {data.notes.items.length === 0 ? (
              <p className="meta">Новых писем от сопровождения нет.</p>
            ) : (
              <ul className="entries">
                {data.notes.items.map((note) => (
                  <li className="entry" key={note.id}>
                    <div>
                      <h3>{note.title}</h3>
                      <p>{note.is_read ? "Прочитано" : "Не прочитано"}</p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section className="panel">
            <div className="panel-head">
              <h2>Обновления</h2>
              <Link to="/updates">Запись</Link>
            </div>
            {data.updates.items.length === 0 ? (
              <p className="meta">Вы ещё не записывались на обновление.</p>
            ) : (
              <ul className="entries">
                {data.updates.items.map((item) => (
                  <UpdateRow key={item.id} item={item} />
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </>
  );
}

function UpdateRow({ item }: { item: ScheduledUpdateRead }) {
  return (
    <li className="entry">
      <div>
        <h3>
          <Link to={`/updates/${item.id}`}>{item.configuration_name}</Link>
        </h3>
        <p>
          {item.company_name} · {formatSlot(item.slot_date, item.slot_start, item.slot_end)}
        </p>
      </div>
      <StatusPill status={item.status} />
    </li>
  );
}
