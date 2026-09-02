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

export function ProfileSettingsForm() {
  const { user, refreshUser, setUser } = useAuth();
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
      toast.success(trimmedName ? "Name updated" : "Name removed");
    } catch (error) {
      toast.error(friendlyApiError(error));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Your profile</CardTitle>
        <CardDescription>
          This is how we greet you in the app. Your email stays private here.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={(event) => void handleSave(event)} className="space-y-6">
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="display-name">Name</FieldLabel>
              <Input
                id="display-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="What should we call you?"
                autoComplete="name"
                maxLength={80}
              />
              <FieldDescription>
                Optional. Up to 80 characters.
              </FieldDescription>
            </Field>

            <Field>
              <FieldLabel htmlFor="account-email">Sign-in email</FieldLabel>
              <Input
                id="account-email"
                value={user?.email ?? ""}
                readOnly
                disabled
                className="bg-muted/40"
              />
              <FieldDescription>
                Used to sign in. Contact support if you need to change it.
              </FieldDescription>
            </Field>
          </FieldGroup>

          <Button type="submit" disabled={!isDirty || saving}>
            {saving ? "Saving…" : "Save changes"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
