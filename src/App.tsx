import { Suspense, lazy } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Loader2 } from "lucide-react";

// Routed page components are code-split so a visitor to the landing page
// isn't also downloading the admin dashboard and strategy builder bundles.
const Landing = lazy(() => import("./pages/Landing"));
const Pricing = lazy(() => import("./pages/Pricing"));
const Login = lazy(() => import("./pages/auth/Login"));
const ResetPassword = lazy(() => import("./pages/auth/ResetPassword"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Admin = lazy(() => import("./pages/Admin"));
const AdminDashboard = lazy(() => import("./pages/AdminDashboard"));
const PaymentHistory = lazy(() => import("./pages/PaymentHistory"));
const ReferralProgram = lazy(() => import("./pages/ReferralProgram"));
const PLReports = lazy(() => import("./pages/PLReports"));
const NotFound = lazy(() => import("./pages/NotFound"));
const Terms = lazy(() => import("./pages/Terms"));
const Privacy = lazy(() => import("./pages/Privacy"));
const Disclaimer = lazy(() => import("./pages/Disclaimer"));
const Status = lazy(() => import("./pages/Status"));
const Docs = lazy(() => import("./pages/Docs"));
const TradeJournal = lazy(() => import("./pages/TradeJournal"));
const TradingLessons = lazy(() => import("./pages/TradingLessons"));
const StrategyBuilderPage = lazy(() => import("./pages/StrategyBuilderPage"));
const ProtectedRoute = lazy(() => import("@/components/ProtectedRoute"));

const queryClient = new QueryClient();

const PageLoading = () => (
  <div className="flex min-h-screen items-center justify-center">
    <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
  </div>
);

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <ErrorBoundary>
        <BrowserRouter>
          <Suspense fallback={<PageLoading />}>
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route path="/pricing" element={<Pricing />} />
              <Route path="/auth/login" element={<Login />} />
              <Route path="/auth/reset-password" element={<ResetPassword />} />
              <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
              <Route path="/admin" element={<Admin />} />
              <Route
                path="/admin/dashboard"
                element={
                  <ProtectedRoute requireRole="admin" redirectTo="/admin" redirectToOnForbidden="/dashboard">
                    <AdminDashboard />
                  </ProtectedRoute>
                }
              />
              <Route path="/payment-history" element={<ProtectedRoute><PaymentHistory /></ProtectedRoute>} />
              <Route path="/referral-program" element={<ProtectedRoute><ReferralProgram /></ProtectedRoute>} />
              <Route path="/pl-reports" element={<ProtectedRoute><PLReports /></ProtectedRoute>} />
              <Route path="/terms" element={<Terms />} />
              <Route path="/privacy" element={<Privacy />} />
              <Route path="/disclaimer" element={<Disclaimer />} />
              <Route path="/status" element={<Status />} />
              <Route path="/docs" element={<Docs />} />
              <Route path="/trade-journal" element={<ProtectedRoute><TradeJournal /></ProtectedRoute>} />
              <Route path="/trading-lessons" element={<ProtectedRoute><TradingLessons /></ProtectedRoute>} />
              <Route path="/strategy-builder" element={<ProtectedRoute><StrategyBuilderPage /></ProtectedRoute>} />
              {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </ErrorBoundary>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
