import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { BookOpen, Upload, X, Loader2, Plus } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";

interface TradeJournalDialogProps {
  tradeId: string;
  trigger?: React.ReactNode;
}

export const TradeJournalDialog = ({ tradeId, trigger }: TradeJournalDialogProps) => {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [notes, setNotes] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState("");
  const [screenshots, setScreenshots] = useState<File[]>([]);
  const [existingNote, setExistingNote] = useState<any>(null);
  const { toast } = useToast();

  useEffect(() => {
    if (open) {
      loadExistingNote();
    }
  }, [open, tradeId]);

  const loadExistingNote = async () => {
    const { data } = await supabase
      .from("trade_notes")
      .select("*")
      .eq("trade_id", tradeId)
      .maybeSingle();

    if (data) {
      setExistingNote(data);
      setNotes(data.notes || "");
      setTags(data.tags || []);
    }
  };

  const handleAddTag = () => {
    if (tagInput.trim() && !tags.includes(tagInput.trim())) {
      setTags([...tags, tagInput.trim()]);
      setTagInput("");
    }
  };

  const handleRemoveTag = (tag: string) => {
    setTags(tags.filter((t) => t !== tag));
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setScreenshots(Array.from(e.target.files));
    }
  };

  const uploadScreenshots = async (userId: string): Promise<string[]> => {
    const urls: string[] = [];

    for (const file of screenshots) {
      const fileName = `${userId}/${tradeId}/${Date.now()}-${file.name}`;
      const { error } = await supabase.storage
        .from("trade-screenshots")
        .upload(fileName, file);

      if (!error) {
        const { data } = supabase.storage
          .from("trade-screenshots")
          .getPublicUrl(fileName);
        urls.push(data.publicUrl);
      }
    }

    return urls;
  };

  const handleSave = async () => {
    setLoading(true);
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      // Upload screenshots if any
      let screenshotUrls: string[] = existingNote?.screenshot_urls || [];
      if (screenshots.length > 0) {
        const newUrls = await uploadScreenshots(user.id);
        screenshotUrls = [...screenshotUrls, ...newUrls];
      }

      if (existingNote) {
        // Update existing note
        const { error } = await supabase
          .from("trade_notes")
          .update({
            notes,
            tags,
            screenshot_urls: screenshotUrls,
          })
          .eq("id", existingNote.id);

        if (error) throw error;
      } else {
        // Create new note
        const { error } = await supabase
          .from("trade_notes")
          .insert({
            user_id: user.id,
            trade_id: tradeId,
            notes,
            tags,
            screenshot_urls: screenshotUrls,
          });

        if (error) throw error;
      }

      toast({
        title: "Journal saved",
        description: "Your trade notes have been saved successfully.",
      });
      setOpen(false);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      toast({
        title: "Error",
        description: message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger || (
          <Button variant="outline" size="sm">
            <BookOpen className="w-4 h-4 mr-2" />
            Journal
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[90vh]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-primary" />
            Trading Journal
          </DialogTitle>
          <DialogDescription>
            Add notes, tags, and screenshots to analyze this trade
          </DialogDescription>
        </DialogHeader>

        <ScrollArea className="max-h-[60vh] pr-4">
          <div className="space-y-6">
            {/* Notes Section */}
            <div className="space-y-2">
              <Label htmlFor="notes">Trade Notes</Label>
              <Textarea
                id="notes"
                placeholder="What happened during this trade? What did you learn?"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={6}
                className="resize-none"
              />
            </div>

            {/* Tags Section */}
            <div className="space-y-2">
              <Label>Tags</Label>
              <div className="flex gap-2">
                <Input
                  placeholder="Add a tag (e.g., breakout, revenge trade)"
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyPress={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleAddTag();
                    }
                  }}
                />
                <Button type="button" variant="outline" onClick={handleAddTag}>
                  <Plus className="w-4 h-4" />
                </Button>
              </div>
              {tags.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {tags.map((tag) => (
                    <Badge key={tag} variant="secondary" className="gap-1">
                      {tag}
                      <button
                        onClick={() => handleRemoveTag(tag)}
                        className="ml-1 hover:text-destructive"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
              )}
            </div>

            {/* Screenshots Section */}
            <div className="space-y-2">
              <Label htmlFor="screenshots">Screenshots</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="screenshots"
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={handleFileChange}
                  className="cursor-pointer"
                />
                <Upload className="w-4 h-4 text-muted-foreground" />
              </div>
              {screenshots.length > 0 && (
                <p className="text-sm text-muted-foreground">
                  {screenshots.length} file(s) selected
                </p>
              )}
              {existingNote?.screenshot_urls?.length > 0 && (
                <p className="text-sm text-muted-foreground">
                  {existingNote.screenshot_urls.length} existing screenshot(s)
                </p>
              )}
            </div>
          </div>
        </ScrollArea>

        <div className="flex justify-end gap-2 mt-4">
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={loading}>
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              "Save Journal"
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
