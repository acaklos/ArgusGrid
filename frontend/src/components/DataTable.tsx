import { ReactNode, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { TableWrap } from "./TableWrap";

// One table with pagination (page sizes 10, 20, 50, 100). Locked and disabled rows are styled in one place.
export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
}

export const PAGE_SIZES = [10, 20, 50, 100] as const;

/** Server-side paging: the caller owns page, size and total (used when data is large or filtered on the server). */
export interface ServerPaging {
  page: number;
  pageSize: number;
  total: number;
  onChange: (page: number, pageSize: number) => void;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
  emptyText?: string;
  paging?: ServerPaging;
  rowClassName?: (row: T) => string | undefined;
}

export function DataTable<T>({ columns, rows, rowKey, emptyText, paging, rowClassName }: DataTableProps<T>) {
  const { t } = useTranslation();
  const [localSize, setLocalSize] = useState<number>(PAGE_SIZES[0]);
  const [localPage, setLocalPage] = useState(0);

  const pageSize = paging ? paging.pageSize : localSize;
  const total = paging ? paging.total : rows.length;
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const current = paging ? Math.min(paging.page - 1, pages - 1) : Math.min(localPage, pages - 1);

  const visible = useMemo(
    () => (paging ? rows : rows.slice(current * pageSize, (current + 1) * pageSize)),
    [paging, rows, current, pageSize],
  );

  const go = (page: number, size = pageSize) => {
    if (paging) paging.onChange(page + 1, size);
    else {
      setLocalPage(page);
      setLocalSize(size);
    }
  };

  return (
    <div>
      <TableWrap>
        <table className="table table--cards">
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c.key} scope="col">
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.length === 0 && (
              <tr>
                <td colSpan={columns.length}>{emptyText ?? t("common.empty")}</td>
              </tr>
            )}
            {visible.map((row) => (
              <tr key={rowKey(row)} className={rowClassName?.(row)}>
                {columns.map((c) => (
                  <td key={c.key} data-label={c.header}>
                    {c.render(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </TableWrap>
      <div className="table__pager">
        <span className="field__help">{t("table.total", { count: total })}</span>
        <label>
          <span className="sr-only">{t("table.page_size")}</span>
          <select className="select" value={pageSize} onChange={(e) => go(0, Number(e.target.value))}>
            {PAGE_SIZES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="btn btn--small" disabled={current === 0} onClick={() => go(current - 1)}>
          {t("table.previous")}
        </button>
        <span>{t("table.page_of", { page: current + 1, pages })}</span>
        <button type="button" className="btn btn--small" disabled={current >= pages - 1} onClick={() => go(current + 1)}>
          {t("table.next")}
        </button>
      </div>
    </div>
  );
}
