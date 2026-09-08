"use client";

import { useState } from "react";
import { ArrowRight, CalendarDays, Lock } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/contexts/auth-context";
import { saveHealthNote, updateDateOfBirth } from "@/lib/api/accounts";
import { friendlyApiError } from "@/lib/api/errors";

/** Mirrors profile.MAX_HEALTH_NOTE_LENGTH on the backend. */
const MAX_NOTE_LENGTH = 2000;

/** Mirrors profile.MIN_AGE_YEARS. Shown as a date bound so the picker itself
 *  refuses an impossible date, rather than waiting for a 400. */
const MIN_AGE_YEARS = 13;
const MAX_AGE_YEARS = 120;

function isoDateYearsAgo(years: number): string {
  const today = new Date();
  const shifted = new Date(
    today.getFullYear() - years,
    today.getMonth(),
    today.getDate(),
  );
  return shifted.toISOString().slice(0, 10);
}

type ProfileDetailsStepProps = {
  /** Called once the date of birth is saved. The note is saved first when
   *  present, but never blocks this — see handleSubmit. */
  onComplete: () => void;
};

/**
 * The one step in onboarding that collects rather than explains: her date of
 * birth (required) and anything she wants us to know (optional).
 *
 * Date of birth is required because age changes what the system suspects —
 * knowledge/features.yaml records that 45 is what separates perimenopause from
 * PCOS — so without it every consultation has to spend a question asking. It
 * is stored as a date, not an age, so it cannot go stale.
 */
export function ProfileDetailsStep({ onComplete }: ProfileDetailsStepProps) {
  const { setUser, refreshUser } = useAuth();
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = dateOfBirth !== "" && !saving;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) return;

    setSaving(true);
    setError(null);
    try {
      const updated = await updateDateOfBirth(dateOfBirth);
      // Only after the required field is accepted, so a rejected date does
      // not leave a note stored against a half-finished profile.
      const trimmedNote = note.trim();
      if (trimmedNote) {
        await saveHealthNote(trimmedNote);
      }
      setUser(updated);
      await refreshUser();
      onComplete();
    } catch (caught) {
      setError(friendlyApiError(caught));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={(event) => void handleSubmit(event)} className="w-full space-y-6">
      <Field>
        <FieldLabel htmlFor="date-of-birth">Date of birth</FieldLabel>
        <Input
          id="date-of-birth"
          type="date"
          required
          value={dateOfBirth}
          min={isoDateYearsAgo(MAX_AGE_YEARS)}
          max={isoDateYearsAgo(MIN_AGE_YEARS)}
          onChange={(event) => setDateOfBirth(event.target.value)}
          autoComplete="bday"
        />
        <FieldDescription>
          Needed, because age changes our guidance — some conditions are far more
          likely at one age than another.
        </FieldDescription>
      </Field>

      <Field>
        <FieldLabel htmlFor="health-note">
          Anything we should know? <span className="text-muted-foreground">(optional)</span>
        </FieldLabel>
        <Textarea
          id="health-note"
          rows={4}
          value={note}
          maxLength={MAX_NOTE_LENGTH}
          onChange={(event) => setNote(event.target.value)}
          placeholder="Conditions you've been told you have, medicines you take, past surgery — anything you'd rather not repeat each time."
        />
        <FieldDescription>
          You can skip this, and change or delete it later in Settings.
        </FieldDescription>
      </Field>

      <div className="flex items-start gap-2 rounded-lg bg-muted/50 p-3 text-xs leading-relaxed text-muted-foreground">
        <Lock className="mt-0.5 size-3.5 shrink-0" />
        <p>
          Only you see this. It gives us background so we ask fewer questions — we
          never treat it as a diagnosis, and it never replaces what you tell us
          about how you feel today.
        </p>
      </div>

      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      <Button type="submit" size="lg" className="w-full" disabled={!canSubmit}>
        {saving ? (
          "Saving…"
        ) : (
          <>
            <CalendarDays className="size-4" />
            Continue
            <ArrowRight className="size-4" />
          </>
        )}
      </Button>
    </form>
  );
}
