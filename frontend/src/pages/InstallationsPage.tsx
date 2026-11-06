import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { useAccess } from "../auth/session";
import { useAsync, useDebounced } from "../lib/hooks";
import { InstallationCard } from "../ui/installations";
import { EmptyState, Field, LoadBlock, PageHeader, Pager, Segmented, TextInput } from "../ui/ui";

const LIMIT = 20;

export function InstallationsPage() {
  const { isClient } = useAccess();
  const [params] = useSearchParams();
  const [q, setQ] = useState("");
  const debounced = useDebounced(q);
  const [outdated, setOutdated] = useState<"all" | "yes" | "no">(params.get("outdated") === "1" ? "yes" : "all");
  useEffect(() => {
    if (params.get("outdated") === "1") setOutdated("yes");
  }, [params]);
  const [offset, setOffset] = useState(0);
  const filterKey = `${debounced}|${outdated}`;
  const [seen, setSeen] = useState(filterKey);
  if (seen !== filterKey) {
    setSeen(filterKey);
    setOffset(0);
  }
  const list = useAsync(
    () =>
      api.listInstallations({
        q: debounced || undefined,
        outdated: outdated === "all" ? undefined : outdated === "yes",
        limit: LIMIT,
        offset,
      }),
    [debounced, outdated, offset],
  );

  return (
    <>
      <PageHeader
        kicker="Базы"
        title={isClient ? "Мои базы" : "Установки"}
        lede="Установленная версия рядом с текущим релизом. Отсюда же можно проверить базу и написать клиенту."
      />
      <div className="toolbar">
        <Field label="Поиск">
          <TextInput
            value={q}
            onChange={(event) => setQ(event.target.value)}
            placeholder={isClient ? "Конфигурация или база" : "Клиент, конфигурация или база"}
          />
        </Field>
        <Segmented
          label="Актуальность"
          value={outdated}
          onChange={setOutdated}
          options={[
            { value: "all", label: "Все" },
            { value: "yes", label: "Устарели" },
            { value: "no", label: "Актуальны" },
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
              title={q || outdated !== "all" ? "Ничего не нашлось" : "Установок нет"}
              text="База появляется, когда специалист привязывает конфигурацию к клиенту."
            />
          }
        >
          <ul className="entries">
            {list.data?.items.map((item) => (
              <InstallationCard key={item.id} item={item} onChanged={list.reload} />
            ))}
          </ul>
          <Pager total={list.data?.total ?? 0} limit={LIMIT} offset={offset} onOffset={setOffset} />
        </LoadBlock>
      </section>
    </>
  );
}
