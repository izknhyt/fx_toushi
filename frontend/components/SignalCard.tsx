import React from "react";

type SignalCardProps = {
  ticketId: string;
  symbol: string;
  side: string;
  status: string;
  onApprove?: () => void;
  onReject?: () => void;
  onDefer?: () => void;
};

export function SignalCard({
  ticketId,
  symbol,
  side,
  status,
  onApprove,
  onReject,
  onDefer,
}: SignalCardProps) {
  return (
    <div className="signal-card" data-ticket-id={ticketId}>
      <header className="signal-card__header">
        <div className="signal-card__symbol">{symbol}</div>
        <div className="signal-card__side">{side}</div>
      </header>
      <div className="signal-card__status">{status}</div>
      <footer className="signal-card__actions">
        <button type="button" onClick={onApprove}>
          Approve
        </button>
        <button type="button" onClick={onReject}>
          Reject
        </button>
        <button type="button" onClick={onDefer}>
          Defer
        </button>
      </footer>
    </div>
  );
}
