
import ReactDOM from "react-dom/client";

import {
    AuthenticatedApp,
} from "./AuthenticatedApp";

import {
    AuthProvider,
} from "./context/AuthContext";

import "./index.css";


ReactDOM.createRoot(
    document.getElementById("root")!
).render(
    <AuthProvider>
        <AuthenticatedApp />
    </AuthProvider>
);
