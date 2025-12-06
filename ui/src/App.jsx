import React, { useState } from "react";

const initialState = {
  killSwitch: "none",
  reason: "none",
};

export default function App() {
  const [state, setState] = useState(initialState);

  const toggleKillSwitch = () => {
    setState((prev) =>
      prev.killSwitch === "none"
        ? { killSwitch: "soft_stop", reason: "spread_block" }
        : initialState,
    );
  };

  return (
    <div className="app">
      <header>
        <h1>Kill Switch Demo</h1>
        <p data-testid="kill-switch-banner">
          Kill Switch: {state.killSwitch.toUpperCase()} (reason: {state.reason})
        </p>
      </header>

      <button data-testid="toggle-kill-switch" onClick={toggleKillSwitch}>
        {state.killSwitch === "none" ? "Set Soft Stop" : "Clear Kill Switch"}
      </button>
    </div>
  );
}
