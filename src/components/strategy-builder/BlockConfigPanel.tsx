import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";
import { Trash2 } from "lucide-react";
import type { PlacedBlock } from "./StrategyBuilder";

// A minimal JSON-Schema-shaped property definition — only the fields this
// panel actually reads out of strategy_blocks.config_schema, which is a
// genuine per-block-type JSON Schema (its full shape varies block to block).
interface JsonSchemaProperty {
  type?: string;
  enum?: string[];
  minimum?: number;
  maximum?: number;
}

type ConfigValue = string | number | undefined;

interface BlockConfigPanelProps {
  block: PlacedBlock;
  onChange: (config: Record<string, unknown>) => void;
  onDelete: () => void;
}

export const BlockConfigPanel = ({ block, onChange, onDelete }: BlockConfigPanelProps) => {
  const { config_schema, default_config } = block.block;
  const config = block.config;

  const handleChange = (key: string, value: ConfigValue) => {
    onChange({ ...config, [key]: value });
  };

  const renderField = (key: string, schema: JsonSchemaProperty) => {
    const value = (config[key] ?? default_config[key]) as ConfigValue;

    // Enum (dropdown)
    if (schema.enum) {
      return (
        <div key={key} className="space-y-2">
          <Label className="capitalize">{key.replace(/_/g, " ")}</Label>
          <Select value={String(value)} onValueChange={(v) => handleChange(key, v)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {schema.enum.map((option: string) => (
                <SelectItem key={option} value={option}>
                  {option}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      );
    }

    // Number with range
    if (schema.type === "number" && schema.minimum !== undefined && schema.maximum !== undefined) {
      return (
        <div key={key} className="space-y-2">
          <div className="flex items-center justify-between">
            <Label className="capitalize">{key.replace(/_/g, " ")}</Label>
            <span className="text-sm text-muted-foreground">{value}</span>
          </div>
          <Slider
            value={[Number(value)]}
            min={schema.minimum}
            max={schema.maximum}
            step={1}
            onValueChange={([v]) => handleChange(key, v)}
          />
        </div>
      );
    }

    // Number input
    if (schema.type === "number") {
      return (
        <div key={key} className="space-y-2">
          <Label className="capitalize">{key.replace(/_/g, " ")}</Label>
          <Input
            type="number"
            value={value ?? ""}
            onChange={(e) => handleChange(key, parseFloat(e.target.value) || 0)}
          />
        </div>
      );
    }

    // String input
    if (schema.type === "string") {
      return (
        <div key={key} className="space-y-2">
          <Label className="capitalize">{key.replace(/_/g, " ")}</Label>
          <Input
            value={value ?? ""}
            onChange={(e) => handleChange(key, e.target.value)}
          />
        </div>
      );
    }

    return null;
  };

  const properties = (config_schema?.properties as Record<string, JsonSchemaProperty> | undefined) || {};

  return (
    <ScrollArea className="h-full">
      <div className="p-4 space-y-6">
        {/* Block Header */}
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-medium">{block.block.name}</h3>
            <Badge variant="outline" className="text-xs mt-1">
              {block.block.block_type}
            </Badge>
          </div>
        </div>

        {/* Description */}
        {block.block.description && (
          <p className="text-sm text-muted-foreground">
            {block.block.description}
          </p>
        )}

        {/* Config Fields */}
        <div className="space-y-4">
          {Object.entries(properties).map(([key, schema]) =>
            renderField(key, schema)
          )}
        </div>

        {/* Delete Button */}
        <Button
          variant="destructive"
          size="sm"
          className="w-full"
          onClick={onDelete}
        >
          <Trash2 className="h-4 w-4 mr-2" />
          Remove Block
        </Button>
      </div>
    </ScrollArea>
  );
};
