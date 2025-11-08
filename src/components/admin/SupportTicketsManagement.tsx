import { useState, useEffect } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Loader2, MessageSquare, Clock, CheckCircle, XCircle } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export const SupportTicketsManagement = () => {
  const [tickets, setTickets] = useState<any[]>([]);
  const [selectedTicket, setSelectedTicket] = useState<any>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [newMessage, setNewMessage] = useState("");
  const [filterStatus, setFilterStatus] = useState("all");
  const { toast } = useToast();

  useEffect(() => {
    loadTickets();
    setupRealtime();
  }, [filterStatus]);

  useEffect(() => {
    if (selectedTicket) {
      loadMessages(selectedTicket.id);
    }
  }, [selectedTicket]);

  const setupRealtime = () => {
    const channel = supabase
      .channel('admin-tickets-changes')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'support_tickets' },
        () => loadTickets()
      )
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'ticket_messages' },
        (payload) => {
          if (selectedTicket && payload.new.ticket_id === selectedTicket.id) {
            setMessages(prev => [...prev, payload.new]);
          }
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  };

  const loadTickets = async () => {
    try {
      let query = supabase
        .from("support_tickets" as any)
        .select("*")
        .order("created_at", { ascending: false });

      if (filterStatus !== "all") {
        query = query.eq("status", filterStatus);
      }

      const { data: tickets, error } = await query;

      if (error) throw error;

      // Load user profiles
      const userIds = (tickets as any[])?.map((t: any) => t.user_id) || [];
      const { data: profiles } = await supabase
        .from("profiles")
        .select("id, full_name, email")
        .in("id", userIds);

      const profileMap = new Map(profiles?.map(p => [p.id, p]));
      const ticketsWithProfiles = (tickets as any[])?.map((ticket: any) => ({
        ...ticket,
        profiles: profileMap.get(ticket.user_id),
      }));

      setTickets(ticketsWithProfiles || []);
    } catch (error: any) {
      toast({
        title: "Error loading tickets",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadMessages = async (ticketId: string) => {
    try {
      const { data: messages, error } = await supabase
        .from("ticket_messages" as any)
        .select("*")
        .eq("ticket_id", ticketId)
        .order("created_at", { ascending: true });

      if (error) throw error;

      // Load user profiles for message senders
      const userIds = (messages as any[])?.map((m: any) => m.user_id) || [];
      const { data: profiles } = await supabase
        .from("profiles")
        .select("id, full_name, email")
        .in("id", userIds);

      const profileMap = new Map(profiles?.map(p => [p.id, p]));
      const messagesWithProfiles = (messages as any[])?.map((msg: any) => ({
        ...msg,
        profiles: profileMap.get(msg.user_id),
      }));

      setMessages(messagesWithProfiles || []);
    } catch (error: any) {
      toast({
        title: "Error loading messages",
        description: error.message,
        variant: "destructive",
      });
    }
  };

  const handleUpdateStatus = async (status: string) => {
    if (!selectedTicket) return;

    try {
      const updates: any = { status };
      if (status === "resolved") {
        updates.resolved_at = new Date().toISOString();
      } else if (status === "closed") {
        updates.closed_at = new Date().toISOString();
      }

      const { error } = await supabase
        .from("support_tickets" as any)
        .update(updates)
        .eq("id", selectedTicket.id);

      if (error) throw error;

      toast({
        title: "Status Updated",
        description: `Ticket marked as ${status}`,
      });

      setSelectedTicket({ ...selectedTicket, ...updates });
      loadTickets();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    }
  };

  const handleSendMessage = async () => {
    if (!newMessage.trim() || !selectedTicket) return;

    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) throw new Error("Not authenticated");

      const { error } = await supabase
        .from("ticket_messages" as any)
        .insert([{
          ticket_id: selectedTicket.id,
          user_id: user.id,
          message: newMessage,
          is_admin: true,
        }]);

      if (error) throw error;

      // Update ticket status to in_progress if it's open
      if (selectedTicket.status === "open") {
        await supabase
          .from("support_tickets" as any)
          .update({ status: "in_progress" })
          .eq("id", selectedTicket.id);
      }

      setNewMessage("");
      loadMessages(selectedTicket.id);
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "open": return <Clock className="w-4 h-4" />;
      case "in_progress": return <MessageSquare className="w-4 h-4" />;
      case "resolved": return <CheckCircle className="w-4 h-4" />;
      case "closed": return <XCircle className="w-4 h-4" />;
      default: return <Clock className="w-4 h-4" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "open": return "bg-yellow-500/10 text-yellow-500 border-yellow-500/20";
      case "in_progress": return "bg-blue-500/10 text-blue-500 border-blue-500/20";
      case "resolved": return "bg-green-500/10 text-green-500 border-green-500/20";
      case "closed": return "bg-gray-500/10 text-gray-500 border-gray-500/20";
      default: return "bg-gray-500/10 text-gray-500 border-gray-500/20";
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Tickets List */}
      <Card className="lg:col-span-1">
        <CardHeader>
          <CardTitle>Support Tickets</CardTitle>
          <CardDescription>All customer support requests</CardDescription>
          <Select value={filterStatus} onValueChange={setFilterStatus}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              <SelectItem value="open">Open</SelectItem>
              <SelectItem value="in_progress">In Progress</SelectItem>
              <SelectItem value="resolved">Resolved</SelectItem>
              <SelectItem value="closed">Closed</SelectItem>
            </SelectContent>
          </Select>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[600px]">
            <div className="space-y-2">
              {tickets.length === 0 ? (
                <p className="text-center text-muted-foreground py-8">
                  No tickets found
                </p>
              ) : (
                tickets.map((ticket) => (
                  <div
                    key={ticket.id}
                    onClick={() => setSelectedTicket(ticket)}
                    className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                      selectedTicket?.id === ticket.id
                        ? "border-primary bg-primary/5"
                        : "hover:bg-muted/50"
                    }`}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1">
                        <h4 className="font-medium text-sm">{ticket.subject}</h4>
                        <p className="text-xs text-muted-foreground">
                          {ticket.profiles?.email}
                        </p>
                      </div>
                      <Badge className={getStatusColor(ticket.status)}>
                        {ticket.status}
                      </Badge>
                    </div>
                    <div className="flex gap-1">
                      <Badge variant="outline" className="text-xs">{ticket.category}</Badge>
                      <Badge variant="outline" className="text-xs">{ticket.priority}</Badge>
                    </div>
                  </div>
                ))
              )}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>

      {/* Ticket Details */}
      <Card className="lg:col-span-2">
        <CardHeader>
          {selectedTicket ? (
            <div>
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle>{selectedTicket.subject}</CardTitle>
                  <CardDescription>
                    From: {selectedTicket.profiles?.full_name} ({selectedTicket.profiles?.email})
                  </CardDescription>
                </div>
                <div className="flex gap-2">
                  <Select
                    value={selectedTicket.status}
                    onValueChange={handleUpdateStatus}
                  >
                    <SelectTrigger className="w-[150px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="open">Open</SelectItem>
                      <SelectItem value="in_progress">In Progress</SelectItem>
                      <SelectItem value="resolved">Resolved</SelectItem>
                      <SelectItem value="closed">Closed</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="mt-4 p-3 bg-muted rounded-lg">
                <p className="text-sm">{selectedTicket.description}</p>
              </div>
            </div>
          ) : (
            <CardDescription>Select a ticket to view details</CardDescription>
          )}
        </CardHeader>
        <CardContent>
          {selectedTicket ? (
            <div className="flex flex-col h-[500px]">
              <ScrollArea className="flex-1 mb-4">
                <div className="space-y-4">
                  {messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`flex ${msg.is_admin ? "justify-end" : "justify-start"}`}
                    >
                      <div
                        className={`max-w-[80%] p-3 rounded-lg ${
                          msg.is_admin
                            ? "bg-primary text-primary-foreground"
                            : "bg-muted"
                        }`}
                      >
                        {!msg.is_admin && (
                          <p className="text-xs font-medium mb-1">
                            {msg.profiles?.full_name}
                          </p>
                        )}
                        <p className="text-sm">{msg.message}</p>
                        <p className="text-xs opacity-70 mt-1">
                          {new Date(msg.created_at).toLocaleString()}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
              <div className="border-t pt-4">
                <div className="flex gap-2">
                  <Textarea
                    placeholder="Type your reply..."
                    value={newMessage}
                    onChange={(e) => setNewMessage(e.target.value)}
                    className="min-h-[80px]"
                  />
                  <Button onClick={handleSendMessage} className="self-end">
                    Send Reply
                  </Button>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-[500px]">
              <p className="text-muted-foreground">Select a ticket to view messages</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};