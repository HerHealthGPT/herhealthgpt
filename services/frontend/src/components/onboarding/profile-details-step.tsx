"use client";

import { useState } from "react";
import { ArrowRight, CalendarDays, Lock } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/contexts/auth-context";
import { completeProfile, saveHealthNote } from "@/lib/api/accounts";
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
 * The one step in onboarding that collects rather than explains.
 *
 * Two required fields and one optional one, and the split is deliberate:
 *
 * - **Name** — required. It is what the app calls her, in the greeting and
 *   on the dashboard. Cheap to give and it makes a health tool addressing a
 *   worried stranger feel less like a form.
 * - **Date of birth** — required, because age changes what the system
 *   suspects: `knowledge/features.yaml` records that 45 is what separates
 *   perimenopause from PCOS. Without it, every consultation burns one of its
 *   few questions asking. Stored as a date rather than an age so it cannot
 *   go stale.
 * - **Health note** — optional, and it stays optional. Blocking on free-text
 *   clinical background would pressure someone into writing something just
 *   to get past a wall, and unreliable background is worse than none.
 *
 * Both required fields save in a single request. They have to: the backend
 * only touches fields a request names, so sending them separately would mean
 * a half-finished profile if the second call failed.
 */
export function ProfileDetailsStep({ onComplete }: ProfileDetailsStepProps) {
  const { user, setUser, refreshUser } = useAuth();
  const [name, setName] = useState(() => user?.display_name ?? "");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = name.trim() !== "" && dateOfBirth !== "" && !saving;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) return;

    setSaving(true);
    setError(null);
    try {
      const updated = await completeProfile(name.trim(), dateOfBirth);
      // Only after the required fields are accepted, so a rejected date does
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
        <FieldLabel htmlFor="display-name">Your name</FieldLabel>
        <Input
          id="display-name"
          type="text"
          required
          maxLength={80}
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="What should we call you?"
          autoComplete="given-name"
        />
        <FieldDescription>
          Just so we can address you properly. A first name or a nickname is
          plenty.
        </FieldDescription>
      </Field>

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
