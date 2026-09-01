export type UserSummary = {
  id: string;
  email: string;
  email_verified: boolean;
};

export type PasswordWeakDetail = {
  reasons: string[];
};

export type ValidationErrorItem = {
  type: string;
  loc: (string | number)[];
  msg: string;
  input?: unknown;
};

export type ApiErrorDetail =
  | string
  | PasswordWeakDetail
  | ValidationErrorItem[];

export type ApiErrorBody = {
  detail: ApiErrorDetail;
};
