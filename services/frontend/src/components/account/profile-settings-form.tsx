"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/contexts/auth-context";
import { updateProfile } from "@/lib/api/accounts";
import { friendlyApiError } from "@/lib/api/errors";
import { useI18n } from "@/i18n/locale-provider";

export function ProfileSettingsForm() {
  const { user, refreshUser, setUser } = useAuth();
  const { m } = useI18n();
  const a = m.account;
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setName(user?.display_name ?? "");
  }, [user?.display_name]);

  const trimmedName = name.trim();
  const savedName = user?.display_name?.trim() ?? "";
  const isDirty = trimmedName !== savedName;

  async function handleSave(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!isDirty) return;

    setSaving(true);
    try {
      const updated = await updateProfile(trimmedName || null);
      setUser(updated);
      await refreshUser();
      toast.success(trimmedName ? a.nameUpdated : a.nameRemoved);
    } catch (error) {
      toast.error(friendlyApiError(error));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{a.profileTitle}</CardTitle>
        <CardDescription>
          {a.profileLead}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={(event) => void handleSave(event)} className="space-y-6">
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="display-name">{a.name}</FieldLabel>
              <Input
                id="display-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder={m.onboarding.namePlaceholder}
                autoComplete="name"
                maxLength={80}
              />
              <FieldDescription>
                {a.nameHint}
              </FieldDescription>
            </Field>

            <Field>
              <FieldLabel htmlFor="account-email">{a.signInEmail}</FieldLabel>
              <Input
                id="account-email"
                value={user?.email ?? ""}
                readOnly
                disabled
                className="bg-muted/40"
              />
              <FieldDescription>
                {a.signInEmailHint}
              </FieldDescription>
            </Field>
          </FieldGroup>

          <Button type="submit" disabled={!isDirty || saving}>
            {saving ? m.onboarding.saving : a.save}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
