import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Landing from "./pages/Landing";
import Pricing from "./pages/Pricing";
import Login from "./pages/auth/Login";
import ResetPassword from "./pages/auth/ResetPassword";
import Dashboard from "./pages/Dashboard";
import Admin from "./pages/Admin";
import AdminDashboard from "./pages/AdminDashboard";
import PaymentHistory from "./pages/PaymentHistory";
import ReferralProgram from "./pages/ReferralProgram";
import PLReports from "./pages/PLReports";
import NotFound from "./pages/NotFound";
import Terms from "./pages/Terms";
import Privacy from "./pages/Privacy";
import Disclaimer from "./pages/Disclaimer";
import Status from "./pages/Status";
import Docs from "./pages/Docs";
import TradeJournal from "./pages/TradeJournal";
import StrategyBuilderPage from "./pages/StrategyBuilderPage";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/pricing" element={<Pricing />} />
          <Route path="/auth/login" element={<Login />} />
          <Route path="/auth/reset-password" element={<ResetPassword />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="/admin/dashboard" element={<AdminDashboard />} />
          <Route path="/payment-history" element={<PaymentHistory />} />
          <Route path="/referral-program" element={<ReferralProgram />} />
          <Route path="/pl-reports" element={<PLReports />} />
          <Route path="/terms" element={<Terms />} />
          <Route path="/privacy" element={<Privacy />} />
          <Route path="/disclaimer" element={<Disclaimer />} />
          <Route path="/status" element={<Status />} />
          <Route path="/docs" element={<Docs />} />
          <Route path="/trade-journal" element={<TradeJournal />} />
          <Route path="/strategy-builder" element={<StrategyBuilderPage />} />
          {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
