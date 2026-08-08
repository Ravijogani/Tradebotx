import { useState, useEffect } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, Plus, Trash2, FileText, Mail, Download, Eye } from "lucide-react";
import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import type { Tables, Json } from "@/integrations/supabase/types";

interface InvoiceItem {
  description: string;
  quantity: number;
  rate: number;
  amount: number;
}

type InvoiceProfile = Pick<Tables<"profiles">, "id" | "full_name" | "email">;
// items is stored as JSONB (Tables<"invoices">.items: Json) — asserted as
// InvoiceItem[] at the read sites below since that's the shape this
// component always writes, not something the DB type can verify for us.
type Invoice = Tables<"invoices"> & { profiles?: Pick<InvoiceProfile, "full_name" | "email"> };

export const InvoiceBuilder = () => {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [users, setUsers] = useState<InvoiceProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [notes, setNotes] = useState("");
  const [items, setItems] = useState<InvoiceItem[]>([
    { description: "", quantity: 1, rate: 0, amount: 0 }
  ]);
  const [actionLoading, setActionLoading] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      // invoices.user_id references auth.users, not public.profiles directly,
      // so there's no FK path PostgREST can use to embed `profiles(...)` in
      // the invoices select (confirmed by the generated types: invoices has
      // an empty Relationships array). Fetch both and merge client-side,
      // same pattern used for support tickets elsewhere in this codebase.
      const [invoicesRes, usersRes] = await Promise.all([
        supabase
          .from("invoices")
          .select("*")
          .order("created_at", { ascending: false }),
        supabase
          .from("profiles")
          .select("id, full_name, email")
          .order("full_name")
      ]);

      if (invoicesRes.error) throw invoicesRes.error;
      if (usersRes.error) throw usersRes.error;

      const profileMap = new Map(usersRes.data?.map(p => [p.id, p]));
      const invoicesWithProfiles = (invoicesRes.data || []).map((invoice) => ({
        ...invoice,
        profiles: profileMap.get(invoice.user_id),
      }));

      setInvoices(invoicesWithProfiles);
      setUsers(usersRes.data || []);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      toast({
        title: "Error loading data",
        description: message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const addItem = () => {
    setItems([...items, { description: "", quantity: 1, rate: 0, amount: 0 }]);
  };

  const removeItem = (index: number) => {
    setItems(items.filter((_, i) => i !== index));
  };

  const updateItem = (index: number, field: keyof InvoiceItem, value: string | number) => {
    const newItems = [...items];
    newItems[index] = { ...newItems[index], [field]: value };
    
    if (field === "quantity" || field === "rate") {
      newItems[index].amount = newItems[index].quantity * newItems[index].rate;
    }
    
    setItems(newItems);
  };

  const calculateTotal = () => {
    return items.reduce((sum, item) => sum + item.amount, 0);
  };

  const generatePDF = (invoice: Invoice): jsPDF => {
    const doc = new jsPDF();
    
    // Header
    doc.setFontSize(20);
    doc.text("INVOICE", 105, 20, { align: "center" });
    
    // Invoice details
    doc.setFontSize(10);
    doc.text(`Invoice #: ${invoice.invoice_number}`, 20, 40);
    doc.text(`Date: ${new Date(invoice.created_at).toLocaleDateString()}`, 20, 46);
    if (invoice.due_date) {
      doc.text(`Due Date: ${new Date(invoice.due_date).toLocaleDateString()}`, 20, 52);
    }
    
    // Customer info
    doc.text(`Bill To:`, 20, 65);
    doc.text(invoice.profiles?.full_name || "N/A", 20, 71);
    doc.text(invoice.profiles?.email || "N/A", 20, 77);
    
    // Items table (items is stored as JSONB — this is the shape this
    // component always writes it in, but the DB type can't verify that)
    const invoiceItems = invoice.items as unknown as InvoiceItem[];
    const tableData = invoiceItems.map((item) => [
      item.description,
      item.quantity.toString(),
      `₹${item.rate.toFixed(2)}`,
      `₹${item.amount.toFixed(2)}`
    ]);
    
    autoTable(doc, {
      startY: 90,
      head: [["Description", "Qty", "Rate", "Amount"]],
      body: tableData,
      foot: [[{ content: "Total", colSpan: 3, styles: { halign: "right" } }, `₹${invoice.amount.toFixed(2)}`]],
      theme: "striped",
      headStyles: { fillColor: [59, 130, 246] },
      footStyles: { fillColor: [241, 245, 249], textColor: [15, 23, 42], fontStyle: "bold" },
    });
    
    // Notes
    if (invoice.notes) {
      // jspdf-autotable attaches this at runtime but doesn't ship types for
      // it in this version — narrower than a blanket any so a typo here
      // would still be caught.
      const finalY = (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY || 90;
      doc.text("Notes:", 20, finalY + 15);
      doc.text(invoice.notes, 20, finalY + 21);
    }
    
    return doc;
  };

  const handleCreateInvoice = async () => {
    if (!selectedUserId || !invoiceNumber || items.some(i => !i.description)) {
      toast({
        title: "Missing information",
        description: "Please fill in all required fields",
        variant: "destructive",
      });
      return;
    }

    setActionLoading(true);
    try {
      const total = calculateTotal();
      
      const { data: invoice, error } = await supabase
        .from("invoices")
        .insert([{
          user_id: selectedUserId,
          invoice_number: invoiceNumber,
          amount: total,
          due_date: dueDate || null,
          notes: notes || null,
          items: items as unknown as Json,
          status: "draft",
        }])
        .select()
        .single();

      if (error) throw error;

      // Generate PDF
      const pdf = generatePDF({ ...invoice, profiles: users.find(u => u.id === selectedUserId), items: items as unknown as Json });
      const pdfBlob = pdf.output("blob");
      
      // Upload PDF to storage
      const fileName = `invoice-${invoice.invoice_number}.pdf`;
      const { error: uploadError } = await supabase.storage
        .from("invoices")
        .upload(fileName, pdfBlob);

      if (uploadError) throw uploadError;

      // Get public URL
      const { data: { publicUrl } } = supabase.storage
        .from("invoices")
        .getPublicUrl(fileName);

      // Update invoice with PDF URL
      await supabase
        .from("invoices")
        .update({ pdf_url: publicUrl })
        .eq("id", invoice.id);

      toast({
        title: "Invoice Created",
        description: "Invoice has been created successfully",
      });

      setShowCreateDialog(false);
      resetForm();
      loadData();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      toast({
        title: "Error",
        description: message,
        variant: "destructive",
      });
    } finally {
      setActionLoading(false);
    }
  };

  const handleCreatePaymentLink = async (invoice: Invoice) => {
    setActionLoading(true);
    try {
      // Create Razorpay order
      const { data: orderData, error: orderError } = await supabase.functions.invoke(
        "create-razorpay-order",
        {
          body: {
            amount: invoice.amount,
            description: `Invoice #${invoice.invoice_number}`,
            metadata: {
              invoice_id: invoice.id,
              invoice_number: invoice.invoice_number,
            },
          },
        }
      );

      if (orderError) throw orderError;

      // Update invoice with payment details
      await supabase
        .from("invoices")
        .update({ 
          status: "awaiting_payment",
          razorpay_order_id: orderData.order_id 
        })
        .eq("id", invoice.id);

      toast({
        title: "Payment Link Created",
        description: "Razorpay payment link created successfully",
      });

      loadData();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      toast({
        title: "Error",
        description: message,
        variant: "destructive",
      });
    } finally {
      setActionLoading(false);
    }
  };

  const handleSendInvoice = async (invoice: Invoice) => {
    setActionLoading(true);
    try {
      const pdf = generatePDF(invoice);
      const pdfBase64 = pdf.output("datauristring");

      await supabase.functions.invoke("send-invoice-email", {
        body: {
          to: invoice.profiles.email,
          invoiceNumber: invoice.invoice_number,
          amount: invoice.amount,
          dueDate: invoice.due_date,
          pdfBase64: pdfBase64,
        },
      });

      await supabase
        .from("invoices")
        .update({ sent_at: new Date().toISOString(), status: "sent" })
        .eq("id", invoice.id);

      toast({
        title: "Invoice Sent",
        description: "Invoice has been emailed to the user",
      });

      loadData();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      toast({
        title: "Error",
        description: message,
        variant: "destructive",
      });
    } finally {
      setActionLoading(false);
    }
  };

  const handleDownloadPDF = (invoice: Invoice) => {
    const pdf = generatePDF(invoice);
    pdf.save(`invoice-${invoice.invoice_number}.pdf`);
  };

  const resetForm = () => {
    setSelectedUserId("");
    setInvoiceNumber("");
    setDueDate("");
    setNotes("");
    setItems([{ description: "", quantity: 1, rate: 0, amount: 0 }]);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Invoice Management</CardTitle>
              <CardDescription>Create and manage invoices for users</CardDescription>
            </div>
            <Button onClick={() => setShowCreateDialog(true)}>
              <Plus className="w-4 h-4 mr-2" />
              Create Invoice
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Invoice #</TableHead>
                  <TableHead>User</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Due Date</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {invoices.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-muted-foreground">
                      No invoices found
                    </TableCell>
                  </TableRow>
                ) : (
                  invoices.map((invoice) => (
                    <TableRow key={invoice.id}>
                      <TableCell className="font-mono">{invoice.invoice_number}</TableCell>
                      <TableCell>
                        <div>
                          <div className="font-medium">{invoice.profiles?.full_name}</div>
                          <div className="text-sm text-muted-foreground">{invoice.profiles?.email}</div>
                        </div>
                      </TableCell>
                      <TableCell className="font-medium">₹{invoice.amount.toFixed(2)}</TableCell>
                      <TableCell>
                        <Badge variant={
                          invoice.status === "paid" ? "default" :
                          invoice.status === "sent" ? "secondary" :
                          "outline"
                        }>
                          {invoice.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {invoice.due_date ? new Date(invoice.due_date).toLocaleDateString() : "N/A"}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {new Date(invoice.created_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleDownloadPDF(invoice)}
                          >
                            <Download className="w-4 h-4" />
                          </Button>
                          {invoice.status === "draft" && (
                            <>
                              <Button
                                size="sm"
                                variant="default"
                                onClick={() => handleSendInvoice(invoice)}
                                disabled={actionLoading}
                              >
                                <Mail className="w-4 h-4" />
                              </Button>
                              <Button
                                size="sm"
                                variant="secondary"
                                onClick={() => handleCreatePaymentLink(invoice)}
                                disabled={actionLoading}
                              >
                                Payment Link
                              </Button>
                            </>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Create Invoice Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Create New Invoice</DialogTitle>
            <DialogDescription>Generate a new invoice for a user</DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="user">Customer</Label>
                <Select value={selectedUserId} onValueChange={setSelectedUserId}>
                  <SelectTrigger id="user">
                    <SelectValue placeholder="Select user" />
                  </SelectTrigger>
                  <SelectContent>
                    {users.map((user) => (
                      <SelectItem key={user.id} value={user.id}>
                        {user.full_name} ({user.email})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label htmlFor="invoiceNumber">Invoice Number</Label>
                <Input
                  id="invoiceNumber"
                  value={invoiceNumber}
                  onChange={(e) => setInvoiceNumber(e.target.value)}
                  placeholder="INV-001"
                />
              </div>
            </div>

            <div>
              <Label htmlFor="dueDate">Due Date (Optional)</Label>
              <Input
                id="dueDate"
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <Label>Invoice Items</Label>
                <Button size="sm" variant="outline" onClick={addItem}>
                  <Plus className="w-4 h-4 mr-2" />
                  Add Item
                </Button>
              </div>
              
              <div className="space-y-2">
                {items.map((item, index) => (
                  <div key={index} className="grid grid-cols-12 gap-2 items-end">
                    <div className="col-span-5">
                      <Input
                        placeholder="Description"
                        value={item.description}
                        onChange={(e) => updateItem(index, "description", e.target.value)}
                      />
                    </div>
                    <div className="col-span-2">
                      <Input
                        type="number"
                        placeholder="Qty"
                        value={item.quantity}
                        onChange={(e) => updateItem(index, "quantity", parseFloat(e.target.value) || 0)}
                      />
                    </div>
                    <div className="col-span-2">
                      <Input
                        type="number"
                        placeholder="Rate"
                        value={item.rate}
                        onChange={(e) => updateItem(index, "rate", parseFloat(e.target.value) || 0)}
                      />
                    </div>
                    <div className="col-span-2">
                      <Input
                        value={`₹${item.amount.toFixed(2)}`}
                        disabled
                      />
                    </div>
                    <div className="col-span-1">
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => removeItem(index)}
                        disabled={items.length === 1}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>

              <div className="flex justify-end mt-4 pt-4 border-t">
                <div className="text-right">
                  <div className="text-sm text-muted-foreground">Total Amount</div>
                  <div className="text-2xl font-bold">₹{calculateTotal().toFixed(2)}</div>
                </div>
              </div>
            </div>

            <div>
              <Label htmlFor="notes">Notes (Optional)</Label>
              <Textarea
                id="notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Additional notes..."
                className="min-h-[100px]"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateInvoice} disabled={actionLoading}>
              {actionLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  <FileText className="mr-2 h-4 w-4" />
                  Create Invoice
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};