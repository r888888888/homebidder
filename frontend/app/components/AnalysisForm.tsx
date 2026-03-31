import { useState, FormEvent } from "react";

interface Props {
  onSubmit: (url: string, buyerContext: string) => void;
  isRunning: boolean;
}

export function AnalysisForm({ onSubmit, isRunning }: Props) {
  const [url, setUrl] = useState("");
  const [buyerContext, setBuyerContext] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!url.trim() || isRunning) return;
    onSubmit(url.trim(), buyerContext.trim());
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Listing URL
        </label>
        <input
          type="url"
          required
          placeholder="https://www.zillow.com/homedetails/..."
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          disabled={isRunning}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Buyer notes <span className="text-gray-400">(optional)</span>
        </label>
        <textarea
          rows={2}
          placeholder="e.g. multiple offers expected, need to close in 30 days, flexible on repairs"
          value={buyerContext}
          onChange={(e) => setBuyerContext(e.target.value)}
          disabled={isRunning}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 resize-none"
        />
      </div>

      <button
        type="submit"
        disabled={isRunning || !url.trim()}
        className="w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isRunning ? "Analyzing…" : "Analyze Listing"}
      </button>
    </form>
  );
}
