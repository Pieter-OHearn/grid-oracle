import type { ReactNode } from 'react';

export function Panel({
  title,
  children,
  note,
}: {
  title: string;
  children: ReactNode;
  note?: string;
}) {
  return (
    <section className="go-panel">
      <header className="go-panel-heading">
        <h2>{title}</h2>
        {note && <p className="go-muted">{note}</p>}
      </header>
      {children}
    </section>
  );
}
