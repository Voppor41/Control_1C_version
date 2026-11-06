import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { AuthProvider } from "./auth/session";
import "./styles/global.css";
import { ConfirmProvider } from "./ui/confirm";
import { ToastProvider } from "./ui/toast";

const root = document.getElementById("root");
if (!root) throw new Error("Root element is missing");

createRoot(root).render(
  <StrictMode>
    <AuthProvider>
      <ToastProvider>
        <ConfirmProvider>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </ConfirmProvider>
      </ToastProvider>
    </AuthProvider>
  </StrictMode>,
);
