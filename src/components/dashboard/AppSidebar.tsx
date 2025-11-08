import { LayoutDashboard, Layers, Calculator, Settings, Activity, FileText, Gift, BarChart3 } from "lucide-react";
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
    { id: "activity", label: "Activity", icon: Activity },
    { id: "calculator", label: "Risk Calculator", icon: Calculator },
  ];

  const quickAccessItems = [
    { id: "payments", label: "Payments", icon: FileText, path: "/payment-history" },
    { id: "referrals", label: "Referrals", icon: Gift, path: "/referral-program" },
    { id: "reports", label: "Reports", icon: BarChart3, path: "/pl-reports" },
  ];

  return (
    <Sidebar collapsible="icon" className="border-r border-border/50">
      <SidebarContent className="bg-card/30 backdrop-blur-xl">
        <SidebarGroup>
          <SidebarGroupLabel className={isCollapsed ? "justify-center" : ""}>
            {!isCollapsed && "Navigation"}
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu className="space-y-1">
              {mainNavItems.map((item) => (
                <SidebarMenuItem key={item.id}>
                  <SidebarMenuButton
                    onClick={() => onTabChange(item.id)}
                    isActive={activeTab === item.id}
                    tooltip={isCollapsed ? item.label : undefined}
                    className="transition-all duration-200"
                  >
                    <item.icon className="w-5 h-5" />
                    {!isCollapsed && <span>{item.label}</span>}
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarSeparator />

        <SidebarGroup>
          <SidebarGroupLabel className={isCollapsed ? "justify-center" : ""}>
            {!isCollapsed && "Quick Access"}
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu className="space-y-1">
              {quickAccessItems.map((item) => (
                <SidebarMenuItem key={item.id}>
                  <SidebarMenuButton
                    onClick={() => navigate(item.path)}
                    tooltip={isCollapsed ? item.label : undefined}
                    className="transition-all duration-200"
                  >
                    <item.icon className="w-5 h-5" />
                    {!isCollapsed && <span>{item.label}</span>}
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarSeparator />

        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton
                  onClick={() => onTabChange("settings")}
                  isActive={activeTab === "settings"}
                  tooltip={isCollapsed ? "Settings" : undefined}
                  className="transition-all duration-200"
                >
                  <Settings className="w-5 h-5" />
                  {!isCollapsed && <span>Settings</span>}
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
}
