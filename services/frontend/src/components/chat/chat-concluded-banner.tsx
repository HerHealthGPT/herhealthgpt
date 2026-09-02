import { MessageSquarePlus } from "lucide-react";

import { Button } from "@/components/ui/button";

type ChatConcludedBannerProps = {
  onStartNewChat: () => void;
};

export function ChatConcludedBanner({ onStartNewChat }: ChatConcludedBannerProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/60 bg-muted/30 px-4 py-3 text-sm">
      <p className="text-muted-foreground">
        This consultation is complete. Start a new chat if something else comes up.
      </p>
      <Button size="sm" variant="outline" onClick={onStartNewChat}>
        <MessageSquarePlus className="size-3.5" />
        New chat
      </Button>
    </div>
  );
}
