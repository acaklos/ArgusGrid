import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { NotifyProvider } from "./components/Notify";
import "./i18n";
import { SessionProvider } from "./state/session";
import "./styles/tokens.css";
import "./styles/base.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <NotifyProvider>
        <SessionProvider>
          <App />
        </SessionProvider>
      </NotifyProvider>
    </BrowserRouter>
  </StrictMode>,
);
