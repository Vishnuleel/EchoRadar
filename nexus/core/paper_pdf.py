"""The paper as a PDF: one company's edition, laid out like a newspaper (masthead, lead, two columns).

build() takes the same display data the website shows (already filtered for the audience and with English
display translations attached) and returns the PDF bytes. Every finding keeps its source link, its date
line and its uncertainty; proposals are labelled as hypotheses. Nothing is added that the site does not show.
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape as esc

NAME = "EchoRadar"
AREAS = [("funding", "Funding"), ("testbed", "Testing opportunities"), ("event", "Events"), ("research", "Research"),
         ("news", "Regional news")]


def _en(item: dict, field: str) -> str:
    """The English display text when a stored translation exists, otherwise the original."""
    tr = item.get(f"{field}_en")
    return (tr.get("text") if isinstance(tr, dict) and tr.get("available") else None) or item.get(field) or ""


def build(paper: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (BaseDocTemplate, Frame, FrameBreak, HRFlowable, KeepTogether, NextPageTemplate, PageTemplate,
                                    Paragraph, Spacer)

    ink, soft, sea, hyp = colors.HexColor("#101F37"), colors.HexColor("#3A475C"), colors.HexColor("#267365"), colors.HexColor("#A4482D")
    serif, serif_b, serif_i, sans, sans_b = "Times-Roman", "Times-Bold", "Times-Italic", "Helvetica", "Helvetica-Bold"
    st = {
        "mast": ParagraphStyle("mast", fontName=serif_b, fontSize=40, leading=44, alignment=1, textColor=ink),
        "strap": ParagraphStyle("strap", fontName=sans, fontSize=8, leading=11, textColor=soft, alignment=1),
        "kicker": ParagraphStyle("kicker", fontName=sans_b, fontSize=7, leading=10, textColor=soft, spaceBefore=6),
        "lead": ParagraphStyle("lead", fontName=serif_b, fontSize=21, leading=24, textColor=ink, spaceAfter=3),
        "h2": ParagraphStyle("h2", fontName=serif_b, fontSize=14, leading=16, textColor=ink, spaceBefore=8, spaceAfter=2),
        "h3": ParagraphStyle("h3", fontName=serif_b, fontSize=11, leading=13, textColor=ink, spaceBefore=6),
        "body": ParagraphStyle("body", fontName=serif, fontSize=9.5, leading=12.5, textColor=ink),
        "why": ParagraphStyle("why", fontName=serif_i, fontSize=9.5, leading=12.5, textColor=soft),
        "meta": ParagraphStyle("meta", fontName=sans, fontSize=7.5, leading=10, textColor=soft),
        "note": ParagraphStyle("note", fontName=sans, fontSize=7.5, leading=10, textColor=hyp),
    }
    W, H = A4
    margin, gutter, head = 16 * mm, 6 * mm, 33 * mm
    col = (W - 2 * margin - gutter) / 2
    company = paper["company"]["name"]
    when = paper["generated_at"]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(sans, 7)
        canvas.setFillColor(soft)
        canvas.drawString(margin, 9 * mm, f"{NAME} · {company} edition · {when:%Y-%m-%d %H:%M} UTC · {paper['audience_note']}")
        canvas.drawRightString(W - margin, 9 * mm, f"Page {doc.page}")
        canvas.setStrokeColor(ink)
        canvas.setLineWidth(0.6)
        canvas.line(margin, 12 * mm, W - margin, 12 * mm)
        canvas.restoreState()

    first = [Frame(margin, H - margin - head, W - 2 * margin, head, id="mast", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
             Frame(margin, 15 * mm, col, H - margin - head - 17 * mm, id="a", leftPadding=0, rightPadding=0, topPadding=4, bottomPadding=0),
             Frame(margin + col + gutter, 15 * mm, col, H - margin - head - 17 * mm, id="b", leftPadding=0, rightPadding=0, topPadding=4, bottomPadding=0)]
    later = [Frame(margin, 15 * mm, col, H - margin - 17 * mm, id="c", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
             Frame(margin + col + gutter, 15 * mm, col, H - margin - 17 * mm, id="d", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)]
    buf = BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4, title=f"{NAME} - {company}", author=NAME,
                          leftMargin=margin, rightMargin=margin, topMargin=margin, bottomMargin=15 * mm)
    doc.addPageTemplates([PageTemplate(id="first", frames=first, onPage=footer),
                          PageTemplate(id="later", frames=later, onPage=footer)])

    def link(url, text):
        return f'<link href="{esc(url)}" color="#152B4E"><u>{esc(text)}</u></link>' if url else esc(text)

    def rule(width=0.6, space=3):
        return HRFlowable(width="100%", thickness=width, color=ink, spaceBefore=space, spaceAfter=space)

    def finding(it: dict, lead: bool = False) -> list:
        fit = f" · fit {it['relevance']:.0f}" if it.get("relevance") is not None else ""
        out = [Paragraph(esc(_en(it, "title"))[:240], st["lead" if lead else "h3"])]
        if it.get("why"):
            out.append(Paragraph(esc(it["why"]), st["why"]))
        if lead and it.get("excerpt"):
            out.append(Paragraph(esc(_en(it, "excerpt"))[:520], st["body"]))
        flags = "".join(f" · {esc(f)}" for f in it.get("flags") or [])
        out.append(Paragraph(f"{esc(it.get('source') or '')} · {esc(it.get('date_label') or '')}{fit}{flags} · "
                             + link(it.get("url"), "source")
                             + (" · " + link(it["apply_url"], "application page") if it.get("apply_url") else ""), st["meta"]))
        for label, value in (it.get("terms") or []):
            if label in ("Organised by", "Speaker (as published)", "Sponsors", "In collaboration with (as published)"):
                out.append(Paragraph(f"<b>{esc(label)}:</b> {esc(str(value))[:200]}", st["meta"]))
        if it.get("next_action"):
            out.append(Paragraph(f"<b>Next step:</b> {esc(it['next_action'])}", st["body"]))
        if it.get("uncertainty"):
            out.append(Paragraph(f"Uncertain: {esc(it['uncertainty'])}", st["meta"]))
        return out

    story = [Paragraph(f"{when:%A, %d %B %Y} · Blue Science Park · Karlskrona", st["strap"]), rule(0.6, 2),
             Paragraph(NAME, st["mast"]), rule(1.6, 2),
             Paragraph(f"<b>{esc(company.upper())} EDITION</b> · {paper['counts_line']}", st["strap"]), rule(0.6, 2),
             FrameBreak(), NextPageTemplate("later")]

    items = paper["items"]
    if not items:
        story.append(Paragraph(f"No findings yet for {esc(company)}: its public profile names no technology or expertise "
                               f"{NAME} can confirm, so nothing is ranked rather than guessed.", st["body"]))
    else:
        lead = paper.get("lead") or items[0]
        story += [Paragraph("LEAD FINDING", st["kicker"])] + finding(lead, lead=True) + [rule(0.4, 5)]
        for kind, label in AREAS:
            rows = [i for i in items if i["kind"] == kind and i is not lead]
            if not rows:
                continue
            shown = rows[: paper.get("per_area", 5)]
            # a section heading never stands alone at the foot of a column
            story.append(KeepTogether([Paragraph(label.upper(), st["kicker"]), rule(0.4, 1)] + finding(shown[0])))
            for it in shown[1:]:
                story.append(KeepTogether(finding(it)))
            if len(rows) > paper.get("per_area", 5):
                story.append(Paragraph(f"and {len(rows) - paper.get('per_area', 5)} more on the radar.", st["meta"]))

    if paper.get("proposals"):
        story += [Spacer(1, 6), rule(1.2, 3), Paragraph("Proposed partnerships", st["h2"]),
                  Paragraph(f"HYPOTHESES. Generated by {NAME} from public information. No company has been contacted, and "
                            "funding eligibility has not been checked.", st["note"])]
        for r in paper["proposals"]:
            story += [Paragraph(esc(r["title"]), st["h3"]),
                      Paragraph(f"with {esc(' + '.join(r['partners']))} · score {r['score']:.0f} of 100", st["meta"]),
                      Paragraph(esc(r["explanation"])[:600], st["body"])]

    missed = paper.get("missed") or {}
    if missed.get("items"):
        story += [Spacer(1, 6), rule(1.2, 3), Paragraph("The opportunity you never saw", st["h2"]),
                  Paragraph(f"Calls that fitted {esc(company)}'s public profile and closed in the last 12 months "
                            f"(fit {missed['min_fit']:.0f} or more). Not an eligibility check.", st["meta"])]
        for c in missed["items"]:
            opened = f"{c['opened']:%Y-%m-%d}" if c.get("opened") else "date not published"
            story += [Paragraph(esc(_en(c, "title"))[:200], st["h3"]),
                      Paragraph(f"Open {opened} to {c['closed']:%Y-%m-%d} · fit {c['relevance']:.0f} · " + link(c["url"], "Vinnova call record"), st["meta"])]

    prof = paper.get("profile") or {}
    if prof:
        story += [Spacer(1, 6), rule(1.2, 3), Paragraph(f"About {esc(company)}", st["h2"])]
        if prof.get("description"):
            story.append(Paragraph(esc(prof["description"])[:700], st["body"]))
        for q in prof.get("capabilities", []):
            story.append(Paragraph(f"<b>{esc(q['name'])}</b> [FACT]: \"{esc(q['quote'])[:220]}\" " + link(q["url"], "source"), st["meta"]))
        if prof.get("inferred"):
            story.append(Paragraph("Inferred, not stated [INFERENCE]: " + esc("; ".join(prof["inferred"])), st["meta"]))

    story += [Spacer(1, 8), rule(0.6, 3), Paragraph("About this paper", st["kicker"]),
              Paragraph(f"Compiled by {NAME} for Blue Science Park members from public sources: the member directory, company "
                        "websites, Vinnova open data, OpenAlex, and the pages of Blue Science Park and Marine Technology Center of "
                        "Sweden. Every finding carries its source and date. Swedish texts are shown in machine translation. "
                        "Connections between members are generated proposals, not agreements. " + esc(paper["disclaimer"]), st["meta"])]
    doc.build(story)
    return buf.getvalue()


def filename(company_name: str, when: datetime) -> str:
    safe = "".join(ch if ch.isalnum() else "-" for ch in company_name).strip("-").lower()
    return f"echoradar-{safe}-{when:%Y-%m-%d}.pdf"
