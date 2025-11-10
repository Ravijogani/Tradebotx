import { LayoutDashboard, Layers, Calculator, Settings, Activity, FileText, Gift, BarChart3, MessageSquare, CreditCard, Brain } from "lucide-react";
import { NavLink } from "@/components/NavLink";
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

interface AppSidebarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

export function AppSidebar({ activeTab, onTabChange }: AppSidebarProps) {
  const { state } = useSidebar();
  const isCollapsed = state === "collapsed";
  const navigate = useNavigate();

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
    { id: "payments", label: "Payments", icon: FileText, path: "/payment-history" },
    { id: "referrals", label: "Referrals", icon: Gift, path: "/referral-program" },
    { id: "reports", label: "Reports", icon: BarChart3, path: "/pl-reports" },
  ];

  const handleQuickAccessClick = (path: string) => {
    navigate(path);
  };

  return (
    <Sidebar collapsible="icon" className="border-r border-border/50">
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
