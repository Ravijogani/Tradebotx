import * as React from "react";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { useSwipeToDismiss } from "@/hooks/useSwipeToDismiss";
import { cn } from "@/lib/utils";

interface SwipeableDialogProps {
  children: React.ReactNode;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

export const SwipeableDialog: React.FC<SwipeableDialogProps> = ({
  children,
  open,
  onOpenChange
}) => {
  const { ref, isSwiping } = useSwipeToDismiss({
    onDismiss: () => onOpenChange?.(false),
    threshold: 100,
    direction: 'down'
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent 
        ref={ref}
        className={cn(
          "touch-pan-y",
          isSwiping && "transition-none"
        )}
      >
        {/* Swipe Indicator */}
        <div className="absolute top-2 left-1/2 -translate-x-1/2 w-12 h-1 bg-muted rounded-full md:hidden" />
        
        {children}
      </DialogContent>
    </Dialog>
  );
};
