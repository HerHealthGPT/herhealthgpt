"use client";

import { MessageSquarePlus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/i18n/locale-provider";

type ChatConcludedBannerProps = {
  onStartNewChat: () => void;
};

export function ChatConcludedBanner({ onStartNewChat }: ChatConcludedBannerProps) {
  const { m } = useI18n();
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/60 bg-muted/30 px-4 py-3 text-sm">
      <p className="text-muted-foreground">
        {m.chat.concludedBanner}
      </p>
      <Button size="sm" variant="outline" onClick={onStartNewChat}>
        <MessageSquarePlus className="size-3.5" />
        {m.chat.newChat}
      </Button>
    </div>
  );
}
