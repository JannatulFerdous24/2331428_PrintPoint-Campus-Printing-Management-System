import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
import { AuthProvider } from "./auth/AuthContext"
import { GuestOnly, RequireAdmin, RequireAuth } from "./auth/guards"
import { Layout } from "./components/Layout"
import { AdminAuditPage } from "./pages/AdminAuditPage"
import { AdminDashboardPage } from "./pages/AdminDashboardPage"
import { AdminGroupDetailPage } from "./pages/AdminGroupDetailPage"
import { AdminModerationPage } from "./pages/AdminModerationPage"
import { AdminUserDetailPage } from "./pages/AdminUserDetailPage"
import { AdminUsersPage } from "./pages/AdminUsersPage"
import { StaffQueuePage } from "./pages/StaffQueuePage"
import { GroupDetailPage } from "./pages/GroupDetailPage"
import { GroupsPage } from "./pages/GroupsPage"
import { LoginPage } from "./pages/LoginPage"
import { NotFoundPage } from "./pages/NotFoundPage"
import { PrintRequestsPage } from "./pages/PrintRequestsPage"
import { ProfilePage } from "./pages/ProfilePage"
import { SessionsPage } from "./pages/SessionsPage"
import { SignupPage } from "./pages/SignupPage"

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Only for visitors who are NOT logged in */}
          <Route element={<GuestOnly />}>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
          </Route>

          {/* Only for logged-in users (the server checks every API call as well) */}
          <Route element={<RequireAuth />}>
            <Route element={<Layout />}>
              <Route path="/requests" element={<PrintRequestsPage />} />
              <Route path="/profile" element={<ProfilePage />} />
              <Route path="/sessions" element={<SessionsPage />} />
              <Route path="/groups" element={<GroupsPage />} />
              <Route path="/groups/:groupId" element={<GroupDetailPage />} />
              <Route element={<RequireAdmin />}>
                <Route path="/staff/queue" element={<StaffQueuePage />} />
                <Route path="/admin" element={<AdminDashboardPage />} />
                <Route path="/admin/users" element={<AdminUsersPage />} />
                <Route path="/admin/users/:userId" element={<AdminUserDetailPage />} />
                <Route path="/admin/moderation" element={<AdminModerationPage key="moderation" />} />
                <Route path="/admin/groups" element={<AdminModerationPage key="groups" initialTab="groups" />} />
                <Route path="/admin/groups/:groupId" element={<AdminGroupDetailPage />} />
                <Route path="/admin/audit" element={<AdminAuditPage />} />
              </Route>
            </Route>
          </Route>

          <Route path="/" element={<Navigate to="/requests" replace />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
