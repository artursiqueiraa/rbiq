import { useState } from "react";
import { DataCenterPage } from "./pages/DataCenterPage";
import { HomePage } from "./pages/HomePage";
import "./App.css";

type Tab = "home" | "data-center";

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
      </nav>
      {tab === "home" ? <HomePage /> : <DataCenterPage />}
    </div>
  );
}

export default App;
