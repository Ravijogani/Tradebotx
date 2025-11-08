import { 
  Users, 
  Package, 
  TrendingUp, 
  Shield, 
  LayoutDashboard, 
  Activity, 
  UserCog, 
  Zap, 
  Mail, 
  BarChart3, 
  Gift, 
  Settings as SettingsIcon, 
  Receipt, 
  MessageSquare, 
  MonitorDot,
  ChevronDown,
  Sparkles
} from "lucide-react";
import { NavLink } from "@/components/NavLink";
import { useLocation } from "react-router-dom";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
  SidebarHeader,
} from "@/components/ui/sidebar";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { useState } from "react";

const mainItems = [
  { title: "AI Insights", path: "ai-insights", icon: Sparkles },
  { title: "Bot Monitor", path: "botmonitor", icon: MonitorDot },
  { title: "Users", path: "users", icon: Users },
  { title: "Support", path: "support", icon: MessageSquare },
];

const managementItems = [
  { title: "Roles", path: "roles", icon: UserCog },
  { title: "Strategies", path: "strategies", icon: Zap },
  { title: "Plans", path: "subscriptions", icon: Package },
];

const analyticsItems = [
  { title: "Analytics", path: "analytics", icon: TrendingUp },
  { title: "Platform", path: "platform", icon: BarChart3 },
  { title: "Referrals", path: "referrals", icon: Gift },
];

const operationsItems = [
  { title: "Invoices", path: "invoices", icon: Receipt },
  { title: "Email Templates", path: "emails", icon: Mail },
  { title: "Settings", path: "settings", icon: SettingsIcon },
  { title: "Activity Logs", path: "logs", icon: Activity },
];

export function AdminSidebar() {
  const { open } = useSidebar();
  const location = useLocation();
  const [openGroups, setOpenGroups] = useState({
    main: true,
    management: true,
    analytics: true,
    operations: true,
  });
  
  const getActiveTab = () => {
    const params = new URLSearchParams(location.search);
    return params.get('tab') || 'ai-insights';
  };

  const isActive = (path: string) => getActiveTab() === path;

  const toggleGroup = (group: keyof typeof openGroups) => {
    setOpenGroups(prev => ({ ...prev, [group]: !prev[group] }));
  };

  const SidebarGroupSection = ({ 
    title, 
    items, 
    groupKey 
  }: { 
    title: string; 
    items: typeof mainItems; 
    groupKey: keyof typeof openGroups;
  }) => (
    <Collapsible
      open={openGroups[groupKey]}
      onOpenChange={() => toggleGroup(groupKey)}
      className="group/collapsible"
    >
      <SidebarGroup>
        <CollapsibleTrigger asChild>
          <SidebarGroupLabel className="cursor-pointer hover:bg-sidebar-accent rounded-md transition-colors flex items-center justify-between group">
            <span>{title}</span>
            <ChevronDown className={`w-4 h-4 transition-transform ${openGroups[groupKey] ? 'rotate-180' : ''}`} />
          </SidebarGroupLabel>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <SidebarGroupContent>
            <SidebarMenu>
              {items.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton 
                    asChild
                    isActive={isActive(item.path)}
                    className="transition-all duration-200"
                  >
                    <a 
                      href={`?tab=${item.path}`}
                      className={`flex items-center gap-3 ${
                        isActive(item.path) 
                          ? 'bg-sidebar-primary text-sidebar-primary-foreground shadow-md' 
                          : 'hover:bg-sidebar-accent'
                      }`}
                    >
                      <item.icon className="w-4 h-4 flex-shrink-0" />
                      {open && <span className="truncate">{item.title}</span>}
                    </a>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </CollapsibleContent>
      </SidebarGroup>
    </Collapsible>
  );

  return (
    <Sidebar collapsible="icon" className="border-r border-sidebar-border">
      <SidebarHeader className="border-b border-sidebar-border p-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary to-accent flex items-center justify-center shadow-glow flex-shrink-0">
            <Shield className="w-5 h-5 text-white" />
          </div>
          {open && (
            <div className="truncate">
              <h2 className="font-bold text-sidebar-foreground">Admin Panel</h2>
              <p className="text-xs text-muted-foreground">Control Center</p>
            </div>
          )}
        </div>
      </SidebarHeader>

      <SidebarContent className="py-2">
        <SidebarGroupSection title="Dashboard" items={mainItems} groupKey="main" />
        <SidebarGroupSection title="Management" items={managementItems} groupKey="management" />
        <SidebarGroupSection title="Analytics" items={analyticsItems} groupKey="analytics" />
        <SidebarGroupSection title="Operations" items={operationsItems} groupKey="operations" />
      </SidebarContent>
    </Sidebar>
  );
}
