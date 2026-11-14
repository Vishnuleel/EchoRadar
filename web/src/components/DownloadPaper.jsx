import { useState } from "react";
import { Download } from "lucide-react";
import { api } from "../api";
import { useSession } from "../store";

/** Download the paper for the company in view as a PDF (the public edition, or the company's own when it reads as itself). */
export default function DownloadPaper({ compact }) {
  const { companyId, names } = useSession();
  const [state, setState] = useState("idle"); // idle | busy | error
  if (companyId == null) return null;
  const go = async () => {
    setState("busy");
    try {
      await api.downloadPaper(companyId);
      setState("idle");
    } catch {
      setState("error");
    }
  };
  const label = state === "busy" ? "Preparing..." : state === "error" ? "Could not create the PDF" : compact ? "PDF" : "Download as PDF";
  return (
    <button type="button" className="btn" onClick={go} disabled={state === "busy"}
            title={`Download the paper for ${names?.[companyId] ?? "this company"} as a PDF`} aria-label="Download the paper as a PDF">
      <Download size={14} />{label}
    </button>
  );
}
