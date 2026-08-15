import { LayoutDashboard, Layers, Calculator, Settings, Activity, FileText, Gift, BarChart3, MessageSquare, CreditCard, Brain, BookOpen, Wand2, Building2, Shield, Mail, GraduationCap } from "lucide-react";
import { useEffect, useState } from "react";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  useSidebar,
  SidebarSeparator,
} from "@/components/ui/sidebar";
import { useNavigate } from "react-router-dom";
import { useIsMobile } from "@/hooks/use-mobile";
import { cn } from "@/lib/utils";
import { supabase } from "@/integrations/supabase/client";
import type { Tables } from "@/integrations/supabase/types";

interface AppSidebarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

export function AppSidebar({ activeTab, onTabChange }: AppSidebarProps) {
  const { state } = useSidebar();
  const isMobile = useIsMobile();
  const isCollapsed = state === "collapsed" && !isMobile;
  const navigate = useNavigate();
  const [isEnterprise, setIsEnterprise] = useState(false);

  useEffect(() => {
    checkEnterprisePlan();
  }, []);

  const checkEnterprisePlan = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      const { data: subscription } = await supabase
        .from("user_subscriptions")
        .select("*, plans(*)")
        .eq("user_id", user.id)
        .single();

      const planType = (subscription?.plans as Pick<Tables<"plans">, "plan_type"> | null)?.plan_type;
      setIsEnterprise(planType === "enterprise");
    } catch (error) {
      console.error("Error checking plan:", error);
    }
  };

  const mainNavItems = [
    { id: "dashboard", label: "Overview", icon: LayoutDashboard },
    { id: "strategies", label: "Strategies", icon: Layers },
    { id: "ai-insights", label: "AI Insights", icon: Brain },
    { id: "activity", label: "Activity", icon: Activity },
    { id: "calculator", label: "Risk Calculator", icon: Calculator },
    { id: "support", label: "Support", icon: MessageSquare },
    { id: "subscription", label: "Subscription", icon: CreditCard },
  ];

  const quickAccessItems = [
    { id: "journal", label: "Trade Journal", icon: BookOpen, path: "/trade-journal" },
    { id: "lessons", label: "Trading Lessons", icon: GraduationCap, path: "/trading-lessons" },
    { id: "payments", label: "Payments", icon: FileText, path: "/payment-history" },
    { id: "referrals", label: "Referrals", icon: Gift, path: "/referral-program" },
    { id: "reports", label: "Reports", icon: BarChart3, path: "/pl-reports" },
  ];

  const enterpriseItems = [
    { id: "strategy-builder", label: "Strategy Builder", icon: Wand2, path: "/strategy-builder" },
    { id: "multi-account", label: "Multi-Account", icon: Building2, tab: "multi-account" },
    { id: "audit-logs", label: "Audit Logs", icon: Shield, tab: "audit-logs" },
    { id: "email-reports", label: "Email Reports", icon: Mail, tab: "email-reports" },
  ];

  const handleEnterpriseClick = (item: typeof enterpriseItems[0]) => {
    if (item.path) {
      navigate(item.path);
    } else if (item.tab) {
      onTabChange(item.tab);
    }
  };

  const handleQuickAccessClick = (path: string) => {
    navigate(path);
  };

  return (
    <Sidebar collapsible="icon" className={cn("border-r border-border/50", isMobile && "w-full")}>
      <SidebarContent className="bg-sidebar/50 backdrop-blur-xl">
        <SidebarGroup>
          <SidebarGroupLabel className={`text-xs font-semibold ${isCollapsed ? "justify-center px-2" : "px-3"}`}>
            {!isCollapsed ? "Navigation" : "Nav"}
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu className="space-y-1">
              {mainNavItems.map((item) => (
                <SidebarMenuItem key={item.id}>
                  <SidebarMenuButton
                    onClick={() => onTabChange(item.id)}
                    isActive={activeTab === item.id}
                    tooltip={isCollapsed ? item.label : undefined}
                    className="transition-all duration-200 hover:bg-sidebar-accent min-h-[44px]"
                  >
                    <item.icon className="w-5 h-5 flex-shrink-0" />
                    {!isCollapsed && <span className="text-sm font-medium">{item.label}</span>}
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarSeparator className="my-2" />

        <SidebarGroup>
          <SidebarGroupLabel className={`text-xs font-semibold ${isCollapsed ? "justify-center px-2" : "px-3"}`}>
            {!isCollapsed ? "Quick Access" : "Quick"}
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu className="space-y-1">
              {quickAccessItems.map((item) => (
                <SidebarMenuItem key={item.id}>
                  <SidebarMenuButton
                    onClick={() => handleQuickAccessClick(item.path)}
                    tooltip={isCollapsed ? item.label : undefined}
                    className="transition-all duration-200 hover:bg-sidebar-accent min-h-[44px]"
                  >
                    <item.icon className="w-5 h-5 flex-shrink-0" />
                    {!isCollapsed && <span className="text-sm font-medium">{item.label}</span>}
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {isEnterprise && (
          <>
            <SidebarSeparator className="my-2" />

            <SidebarGroup>
              <SidebarGroupLabel className={`text-xs font-semibold ${isCollapsed ? "justify-center px-2" : "px-3"}`}>
                {!isCollapsed ? "Enterprise" : "Ent"}
              </SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu className="space-y-1">
                  {enterpriseItems.map((item) => (
                    <SidebarMenuItem key={item.id}>
                      <SidebarMenuButton
                        onClick={() => handleEnterpriseClick(item)}
                        isActive={activeTab === item.id || activeTab === item.tab}
                        tooltip={isCollapsed ? item.label : undefined}
                        className="transition-all duration-200 hover:bg-sidebar-accent min-h-[44px]"
                      >
                        <item.icon className="w-5 h-5 flex-shrink-0" />
                        {!isCollapsed && <span className="text-sm font-medium">{item.label}</span>}
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          </>
        )}

        <SidebarSeparator className="my-2" />

        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton
                  onClick={() => onTabChange("settings")}
                  isActive={activeTab === "settings"}
                  tooltip={isCollapsed ? "Settings" : undefined}
                  className="transition-all duration-200 hover:bg-sidebar-accent min-h-[44px]"
                >
                  <Settings className="w-5 h-5 flex-shrink-0" />
                  {!isCollapsed && <span className="text-sm font-medium">Settings</span>}
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
}
