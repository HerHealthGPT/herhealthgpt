"use client";

import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";

import { Input } from "./input";
import { useI18n } from "@/i18n/locale-provider";

function PasswordInput({
  className,
  ...props
}: Omit<React.ComponentProps<typeof Input>, "type">) {
  const [visible, setVisible] = useState(false);
  const { m } = useI18n();

  return (
    <div className="relative">
      <Input
        type={visible ? "text" : "password"}
        className={cn("pe-9", className)}
        {...props}
      />
      <button
        type="button"
        tabIndex={-1}
        onClick={() => setVisible((show) => !show)}
        className="absolute top-1/2 end-2 -translate-y-1/2 rounded-md p-1 text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label={visible ? m.common.hidePassword : m.common.showPassword}
      >
        {visible ? (
          <EyeOff className="size-4" aria-hidden />
        ) : (
          <Eye className="size-4" aria-hidden />
        )}
      </button>
    </div>
  );
}

export { PasswordInput };
