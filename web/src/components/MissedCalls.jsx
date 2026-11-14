import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { SourceLink, Translated, day } from "./ui";

/** "The opportunity you never saw": calls that fitted this member and closed in the last 12 months. */
export default function MissedCalls({ companyId, name }) {
  const q = useQuery({ queryKey: ["missed", companyId], queryFn: () => api.missed(companyId), enabled: companyId != null });
  const d = q.data;
  if (!d) return null;
  return (
    <section className="mt-10 border-t-[3px] border-double border-ink pt-4">
      <div className="kicker">The opportunity you never saw</div>
      <h2 className="mt-1 font-serif text-[26px] font-semibold leading-tight">
        {d.items.length
          ? `${d.items.length} funding call${d.items.length === 1 ? "" : "s"} fitted ${name} and closed in the last 12 months`
          : `No closed call fitted ${name} closely in the last 12 months`}
      </h2>
      <p className="meta mt-1 max-w-3xl leading-relaxed">
        All {d.closed_calls_checked} Vinnova calls that closed in the last 12 months, scored against {name}'s public profile
        as it is today, with the same matching as the radar. Only fits of {d.min_fit} or more are shown; below that, unrelated
        calls start to appear. A fit is not an eligibility check, and the profile at the time may have been different.
      </p>
      {d.items.length > 0 && (
        <ol className="mt-4 space-y-4">
          {d.items.map((c) => (
            <li key={c.ref_id} className="grid grid-cols-[1fr_auto] gap-4 border-b border-line pb-3">
              <div>
                <h3 className="font-serif text-[19px] font-semibold leading-snug"><Translated original={c.title} en={c.title_en} /></h3>
                <p className="mt-1 font-sans text-[14px] text-ink2">
                  Open {c.opened ? day(c.opened) : "date not published"} to {day(c.closed)}
                  {c.open_days != null && <span className="text-muted"> ({c.open_days} days)</span>}. {c.why}
                </p>
                <p className="mt-1 font-sans text-[14px]">
                  {c.next_round
                    ? <><span className="font-semibold text-sea">A new round is {c.next_round.status}:</span> <SourceLink url={c.next_round.url}>{c.next_round.title}</SourceLink>{c.next_round.deadline && ` (deadline ${day(c.next_round.deadline)})`}</>
                    : <span className="text-ink2">No new round is open yet. The radar will show it when one appears.</span>}
                </p>
                <p className="meta mt-0.5"><SourceLink url={c.url}>Vinnova call record</SourceLink></p>
              </div>
              <div className="text-right">
                <div className="font-serif text-[24px] font-semibold tabular-nums leading-none">{Math.round(c.relevance)}</div>
                <div className="meta">fit</div>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
