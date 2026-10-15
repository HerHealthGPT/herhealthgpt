"use client";

import { useEffect, useState } from "react";
import { Lock } from "lucide-react";
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
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/contexts/auth-context";
import {
  deleteHealthNote,
  getHealthNote,
  saveHealthNote,
  updateDateOfBirth,
} from "@/lib/api/accounts";
import { friendlyApiError } from "@/lib/api/errors";
import { useI18n } from "@/i18n/locale-provider";

/** Mirrors profile.MAX_HEALTH_NOTE_LENGTH on the backend. */
const MAX_NOTE_LENGTH = 2000;
/** Mirrors profile.MIN_AGE_YEARS / MAX_AGE_YEARS. */
const MIN_AGE_YEARS = 13;
const MAX_AGE_YEARS = 120;

function isoDateYearsAgo(years: number): string {
  const today = new Date();
  return new Date(today.getFullYear() - years, today.getMonth(), today.getDate())
    .toISOString()
    .slice(0, 10);
}

/** "30_to_39" -> "30 to 39". A reformatting of a real features.yaml value,
 *  never an invented label. */

/**
 * Date of birth and the optional health note, editable after sign-up.
 *
 * Separate from ProfileSettingsForm because these are different kinds of
 * thing: a display name is presentation, this is what the reasoning model is
 * told about her. Keeping them apart means the "only you see this" note sits
 * on exactly the fields it is true of.
 */
export function HealthDetailsForm() {
  const { user, setUser, refreshUser } = useAuth();
  const { m } = useI18n();
  const a = m.account;
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [note, setNote] = useState("");
  const [savedNote, setSavedNote] = useState("");
  const [loadingNote, setLoadingNote] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setDateOfBirth(user?.date_of_birth ?? "");
  }, [user?.date_of_birth]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const fetched = await getHealthNote();
        if (cancelled) return;
        setNote(fetched.content ?? "");
        setSavedNote(fetched.content ?? "");
      } catch {
        // Leave the field empty rather than showing an error for something
        // she may never have written.
      } finally {
        if (!cancelled) setLoadingNote(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const savedDateOfBirth = user?.date_of_birth ?? "";
  const trimmedNote = note.trim();
  const isDirty = dateOfBirth !== savedDateOfBirth || trimmedNote !== savedNote.trim();

  async function handleSave(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!isDirty || saving) return;

    setSaving(true);
    try {
      if (dateOfBirth && dateOfBirth !== savedDateOfBirth) {
        const updated = await updateDateOfBirth(dateOfBirth);
        setUser(updated);
      }
      if (trimmedNote !== savedNote.trim()) {
        if (trimmedNote) {
          await saveHealthNote(trimmedNote);
        } else {
          await deleteHealthNote();
        }
        setSavedNote(trimmedNote);
      }
      await refreshUser();
      toast.success(a.healthUpdated);
    } catch (error) {
      toast.error(friendlyApiError(error));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{a.healthTitle}</CardTitle>
        <CardDescription>
          {a.healthLead}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={(event) => void handleSave(event)} className="space-y-6">
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="settings-date-of-birth">{m.onboarding.dateOfBirth}</FieldLabel>
              <Input
                id="settings-date-of-birth"
                type="date"
                value={dateOfBirth}
                min={isoDateYearsAgo(MAX_AGE_YEARS)}
                max={isoDateYearsAgo(MIN_AGE_YEARS)}
                onChange={(event) => setDateOfBirth(event.target.value)}
                autoComplete="bday"
              />
              <FieldDescription>
                {user?.age_band
                  ? a.ageRange(a.ageBand(user.age_band))
                  : a.ageWhy}
              </FieldDescription>
            </Field>

            <Field>
              <FieldLabel htmlFor="settings-health-note">
                {m.onboarding.anythingToKnow}{" "}
                <span className="text-muted-foreground">{m.onboarding.optional}</span>
              </FieldLabel>
              <Textarea
                id="settings-health-note"
                rows={5}
                value={note}
                maxLength={MAX_NOTE_LENGTH}
                disabled={loadingNote}
                onChange={(event) => setNote(event.target.value)}
                placeholder={a.healthNotePlaceholder}
              />
              <FieldDescription>
                {a.noteCount(note.length, MAX_NOTE_LENGTH)}
              </FieldDescription>
            </Field>
          </FieldGroup>

          <div className="flex items-start gap-2 rounded-lg bg-muted/50 p-3 text-xs leading-relaxed text-muted-foreground">
            <Lock className="mt-0.5 size-3.5 shrink-0" />
            <p>
              {a.healthPrivacy}
            </p>
          </div>

          <Button type="submit" disabled={!isDirty || saving}>
            {saving ? m.onboarding.saving : a.save}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
