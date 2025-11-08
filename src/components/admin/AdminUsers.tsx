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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Loader2, Search, UserCheck, UserX, CheckCircle, XCircle, Clock, AlertCircle, Eye, Filter, Mail, Download } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { UserProfileModal } from "@/components/admin/UserProfileModal";

const ADMIN_EMAIL = "admin@tradebotx.com"; // Configure this with your admin email

export const AdminUsers = () => {
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedUser, setSelectedUser] = useState<any>(null);
  const [selectedUserIdForProfile, setSelectedUserIdForProfile] = useState<string | null>(null);
  const [approvalNotes, setApprovalNotes] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [selectedUsers, setSelectedUsers] = useState<string[]>([]);
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [filterPlan, setFilterPlan] = useState<string>("all");
  const [filterApproval, setFilterApproval] = useState<string>("all");
  const [showBulkEmailDialog, setShowBulkEmailDialog] = useState(false);
  const [bulkEmailSubject, setBulkEmailSubject] = useState("");
  const [bulkEmailMessage, setBulkEmailMessage] = useState("");
  const { toast } = useToast();

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      // Load profiles first
      const { data: profiles, error: profilesError } = await supabase
        .from("profiles")
        .select("*")
        .order("created_at", { ascending: false });

      if (profilesError) throw profilesError;

      // Load subscriptions
      const userIds = profiles?.map(p => p.id) || [];
      const { data: subscriptions } = await supabase
        .from("user_subscriptions")
        .select("*, plans(plan_type)")
        .in("user_id", userIds);

      // Load user setup
      const { data: setups } = await supabase
        .from("user_setup")
        .select("*")
        .in("user_id", userIds);

      // Combine data
      const subscriptionMap = new Map(subscriptions?.map(s => [s.user_id, s]));
      const setupMap = new Map(setups?.map(s => [s.user_id, s]));

      const usersWithData = profiles?.map(profile => ({
        ...profile,
        user_subscriptions: subscriptionMap.get(profile.id) ? [subscriptionMap.get(profile.id)] : [],
        user_setup: setupMap.get(profile.id) ? [setupMap.get(profile.id)] : [],
      }));

      setUsers(usersWithData || []);
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

      // Log activity
      const { data: { user: currentUser } } = await supabase.auth.getUser();
      const targetUser = users.find(u => u.id === userId);
      
      if (currentUser && targetUser) {
        await supabase.from("admin_activity_logs").insert({
          admin_user_id: currentUser.id,
          action_type: approved ? "user_approved" : "user_rejected",
          target_user_id: userId,
          description: `${approved ? "Approved" : "Rejected"} setup for ${targetUser.email}${approvalNotes ? ` - ${approvalNotes}` : ""}`,
        });

        // Send email notification to admin
        try {
          await supabase.functions.invoke('send-admin-alert', {
            body: {
              adminEmail: ADMIN_EMAIL,
              actionType: approved ? 'User Approved' : 'User Rejected',
              performedBy: currentUser.email || 'Unknown Admin',
              targetUser: targetUser.email || 'Unknown User',
              details: approved 
                ? `User account has been approved and is now active. The user can now access all platform features according to their subscription plan.${approvalNotes ? `\n\nNotes: ${approvalNotes}` : ''}`
                : `User account setup has been rejected. The user will not be able to access the platform until their setup is approved.${approvalNotes ? `\n\nReason: ${approvalNotes}` : ''}`
            }
          });
        } catch (emailError) {
          console.error('Failed to send admin alert email:', emailError);
        }
      }

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

  const handleBulkApproval = async () => {
    if (selectedUsers.length === 0) {
      toast({
        title: "No users selected",
        description: "Please select users to approve",
        variant: "destructive",
      });
      return;
    }

    setActionLoading(true);
    try {
      const { data: { user: currentUser } } = await supabase.auth.getUser();
      
      for (const userId of selectedUsers) {
        await supabase
          .from("user_setup")
          .update({ admin_approved: true })
          .eq("user_id", userId);

        if (currentUser) {
          const targetUser = users.find(u => u.id === userId);
          await supabase.from("admin_activity_logs").insert({
            admin_user_id: currentUser.id,
            action_type: "bulk_user_approved",
            target_user_id: userId,
            description: `Bulk approved setup for ${targetUser?.email}`,
          });
        }
      }

      toast({
        title: "Bulk Approval Complete",
        description: `${selectedUsers.length} users approved successfully`,
      });

      setSelectedUsers([]);
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

  const handleBulkEmail = async () => {
    if (selectedUsers.length === 0) {
      toast({
        title: "No users selected",
        description: "Please select users to send email",
        variant: "destructive",
      });
      return;
    }

    if (!bulkEmailSubject || !bulkEmailMessage) {
      toast({
        title: "Missing information",
        description: "Please provide subject and message",
        variant: "destructive",
      });
      return;
    }

    setActionLoading(true);
    try {
      const selectedUserEmails = users
        .filter(u => selectedUsers.includes(u.id))
        .map(u => u.email);

      await supabase.functions.invoke('send-custom-email', {
        body: {
          to: selectedUserEmails,
          subject: bulkEmailSubject,
          message: bulkEmailMessage,
        }
      });

      toast({
        title: "Emails Sent",
        description: `Email sent to ${selectedUsers.length} users successfully`,
      });

      setShowBulkEmailDialog(false);
      setBulkEmailSubject("");
      setBulkEmailMessage("");
      setSelectedUsers([]);
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

  const toggleUserSelection = (userId: string) => {
    setSelectedUsers(prev =>
      prev.includes(userId)
        ? prev.filter(id => id !== userId)
        : [...prev, userId]
    );
  };

  const toggleAllUsers = () => {
    if (selectedUsers.length === filteredUsers.length) {
      setSelectedUsers([]);
    } else {
      setSelectedUsers(filteredUsers.map(u => u.id));
    }
  };

  const filteredUsers = users.filter(user => {
    const matchesSearch = user.email?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      user.full_name?.toLowerCase().includes(searchTerm.toLowerCase());
    
    const subscription = user.user_subscriptions?.[0];
    const setup = user.user_setup?.[0];
    const planType = subscription?.plans?.plan_type;

    const matchesStatus = filterStatus === "all" || subscription?.status === filterStatus;
    const matchesPlan = filterPlan === "all" || planType === filterPlan;
    const matchesApproval = filterApproval === "all" || 
      (filterApproval === "approved" && setup?.admin_approved) ||
      (filterApproval === "pending" && setup?.is_completed && !setup?.admin_approved) ||
      (filterApproval === "not_submitted" && !setup?.is_completed);

    return matchesSearch && matchesStatus && matchesPlan && matchesApproval;
  });

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
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>All Users</CardTitle>
                <CardDescription>
                  Manage user accounts and subscriptions
                </CardDescription>
              </div>
              {selectedUsers.length > 0 && (
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="default"
                    onClick={handleBulkApproval}
                    disabled={actionLoading}
                  >
                    <CheckCircle className="w-4 h-4 mr-2" />
                    Approve Selected ({selectedUsers.length})
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setShowBulkEmailDialog(true)}
                    disabled={actionLoading}
                  >
                    <Mail className="w-4 h-4 mr-2" />
                    Email Selected
                  </Button>
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Search and Filters */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="flex items-center gap-2">
                <Search className="w-4 h-4 text-muted-foreground" />
                <Input
                  placeholder="Search users..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
              <Select value={filterStatus} onValueChange={setFilterStatus}>
                <SelectTrigger>
                  <SelectValue placeholder="Filter by status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="trial">Trial</SelectItem>
                  <SelectItem value="expired">Expired</SelectItem>
                </SelectContent>
              </Select>
              <Select value={filterPlan} onValueChange={setFilterPlan}>
                <SelectTrigger>
                  <SelectValue placeholder="Filter by plan" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Plans</SelectItem>
                  <SelectItem value="free">Free</SelectItem>
                  <SelectItem value="starter">Starter</SelectItem>
                  <SelectItem value="pro">Pro</SelectItem>
                  <SelectItem value="enterprise">Enterprise</SelectItem>
                </SelectContent>
              </Select>
              <Select value={filterApproval} onValueChange={setFilterApproval}>
                <SelectTrigger>
                  <SelectValue placeholder="Filter by approval" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Approvals</SelectItem>
                  <SelectItem value="approved">Approved</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                  <SelectItem value="not_submitted">Not Submitted</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12">
                      <Checkbox
                        checked={selectedUsers.length === filteredUsers.length && filteredUsers.length > 0}
                        onCheckedChange={toggleAllUsers}
                      />
                    </TableHead>
                    <TableHead>User</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Plan</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Setup</TableHead>
                    <TableHead>Approval</TableHead>
                    <TableHead>Joined</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredUsers.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={9} className="text-center text-muted-foreground">
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
                          <TableCell>
                            <Checkbox
                              checked={selectedUsers.includes(user.id)}
                              onCheckedChange={() => toggleUserSelection(user.id)}
                            />
                          </TableCell>
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
                          <TableCell>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => setSelectedUserIdForProfile(user.id)}
                              className="gap-2"
                            >
                              <Eye className="w-4 h-4" />
                              View
                            </Button>
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
              {selectedUsers.length > 0 && (
                <span className="text-primary font-medium">{selectedUsers.length} selected</span>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Bulk Email Dialog */}
      <Dialog open={showBulkEmailDialog} onOpenChange={setShowBulkEmailDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Send Email to Selected Users</DialogTitle>
            <DialogDescription>
              Send a custom email to {selectedUsers.length} selected user(s)
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div>
              <Label htmlFor="subject">Subject</Label>
              <Input
                id="subject"
                value={bulkEmailSubject}
                onChange={(e) => setBulkEmailSubject(e.target.value)}
                placeholder="Email subject..."
                className="mt-1.5"
              />
            </div>

            <div>
              <Label htmlFor="message">Message</Label>
              <Textarea
                id="message"
                value={bulkEmailMessage}
                onChange={(e) => setBulkEmailMessage(e.target.value)}
                placeholder="Email message..."
                className="mt-1.5 min-h-[200px]"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowBulkEmailDialog(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleBulkEmail}
              disabled={actionLoading || !bulkEmailSubject || !bulkEmailMessage}
            >
              {actionLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Sending...
                </>
              ) : (
                <>
                  <Mail className="mr-2 h-4 w-4" />
                  Send Email
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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

      <UserProfileModal
        userId={selectedUserIdForProfile}
        open={!!selectedUserIdForProfile}
        onClose={() => setSelectedUserIdForProfile(null)}
      />
    </>
  );
};