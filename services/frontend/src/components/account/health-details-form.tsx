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
function humanizeAgeBand(band: string): string {
  return band.replace(/_/g, " ").replace("plus", "+");
}

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
      toast.success("Health details updated");
    } catch (error) {
      toast.error(friendlyApiError(error));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Your health details</CardTitle>
        <CardDescription>
          Background we use to give better guidance and ask fewer questions.
          Never a diagnosis.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={(event) => void handleSave(event)} className="space-y-6">
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="settings-date-of-birth">Date of birth</FieldLabel>
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
                  ? `We use the age range ${humanizeAgeBand(user.age_band)}, not your exact date.`
                  : "Some conditions are far more likely at one age than another."}
              </FieldDescription>
            </Field>

            <Field>
              <FieldLabel htmlFor="settings-health-note">
                Anything we should know?{" "}
                <span className="text-muted-foreground">(optional)</span>
              </FieldLabel>
              <Textarea
                id="settings-health-note"
                rows={5}
                value={note}
                maxLength={MAX_NOTE_LENGTH}
                disabled={loadingNote}
                onChange={(event) => setNote(event.target.value)}
                placeholder="Conditions you've been told you have, medicines you take, past surgery."
              />
              <FieldDescription>
                {note.length}/{MAX_NOTE_LENGTH}. Clear the box and save to delete
                it.
              </FieldDescription>
            </Field>
          </FieldGroup>

          <div className="flex items-start gap-2 rounded-lg bg-muted/50 p-3 text-xs leading-relaxed text-muted-foreground">
            <Lock className="mt-0.5 size-3.5 shrink-0" />
            <p>
              Only you see this. We treat it as background, not as symptoms
              you&apos;re reporting now, and it never replaces what you tell us in
              a chat.
            </p>
          </div>

          <Button type="submit" disabled={!isDirty || saving}>
            {saving ? "Saving…" : "Save changes"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
