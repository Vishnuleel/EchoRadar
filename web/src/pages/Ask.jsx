import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { SendHorizontal } from "lucide-react";
import { api } from "../api";
import { useSession } from "../store";
import ItemCard from "../components/ItemCard";
import { HypothesisCard, Notice, PageHeader, SourceLink, Translated } from "../components/ui";

let chatMemory = []; // survives page turns within the session; never stored
const keyOf = (i) => `${i.kind}:${i.ref_id}`;
const TYPE = { park: "about Blue Science Park", help: "help", company: "member", apply: "applying for funding", count: "count",
               opportunities: "opportunities", partners: "partners", search: "subject search", off_topic: "off-topic",
               unknown: "not recognised" };

/** A short answer box built from stored records and fixed sentences: a member, the park, a count, help. */
function AnswerCard({ c }) {
  const { setViewing } = useSession();
  const navigate = useNavigate();
  const open = (l) => { if (l.company_id) setViewing(l.company_id); navigate(l.href); };
  return (
    <article className="border-l-2 border-ink/70 py-1 pl-4">
      {c.kicker && <div className="kicker mb-1">{c.kicker}</div>}
      <h3 className="font-serif text-[22px] font-semibold leading-tight">{c.title}</h3>
      {c.text && <p className="mt-1.5 font-serif text-[16.5px] leading-relaxed text-ink2"><Translated original={c.text} en={c.text_en} /></p>}
      {c.notice && <p className="mt-2 font-sans text-[14px] text-ink2">{c.notice}</p>}
      {c.rows.length > 0 && (
        <dl className="mt-3 grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 font-sans text-[14px]">
          {c.rows.map((r) => (
            <div key={r.label} className="contents">
              <dt className="text-muted">{r.label}</dt>
              <dd className="min-w-0 break-words text-ink">
                {r.url ? <a className="link" href={r.url} target="_blank" rel="noopener noreferrer">{r.value}</a> : r.value}
              </dd>
            </div>
          ))}
        </dl>
      )}
      {c.kind === "compare" && (
        <div className="mt-3 grid gap-5 sm:grid-cols-2">
          {c.columns.map((col) => (
            <div key={col.company_id}>
              <div className="font-serif text-[17px] font-semibold">{col.name}</div>
              {col.capabilities.length ? (
                <ul className="mt-1 space-y-0.5 font-sans text-[14px] text-ink2">
                  {col.capabilities.map((x) => (
                    <li key={x}>{x}{c.shared.includes(x) && <span className="text-muted"> · both</span>}</li>
                  ))}
                </ul>
              ) : <p className="meta mt-1">No capability confirmed from public text.</p>}
            </div>
          ))}
        </div>
      )}
      {c.quotes.length > 0 && (
        <div className="mt-3 space-y-2">
          {c.quotes.map((q) => (
            <blockquote key={q.label + q.url} className="quote !my-0">
              <span className="mr-1 font-sans text-[12.5px] font-semibold not-italic text-ink">{q.label}:</span>
              <Translated original={q.text} en={q.text_en} /> <SourceLink url={q.url} className="not-italic" />
            </blockquote>
          ))}
        </div>
      )}
      {c.note && <p className="meta mt-2">{c.note}</p>}
      {c.links.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {c.links.map((l) => (l.href.startsWith("/")
            ? <button key={l.label} type="button" className="btn" onClick={() => open(l)}>{l.label}</button>
            : <a key={l.label} className="btn" href={l.href} target="_blank" rel="noopener noreferrer">{l.label}</a>))}
        </div>
      )}
    </article>
  );
}

function Answer({ turn, disclaimer, onAsk }) {
  const cat = turn.category;
  const blocked = ["prompt_injection", "privacy_violation"].includes(cat);
  const declined = ["out_of_scope", "needs_clarification", "empty"].includes(cat);
  const cards = turn.cards ?? [];
  const nothing = !blocked && !declined && !(turn.items.length || turn.companies.length || cards.length || turn.hypotheses.length || turn.summary);
  const type = turn.route?.type;
  return (
    <div className="space-y-3">
      <span className="meta">
        Boundary check: {cat.replace(/_/g, " ")}
        {type && !blocked && <> · question type: {TYPE[type] ?? type}</>}
        {turn.route?.source === "gemini" && <> · sorted with Gemini</>}
      </span>
      {(blocked || declined || cat === "escalation") && turn.message && (
        <Notice tone={blocked ? "error" : cat === "escalation" ? "sim" : "info"}>{turn.message}</Notice>
      )}
      {nothing && (
        <Notice tone="info">
          No stored record matches this well enough, and nothing has been made up. Blue Science Park staff may know
          more: <SourceLink url="https://www.bluesciencepark.se/kontakt/">contact</SourceLink>
        </Notice>
      )}
      {!blocked && !declined && cards.map((c, i) => <AnswerCard key={i} c={c} />)}
      {!blocked && !declined && turn.summary && <p className="font-serif text-[15.5px] italic text-ink2">{turn.summary}</p>}
      {!blocked && !declined && turn.items.map((it) => <ItemCard key={keyOf(it)} item={it} compact />)}
      {!blocked && !declined && turn.companies.map((c) => (
        <div key={c.company_id} className="border-b border-line py-3">
          <div className="flex items-baseline justify-between gap-2">
            <span className="font-serif text-[19px] font-semibold">{c.name}</span>
            {c.relevance != null && <span className="meta">fit {c.relevance.toFixed(0)}</span>}
          </div>
          {c.evidence.map((e, i) => (
            <blockquote key={i} className="quote">
              {e.capability_name}: "<Translated original={e.excerpt.slice(0, 200)} en={e.excerpt_en} />"{" "}
              <SourceLink url={e.url} className="not-italic" />
            </blockquote>
          ))}
        </div>
      ))}
      {!blocked && !declined && turn.hypotheses.map((h) => <HypothesisCard key={h.key} h={h} compact />)}
      {(turn.suggestions ?? []).length > 0 && (
        <div>
          <div className="kicker mb-1.5">You could ask</div>
          <ul className="space-y-1">
            {turn.suggestions.map((q) => (
              <li key={q}>
                <button type="button" onClick={() => onAsk(q)}
                        className="text-left font-serif text-[16px] text-ink2 underline decoration-line underline-offset-4 hover:text-ink hover:decoration-ink">
                  {q}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      {turn.route_note && <p className="meta">{turn.route_note}</p>}
      {!blocked && !declined && <p className="meta italic">{disclaimer}</p>}
    </div>
  );
}

/** Ask EchoRadar: questions in, sourced records out. Rule-based: no language model writes the answers. */
export default function Ask({ preview }) {
  const { meta } = useSession();
  const [chat, setChat] = useState(chatMemory);
  const [text, setText] = useState("");
  const end = useRef(null);
  useEffect(() => { chatMemory = chat; }, [chat]);
  const ask = useMutation({
    mutationFn: (question) => {
      const prev = [...chat].reverse().find((t) => ["in_scope", "escalation"].includes(t.category))?.query ?? null;
      return api.ask(question, prev);
    },
    onSuccess: (turn) => setChat((c) => [...c, turn].slice(-12)),
  });
  useEffect(() => { if (chat.length && !preview) end.current?.scrollIntoView({ block: "nearest", behavior: "smooth" }); }, [chat.length, preview]);
  const send = (q) => { const question = (q ?? text).trim(); if (!question || ask.isPending) return; setText(""); ask.mutate(question); };

  return (
    <>
      <PageHeader eyebrow="Inquiries" title="Ask EchoRadar"
                  subtitle="Ask about funding, testing, events, research, a member company or Blue Science Park itself. Answers are put together from stored, sourced records; no language model writes them." />
      <div className="grid gap-10 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <section>
          <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); send(); }}>
            <input className="input" value={text} onChange={(e) => setText(e.target.value)} maxLength={2000}
                   placeholder="For example: which funding calls close in the next 30 days?" aria-label="Your question" />
            <button type="submit" className="btn btn-primary !px-3" disabled={!text.trim() || ask.isPending} aria-label="Send"><SendHorizontal size={16} /></button>
          </form>
          <div className="mt-6 space-y-6">
            {!chat.length && !ask.isPending && (
              <p className="font-serif text-[17px] italic text-ink2">No questions yet this session. Try one of the examples.</p>
            )}
            {chat.map((turn, i) => (
              <div key={i} className="space-y-1.5 border-t border-ink/70 pt-3">
                <p className="font-serif text-[20px] font-semibold leading-snug">{turn.question}</p>
                <Answer turn={turn} disclaimer={meta.disclaimer} onAsk={send} />
              </div>
            ))}
            {ask.isPending && <p className="meta">Checking the question and searching stored records...</p>}
            {ask.isError && <Notice tone="error">{ask.error.message}</Notice>}
            <div ref={end} />
          </div>
          {chat.length > 0 && <button type="button" className="meta mt-4 hover:text-ink hover:underline" onClick={() => setChat([])}>Clear the conversation</button>}
        </section>
        <aside className="lg:border-l lg:border-line lg:pl-8">
          <div className="kicker mb-2">Try asking</div>
          <ul className="space-y-2">
            {meta.examples.map((ex) => (
              <li key={ex}>
                <button type="button" onClick={() => send(ex)}
                        className="text-left font-serif text-[17px] leading-snug text-ink2 underline decoration-line underline-offset-4 hover:text-ink hover:decoration-ink">
                  {ex}
                </button>
              </li>
            ))}
          </ul>
          <div className="kicker mb-2 mt-8">How answers are made</div>
          <p className="font-serif text-[16px] leading-relaxed text-ink2">
            Every question first passes a boundary check: off-topic requests, attempts to override the service and
            requests for private data are declined. EchoRadar then works out what kind of question it is: about the park,
            about a member, about a period, a count, or a subject. The answer is put together from stored records, and
            each one shows its source. {meta.scope}
          </p>
          {meta.llm_routing && (
            <p className="meta mt-3 leading-relaxed">
              Questions from visitors that the rules cannot place are sorted by Google Gemini into the same question types.
              Questions asked as a company are never sent. The answer still comes only from stored records.
            </p>
          )}
        </aside>
      </div>
    </>
  );
}
