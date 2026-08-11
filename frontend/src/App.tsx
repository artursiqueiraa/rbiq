import { useState } from "react";
import { DataCenterPage } from "./pages/DataCenterPage";
import { HomePage } from "./pages/HomePage";
import { IndicatorLabPage } from "./pages/IndicatorLabPage";
import { MarketLabPage } from "./pages/MarketLabPage";
import { StrategyLabPage } from "./pages/StrategyLabPage";
import "./App.css";

type Tab = "home" | "data-center" | "indicator-lab" | "market-lab" | "strategy-lab";

function App() {
  const [tab, setTab] = useState<Tab>("home");

  return (
    <div>
      <nav className="top-nav">
        <button className={tab === "home" ? "active" : ""} onClick={() => setTab("home")}>
          Início
        </button>
        <button className={tab === "data-center" ? "active" : ""} onClick={() => setTab("data-center")}>
          Data Center
        </button>
        <button className={tab === "indicator-lab" ? "active" : ""} onClick={() => setTab("indicator-lab")}>
          Indicator Lab
        </button>
        <button className={tab === "market-lab" ? "active" : ""} onClick={() => setTab("market-lab")}>
          Market Lab
        </button>
        <button className={tab === "strategy-lab" ? "active" : ""} onClick={() => setTab("strategy-lab")}>
          Strategy Lab
        </button>
      </nav>
      {tab === "home" && <HomePage />}
      {tab === "data-center" && <DataCenterPage />}
      {tab === "indicator-lab" && <IndicatorLabPage />}
      {tab === "market-lab" && <MarketLabPage />}
      {tab === "strategy-lab" && <StrategyLabPage />}
    </div>
  );
}

export default App;
