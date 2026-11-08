
import {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useState,
} from "react";

import type {
    ReactNode,
} from "react";

import type {
    AuthenticatedUser,
} from "../api/auth";

import {
    changePassword as apiChangePassword,
    getCurrentSession,
    login as apiLogin,
    logout as apiLogout,
} from "../api/auth";

import {
    ApiError,
    clearCsrfToken,
} from "../api/client";


interface AuthContextValue {

    user: AuthenticatedUser | null;

    loading: boolean;

    login: (
        username: string,
        password: string,
    ) => Promise<void>;

    logout: () => Promise<void>;

    changePassword: (
        currentPassword: string,
        newPassword: string,
    ) => Promise<void>;
}


const AuthContext = createContext<
    AuthContextValue | undefined
>(undefined);


export function AuthProvider({
    children,
}: {
    children: ReactNode;
}) {

    const [user, setUser] = useState<
        AuthenticatedUser | null
    >(null);

    const [loading, setLoading] = useState(
        true
    );

    useEffect(() => {

        let cancelled = false;

        async function restoreSession() {

            try {

                const restoredUser = (
                    await getCurrentSession()
                );

                if (!cancelled) {
                    setUser(restoredUser);
                }

            } catch (error) {

                if (!cancelled) {

                    clearCsrfToken();
                    setUser(null);

                    if (
                        !(
                            error instanceof ApiError &&
                            error.status === 401
                        )
                    ) {

                        console.error(
                            "Session restoration failed.",
                            error,
                        );
                    }
                }

            } finally {

                if (!cancelled) {
                    setLoading(false);
                }
            }
        }

        void restoreSession();

        return () => {
            cancelled = true;
        };

    }, []);


    const login = useCallback(
        async (
            username: string,
            password: string,
        ) => {

            const authenticatedUser = (
                await apiLogin(
                    username,
                    password,
                )
            );

            setUser(
                authenticatedUser
            );
        },
        [],
    );


    const logout = useCallback(
        async () => {

            try {

                await apiLogout();

            } finally {

                setUser(null);
            }
        },
        [],
    );


    const changePassword = useCallback(
        async (
            currentPassword: string,
            newPassword: string,
        ) => {

            await apiChangePassword(
                currentPassword,
                newPassword,
            );

            setUser(null);
        },
        [],
    );


    return (
        <AuthContext.Provider
            value={{
                user,
                loading,
                login,
                logout,
                changePassword,
            }}
        >
            {children}
        </AuthContext.Provider>
    );
}


export function useAuth(): AuthContextValue {

    const context = useContext(
        AuthContext
    );

    if (context === undefined) {

        throw new Error(
            "useAuth must be used within AuthProvider."
        );
    }

    return context;
}
