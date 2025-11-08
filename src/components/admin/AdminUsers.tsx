import { useState, useEffect } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Loader2, Search, UserCheck, UserX, CheckCircle, XCircle, Clock, AlertCircle } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";

export const AdminUsers = () => {
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedUser, setSelectedUser] = useState<any>(null);
  const [approvalNotes, setApprovalNotes] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      const { data: profiles, error } = await supabase
        .from("profiles")
        .select(`
          *,
          user_subscriptions (
            status,
            subscription_tier,
            trial_ends_at,
            plans (
              plan_type
            )
          ),
          user_setup (
            mt5_account,
            is_completed,
            admin_approved,
            broker_name,
            broker_account_id,
            broker_referral_code,
            submitted_for_approval_at,
            approval_notes
          )
        `)
        .order("created_at", { ascending: false });

      if (error) throw error;
      setUsers(profiles || []);
    } catch (error: any) {
      toast({
        title: "Error loading users",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleApproval = async (userId: string, approved: boolean) => {
    setActionLoading(true);
    try {
      const { error } = await supabase
        .from("user_setup")
        .update({
          admin_approved: approved,
          approval_notes: approvalNotes || null,
        })
        .eq("user_id", userId);

      if (error) throw error;

      toast({
        title: approved ? "User Approved" : "User Rejected",
        description: approved 
          ? "User can now start trading bots" 
          : "User has been notified of rejection",
      });

      setSelectedUser(null);
      setApprovalNotes("");
      loadUsers();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setActionLoading(false);
    }
  };

  const filteredUsers = users.filter(user =>
    user.email?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    user.full_name?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Filter for pending approvals (all users waiting for approval)
  const pendingApprovals = filteredUsers.filter(user => {
    const setup = user.user_setup?.[0];
    
    return setup?.is_completed && !setup?.admin_approved;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <>
      <div className="space-y-6">
        {/* Pending Approvals Alert */}
        {pendingApprovals.length > 0 && (
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertDescription className="flex items-center justify-between">
              <span>
                <strong>{pendingApprovals.length}</strong> user{pendingApprovals.length > 1 ? 's' : ''} waiting for approval
              </span>
            </AlertDescription>
          </Alert>
        )}

        {/* Pending Approvals Section */}
        {pendingApprovals.length > 0 && (
          <Card className="border-orange-500/20 bg-orange-500/5">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="h-5 w-5 text-orange-500" />
                Pending Approvals
              </CardTitle>
              <CardDescription>
                Review and approve all user accounts
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>User</TableHead>
                      <TableHead>Broker</TableHead>
                      <TableHead>Broker Account ID</TableHead>
                      <TableHead>Submitted</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {pendingApprovals.map((user) => {
                      const setup = user.user_setup?.[0];
                      return (
                        <TableRow key={user.id}>
                          <TableCell>
                            <div>
                              <div className="font-medium">{user.full_name || "N/A"}</div>
                              <div className="text-sm text-muted-foreground">{user.email}</div>
                            </div>
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline">{setup?.broker_name || "N/A"}</Badge>
                          </TableCell>
                          <TableCell className="font-mono text-sm">
                            {setup?.broker_account_id || "N/A"}
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {setup?.submitted_for_approval_at 
                              ? new Date(setup.submitted_for_approval_at).toLocaleDateString()
                              : "N/A"}
                          </TableCell>
                          <TableCell>
                            <div className="flex gap-2">
                              <Button
                                size="sm"
                                variant="default"
                                onClick={() => setSelectedUser({ ...user, action: 'approve' })}
                              >
                                <CheckCircle className="h-4 w-4 mr-1" />
                                Approve
                              </Button>
                              <Button
                                size="sm"
                                variant="destructive"
                                onClick={() => setSelectedUser({ ...user, action: 'reject' })}
                              >
                                <XCircle className="h-4 w-4 mr-1" />
                                Reject
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        )}

        {/* All Users Section */}
        <Card>
          <CardHeader>
            <CardTitle>All Users</CardTitle>
            <CardDescription>
              Manage user accounts and subscriptions
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-2">
              <Search className="w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search users by email or name..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="max-w-sm"
              />
            </div>

            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>User</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Plan</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Setup</TableHead>
                    <TableHead>Approval</TableHead>
                    <TableHead>Joined</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredUsers.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center text-muted-foreground">
                        No users found
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredUsers.map((user) => {
                      const setup = user.user_setup?.[0];
                      const subscription = user.user_subscriptions?.[0];
                      const planType = subscription?.plans?.plan_type;
                      
                      return (
                        <TableRow key={user.id}>
                          <TableCell className="font-medium">
                            {user.full_name || "N/A"}
                          </TableCell>
                          <TableCell>{user.email}</TableCell>
                          <TableCell>
                            <Badge variant="outline">
                              {planType || "starter"}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            {subscription?.status === "active" ? (
                              <Badge className="bg-green-500/10 text-green-500 border-green-500/20">
                                <UserCheck className="w-3 h-3 mr-1" />
                                Active
                              </Badge>
                            ) : (
                              <Badge variant="secondary">
                                <UserX className="w-3 h-3 mr-1" />
                                {subscription?.status || "trial"}
                              </Badge>
                            )}
                          </TableCell>
                          <TableCell>
                            {setup?.is_completed ? (
                              <Badge className="bg-blue-500/10 text-blue-500 border-blue-500/20">
                                Completed
                              </Badge>
                            ) : (
                              <Badge variant="secondary">Pending</Badge>
                            )}
                          </TableCell>
                          <TableCell>
                            {setup?.admin_approved ? (
                              <Badge className="bg-green-500/10 text-green-500 border-green-500/20">
                                Approved
                              </Badge>
                            ) : setup?.is_completed ? (
                              <Badge className="bg-orange-500/10 text-orange-500 border-orange-500/20">
                                <Clock className="w-3 h-3 mr-1" />
                                Pending
                              </Badge>
                            ) : (
                              <Badge variant="secondary">N/A</Badge>
                            )}
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {new Date(user.created_at).toLocaleDateString()}
                          </TableCell>
                        </TableRow>
                      );
                    })
                  )}
                </TableBody>
              </Table>
            </div>

            <div className="flex items-center justify-between text-sm text-muted-foreground">
              <span>Total Users: {filteredUsers.length}</span>
              <span>Pending Approvals: {pendingApprovals.length}</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Approval Dialog */}
      <Dialog open={!!selectedUser} onOpenChange={() => setSelectedUser(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {selectedUser?.action === 'approve' ? 'Approve User' : 'Reject User'}
            </DialogTitle>
            <DialogDescription>
              {selectedUser?.action === 'approve' 
                ? 'Approve this user to start trading with their bot?'
                : 'Reject this user\'s setup? They will need to resubmit.'}
            </DialogDescription>
          </DialogHeader>

          {selectedUser && (
            <div className="space-y-4">
              <div className="p-4 bg-muted rounded-lg space-y-2">
                <div className="text-sm">
                  <span className="text-muted-foreground">User:</span>{" "}
                  <span className="font-medium">{selectedUser.email}</span>
                </div>
                <div className="text-sm">
                  <span className="text-muted-foreground">Broker:</span>{" "}
                  <span className="font-medium">{selectedUser.user_setup?.[0]?.broker_name || "N/A"}</span>
                </div>
                <div className="text-sm">
                  <span className="text-muted-foreground">Broker Account:</span>{" "}
                  <span className="font-mono font-medium">{selectedUser.user_setup?.[0]?.broker_account_id || "N/A"}</span>
                </div>
                <div className="text-sm">
                  <span className="text-muted-foreground">Referral Code:</span>{" "}
                  <span className="font-mono font-medium">{selectedUser.user_setup?.[0]?.broker_referral_code || "N/A"}</span>
                </div>
              </div>

              <div>
                <Label htmlFor="notes">Notes (Optional)</Label>
                <Textarea
                  id="notes"
                  value={approvalNotes}
                  onChange={(e) => setApprovalNotes(e.target.value)}
                  placeholder={
                    selectedUser.action === 'approve'
                      ? "Add any approval notes..."
                      : "Add rejection reason..."
                  }
                  className="mt-1.5"
                />
              </div>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setSelectedUser(null)}>
              Cancel
            </Button>
            <Button
              variant={selectedUser?.action === 'approve' ? 'default' : 'destructive'}
              onClick={() => handleApproval(selectedUser.id, selectedUser.action === 'approve')}
              disabled={actionLoading}
            >
              {actionLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Processing...
                </>
              ) : (
                selectedUser?.action === 'approve' ? 'Approve User' : 'Reject User'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};