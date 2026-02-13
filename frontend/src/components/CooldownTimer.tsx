"use client";

import { useEffect, useState } from "react";

interface CooldownTimerProps {
  cooldownSeconds: number;
  nextTurnNumber: number;
  serverCooldownSeconds?: number;
}

export function CooldownTimer({ cooldownSeconds, nextTurnNumber, serverCooldownSeconds }: CooldownTimerProps) {
  const [timeLeft, setTimeLeft] = useState(cooldownSeconds);

  useEffect(() => {
    // Sync with server value if provided (SSE live mode)
    if (serverCooldownSeconds != null && serverCooldownSeconds > 0) {
      setTimeLeft(serverCooldownSeconds);
    }
  }, [serverCooldownSeconds]);

  useEffect(() => {
    // Reset timer when cooldown changes (new turn arrived)
    setTimeLeft(cooldownSeconds);
  }, [cooldownSeconds]);

  useEffect(() => {
    if (timeLeft <= 0) return;

    const intervalId = setInterval(() => {
      setTimeLeft((prev) => Math.max(0, prev - 1));
    }, 1000);

    return () => clearInterval(intervalId);
  }, [timeLeft]);

  if (timeLeft <= 0) {
    return (
      <div className="flex items-center gap-3 py-4 px-5 rounded-xl border border-card-border bg-card animate-pulse-border">
        <div className="w-2 h-2 rounded-full bg-accent animate-pulse" />
        <span className="text-sm text-muted">
          Waiting for Turn {nextTurnNumber}...
        </span>
      </div>
    );
  }

  const progress = (timeLeft / cooldownSeconds) * 100;

  return (
    <div className="flex items-center gap-3 py-4 px-5 rounded-xl border border-card-border bg-card">
      <div className="relative w-8 h-8 flex items-center justify-center">
        <svg className="w-8 h-8 -rotate-90">
          <circle
            cx="16"
            cy="16"
            r="14"
            stroke="currentColor"
            strokeWidth="2"
            fill="none"
            className="text-card-border"
          />
          <circle
            cx="16"
            cy="16"
            r="14"
            stroke="currentColor"
            strokeWidth="2"
            fill="none"
            strokeDasharray={`${2 * Math.PI * 14}`}
            strokeDashoffset={`${2 * Math.PI * 14 * (1 - progress / 100)}`}
            className="text-accent transition-all duration-1000"
            strokeLinecap="round"
          />
        </svg>
        <span className="absolute text-xs font-mono font-bold text-accent">
          {timeLeft}
        </span>
      </div>
      <span className="text-sm text-muted">
        Next turn in {timeLeft}s...
      </span>
    </div>
  );
}
