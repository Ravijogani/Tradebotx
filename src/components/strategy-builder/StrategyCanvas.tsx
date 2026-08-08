import { useRef, useState, useCallback } from "react";
import { 
  TrendingUp, Activity, BarChart, Target, Clock, 
  Shield, ShoppingCart, XCircle, Filter, Crosshair,
  ArrowUpDown, AlignVerticalJustifyCenter, CandlestickChart,
  GripVertical, X
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { StrategyBlock, PlacedBlock } from "./StrategyBuilder";

interface StrategyCanvasProps {
  blocks: PlacedBlock[];
  availableBlocks: StrategyBlock[];
  onBlockDrop: (block: StrategyBlock, position: { x: number; y: number }) => void;
  onBlockSelect: (block: PlacedBlock) => void;
  onBlockDelete: (blockId: string) => void;
  onBlockMove: (blockId: string, position: { x: number; y: number }) => void;
  onConnect: (fromId: string, toId: string) => void;
  selectedBlockId?: string;
}

const iconMap: Record<string, LucideIcon> = {
  TrendingUp, Activity, BarChart, Target, Clock,
  Shield, ShoppingCart, XCircle, Filter, Crosshair,
  ArrowUpDown, AlignVerticalJustifyCenter, CandlestickChart
};

const categoryColors: Record<string, string> = {
  indicator: "border-blue-500 bg-blue-500/10",
  condition: "border-yellow-500 bg-yellow-500/10",
  action: "border-green-500 bg-green-500/10",
  filter: "border-purple-500 bg-purple-500/10"
};

export const StrategyCanvas = ({
  blocks,
  availableBlocks,
  onBlockDrop,
  onBlockSelect,
  onBlockDelete,
  onBlockMove,
  onConnect,
  selectedBlockId
}: StrategyCanvasProps) => {
  const canvasRef = useRef<HTMLDivElement>(null);
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const [draggingBlockId, setDraggingBlockId] = useState<string | null>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
    setIsDraggingOver(true);
  };

  const handleDragLeave = () => {
    setIsDraggingOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDraggingOver(false);

    const canvasRect = canvasRef.current?.getBoundingClientRect();
    if (!canvasRect) return;

    const position = {
      x: e.clientX - canvasRect.left - 75, // Center the block
      y: e.clientY - canvasRect.top - 30
    };

    try {
      const blockData = e.dataTransfer.getData("application/json");
      if (blockData) {
        const block = JSON.parse(blockData) as StrategyBlock;
        onBlockDrop(block, position);
      }
    } catch (error) {
      console.error("Error parsing dropped block:", error);
    }
  };

  const handleBlockMouseDown = (e: React.MouseEvent, block: PlacedBlock) => {
    if (e.button !== 0) return; // Only left click
    e.stopPropagation();
    
    onBlockSelect(block);
    setDraggingBlockId(block.id);

    const startX = e.clientX;
    const startY = e.clientY;
    const startPos = { ...block.position };

    const handleMouseMove = (moveEvent: MouseEvent) => {
      const dx = moveEvent.clientX - startX;
      const dy = moveEvent.clientY - startY;
      onBlockMove(block.id, {
        x: Math.max(0, startPos.x + dx),
        y: Math.max(0, startPos.y + dy)
      });
    };

    const handleMouseUp = () => {
      setDraggingBlockId(null);
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
  };

  // Draw connections between blocks
  const renderConnections = () => {
    return blocks.map(block => 
      block.connections.map(targetId => {
        const target = blocks.find(b => b.id === targetId);
        if (!target) return null;

        const startX = block.position.x + 150;
        const startY = block.position.y + 30;
        const endX = target.position.x;
        const endY = target.position.y + 30;

        const midX = (startX + endX) / 2;

        return (
          <svg
            key={`${block.id}-${targetId}`}
            className="absolute inset-0 pointer-events-none"
            style={{ width: "100%", height: "100%" }}
          >
            <path
              d={`M ${startX} ${startY} C ${midX} ${startY}, ${midX} ${endY}, ${endX} ${endY}`}
              fill="none"
              stroke="hsl(var(--primary))"
              strokeWidth="2"
              strokeDasharray="4"
            />
            <circle cx={endX} cy={endY} r="4" fill="hsl(var(--primary))" />
          </svg>
        );
      })
    );
  };

  return (
    <div
      ref={canvasRef}
      className={`relative flex-1 bg-muted/30 overflow-auto transition-colors ${
        isDraggingOver ? "bg-primary/5 ring-2 ring-primary ring-inset" : ""
      }`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      style={{
        backgroundImage: `radial-gradient(circle, hsl(var(--border)) 1px, transparent 1px)`,
        backgroundSize: "20px 20px"
      }}
    >
      {blocks.length === 0 && !isDraggingOver && (
        <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
          <div className="text-center">
            <div className="text-4xl mb-4">⟵</div>
            <p className="text-lg font-medium">Drag blocks here to build your strategy</p>
            <p className="text-sm mt-1">Start with an indicator, add conditions, then actions</p>
          </div>
        </div>
      )}

      {renderConnections()}

      {blocks.map((block) => {
        const Icon = iconMap[block.block.icon] || Activity;
        const colorClass = categoryColors[block.block.block_type] || "border-border bg-muted";
        const isSelected = selectedBlockId === block.id;
        const isDragging = draggingBlockId === block.id;

        return (
          <div
            key={block.id}
            className={`absolute flex items-center gap-2 p-3 rounded-lg border-2 cursor-move transition-shadow ${colorClass} ${
              isSelected ? "ring-2 ring-primary shadow-lg" : ""
            } ${isDragging ? "opacity-75 shadow-xl" : ""}`}
            style={{
              left: block.position.x,
              top: block.position.y,
              minWidth: 150
            }}
            onMouseDown={(e) => handleBlockMouseDown(e, block)}
          >
            <GripVertical className="h-4 w-4 text-muted-foreground/50" />
            <Icon className="h-4 w-4 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate">{block.block.name}</div>
              <div className="text-xs text-muted-foreground truncate">
                {Object.entries(block.config).slice(0, 2).map(([k, v]) => 
                  `${k}: ${v}`
                ).join(", ")}
              </div>
            </div>
            <button
              className="p-1 hover:bg-destructive/10 rounded transition-colors"
              onClick={(e) => {
                e.stopPropagation();
                onBlockDelete(block.id);
              }}
            >
              <X className="h-3 w-3 text-destructive" />
            </button>
          </div>
        );
      })}
    </div>
  );
};