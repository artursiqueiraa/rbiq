import { useState } from "react";
import { DataCenterPage } from "./pages/DataCenterPage";
import { HomePage } from "./pages/HomePage";
import { IndicatorLabPage } from "./pages/IndicatorLabPage";
import { MarketLabPage } from "./pages/MarketLabPage";
import "./App.css";

type Tab = "home" | "data-center" | "indicator-lab" | "market-lab";

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
      </nav>
      {tab === "home" && <HomePage />}
      {tab === "data-center" && <DataCenterPage />}
      {tab === "indicator-lab" && <IndicatorLabPage />}
      {tab === "market-lab" && <MarketLabPage />}
    </div>
  );
}

export default App;
