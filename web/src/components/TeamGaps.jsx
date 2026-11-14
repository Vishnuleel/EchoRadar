import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { SectionTitle, SourceLink, day } from "./ui";

/** For staff: what the park missed, which roles proposals lack and who in the park has them, and the real gaps. */
export default function TeamGaps() {
  const q = useQuery({ queryKey: ["insights"], queryFn: api.insights });
  const d = q.data;
  if (!d) return null;
  const m = d.missed, t = d.team;
  return (
    <div className="space-y-9">
      <section>
        <SectionTitle hint={`Every Vinnova call that closed in the last 12 months, scored against every member's public profile (fit ${m.min_fit} or more). Not an eligibility check.`}>
          The opportunities the park did not see
        </SectionTitle>
        <p className="max-w-4xl font-serif text-[19px] leading-snug">
          <b>{m.fitted_at_least_one_member} of {m.closed_calls}</b> calls that closed in the last 12 months fitted at least one
          member's public profile. <b>{m.members_with_a_missed_call} of {m.members_checked}</b> members had at least one such call
          {m.of_which_public_authorities > 0 && ` (${m.of_which_public_authorities} of them public authorities, which are not typical applicants)`}.
        </p>
        <div className="mt-3 grid gap-x-8 gap-y-1 font-sans text-[14px] sm:grid-cols-2">
          {m.calls.slice(0, 6).map((c) => (
            <div key={c.url} className="border-b border-line py-2">
              <SourceLink url={c.url}>{c.title}</SourceLink>
              <div className="meta">closed {day(c.closed)} · fitted {c.members.join(", ")}</div>
            </div>
          ))}
        </div>
      </section>

      <section>
        <SectionTitle hint="Each proposal records the roles none of its companies covers. These members, outside the proposal, have public evidence of the role. None has been contacted.">
          Complete the team: {t.proposals_missing_a_role} of {t.proposals} proposals lack a role that another member has
        </SectionTitle>
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>Missing role</th><th className="text-right">Proposals</th><th>Members with public evidence of it</th><th>For example</th></tr></thead>
            <tbody>
              {t.roles.slice(0, 10).map((r) => (
                <tr key={r.role}>
                  <td className="whitespace-nowrap font-medium text-ink">{r.role}</td>
                  <td className="text-right tabular-nums">{r.proposals}</td>
                  <td>{r.providers.length ? r.providers.join(", ") : <span className="font-semibold text-hyp">no member</span>}</td>
                  <td className="text-[13px]">{r.examples[0]?.title}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <SectionTitle hint="Capabilities in EchoRadar's vocabulary that no member describes in public sources.">Real gaps in the ecosystem</SectionTitle>
        {t.real_gaps.length ? (
          <ul className="space-y-1.5 font-sans text-[14px] text-ink2">
            {t.real_gaps.map((g) => (
              <li key={g.key}><b className="text-ink">{g.name}</b>: no member shows it publicly; {g.research} research records and {g.open_calls} open
                calls touch it. A topic for recruiting a member or a partner outside the park.</li>
            ))}
          </ul>
        ) : <p className="meta">Every capability in the vocabulary is offered by at least one member.</p>}
        {t.roles_without_any_provider.length === 0 && (
          <p className="meta mt-2">Every role that a proposal lacks is covered by at least one member, so the gaps above are gaps of the
            proposals, not of the park.</p>
        )}
      </section>
    </div>
  );
}
