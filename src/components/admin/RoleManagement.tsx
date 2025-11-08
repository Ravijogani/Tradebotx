import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { Loader2, Shield, UserPlus, UserMinus, Search } from "lucide-react";

const ADMIN_EMAIL = "admin@tradebotx.com"; // Configure this with your admin email

interface UserWithRoles {
  id: string;
  email: string;
  full_name: string;
  roles: string[];
}

export const RoleManagement = () => {
  const [users, setUsers] = useState<UserWithRoles[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedRole, setSelectedRole] = useState<"admin" | "user">("user");
  const { toast } = useToast();

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      const { data: profiles, error: profilesError } = await supabase
        .from("profiles")
        .select("id, email, full_name")
        .order("email");

      if (profilesError) throw profilesError;

      const { data: rolesData, error: rolesError } = await supabase
        .from("user_roles")
        .select("user_id, role");

      if (rolesError) throw rolesError;

      const usersWithRoles = profiles?.map((profile) => ({
        ...profile,
        roles: rolesData?.filter((r) => r.user_id === profile.id).map((r) => r.role) || [],
      })) || [];

      setUsers(usersWithRoles);
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const logActivity = async (actionType: string, targetUserId: string, description: string) => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      await supabase.from("admin_activity_logs").insert({
        admin_user_id: user.id,
        action_type: actionType,
        target_user_id: targetUserId,
        description: description,
      });
    } catch (error) {
      console.error("Error logging activity:", error);
    }
  };

  const handleAssignRole = async (userId: string, role: "admin" | "user", userEmail: string) => {
    try {
      const { error } = await supabase.from("user_roles").insert([{
        user_id: userId,
        role: role,
      }]);

      if (error) {
        if (error.code === "23505") {
          toast({
            title: "Role Already Assigned",
            description: `User already has the ${role} role`,
            variant: "destructive",
          });
          return;
        }
        throw error;
      }

      await logActivity(
        "role_assigned",
        userId,
        `Assigned ${role} role to ${userEmail}`
      );

      // Send email notification to admin
      try {
        const { data: { user: currentUser } } = await supabase.auth.getUser();
        await supabase.functions.invoke('send-admin-alert', {
          body: {
            adminEmail: ADMIN_EMAIL,
            actionType: 'Role Assigned',
            performedBy: currentUser?.email || 'Unknown Admin',
            targetUser: userEmail,
            details: `The ${role} role has been assigned to this user. This grants them ${role === 'admin' ? 'administrative privileges including user management and system configuration' : 'standard user access to the platform'}.`
          }
        });
      } catch (emailError) {
        console.error('Failed to send admin alert email:', emailError);
      }

      toast({
        title: "Role Assigned",
        description: `Successfully assigned ${role} role to ${userEmail}`,
      });

      loadUsers();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    }
  };

  const handleRevokeRole = async (userId: string, role: "admin" | "user", userEmail: string) => {
    try {
      const { error } = await supabase
        .from("user_roles")
        .delete()
        .eq("user_id", userId)
        .eq("role", role);

      if (error) throw error;

      await logActivity(
        "role_revoked",
        userId,
        `Revoked ${role} role from ${userEmail}`
      );

      // Send email notification to admin
      try {
        const { data: { user: currentUser } } = await supabase.auth.getUser();
        await supabase.functions.invoke('send-admin-alert', {
          body: {
            adminEmail: ADMIN_EMAIL,
            actionType: 'Role Revoked',
            performedBy: currentUser?.email || 'Unknown Admin',
            targetUser: userEmail,
            details: `The ${role} role has been revoked from this user. They will no longer have ${role === 'admin' ? 'administrative privileges' : 'this role\'s permissions'}.`
          }
        });
      } catch (emailError) {
        console.error('Failed to send admin alert email:', emailError);
      }

      toast({
        title: "Role Revoked",
        description: `Successfully revoked ${role} role from ${userEmail}`,
      });

      loadUsers();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    }
  };

  const filteredUsers = users.filter(
    (user) =>
      user.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
      user.full_name?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Shield className="w-5 h-5" />
          Role Management
        </CardTitle>
        <CardDescription>
          Assign or revoke admin and moderator roles for users
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Search and Filter */}
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Search users..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9"
            />
          </div>
          <Select value={selectedRole} onValueChange={(value: "admin" | "user") => setSelectedRole(value)}>
            <SelectTrigger className="w-[150px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="admin">Admin</SelectItem>
              <SelectItem value="user">User</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Users List */}
        <div className="space-y-2 max-h-[500px] overflow-y-auto">
          {filteredUsers.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No users found
            </div>
          ) : (
            filteredUsers.map((user) => (
              <div
                key={user.id}
                className="flex items-center justify-between p-4 rounded-lg border border-border/50 bg-card/50 hover:bg-card transition-colors"
              >
                <div className="flex-1">
                  <p className="font-medium">{user.full_name || "No name"}</p>
                  <p className="text-sm text-muted-foreground">{user.email}</p>
                  <div className="flex gap-2 mt-2">
                    {user.roles.length > 0 ? (
                      user.roles.map((role) => (
                        <Badge key={role} variant="outline" className="gap-1">
                          {role}
                          <button
                            onClick={() => handleRevokeRole(user.id, role as "admin" | "user", user.email)}
                            className="ml-1 hover:text-destructive"
                          >
                            ×
                          </button>
                        </Badge>
                      ))
                    ) : (
                      <Badge variant="outline" className="text-muted-foreground">
                        No special roles
                      </Badge>
                    )}
                  </div>
                </div>
                <div className="flex gap-2">
                  {!user.roles.includes(selectedRole) ? (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleAssignRole(user.id, selectedRole, user.email)}
                      className="gap-2"
                    >
                      <UserPlus className="w-4 h-4" />
                      Assign {selectedRole}
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => handleRevokeRole(user.id, selectedRole, user.email)}
                      className="gap-2"
                    >
                      <UserMinus className="w-4 h-4" />
                      Revoke {selectedRole}
                    </Button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
};
