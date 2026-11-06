import { Link } from "react-router-dom";
import { EmptyState, PageHeader } from "../ui/ui";

export function NotFoundPage() {
  return (
    <>
      <PageHeader kicker="404" title="Такой страницы нет" lede="Проверьте адрес или вернитесь к обзору." />
      <EmptyState
        title="Ничего не открылось"
        text="Раздел не существует или был переименован."
        action={
          <Link className="btn btn-primary" to="/">
            На обзор
          </Link>
        }
      />
    </>
  );
}
