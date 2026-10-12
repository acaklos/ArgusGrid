import { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes, useId } from "react";

// One label / error / help layout for every form control (rules/16 Form + Field).
// Errors are text next to the field and announced with aria-describedby, never colour alone.
interface FrameProps {
  label: string;
  help?: string;
  error?: string | null;
  inline?: boolean;
  children: (ids: { id: string; describedBy: string | undefined; invalid: boolean }) => ReactNode;
}

export function FieldFrame({ label, help, error, inline, children }: FrameProps) {
  const id = useId();
  const helpId = `${id}-help`;
  const errorId = `${id}-error`;
  const describedBy = [help ? helpId : null, error ? errorId : null].filter(Boolean).join(" ") || undefined;
  return (
    <div className={`field${inline ? " field--inline" : ""}`}>
      {!inline && (
        <label className="field__label" htmlFor={id}>
          {label}
        </label>
      )}
      {children({ id, describedBy, invalid: !!error })}
      {inline && (
        <label className="field__label" htmlFor={id}>
          {label}
        </label>
      )}
      {help && (
        <span id={helpId} className="field__help">
          {help}
        </span>
      )}
      {error && (
        <span id={errorId} className="field__error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}

type InputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & {
  label: string;
  help?: string;
  error?: string | null;
};

export function TextField({ label, help, error, ...rest }: InputProps) {
  return (
    <FieldFrame label={label} help={help} error={error}>
      {({ id, describedBy, invalid }) => (
        <input {...rest} id={id} type="text" className="input" aria-describedby={describedBy} aria-invalid={invalid} />
      )}
    </FieldFrame>
  );
}

export function NumberField({ label, help, error, ...rest }: InputProps) {
  return (
    <FieldFrame label={label} help={help} error={error}>
      {({ id, describedBy, invalid }) => (
        <input
          {...rest}
          id={id}
          type="number"
          inputMode="numeric"
          className="input"
          aria-describedby={describedBy}
          aria-invalid={invalid}
        />
      )}
    </FieldFrame>
  );
}

export function CheckboxField({ label, help, error, ...rest }: InputProps) {
  return (
    <FieldFrame label={label} help={help} error={error} inline>
      {({ id, describedBy, invalid }) => (
        <input {...rest} id={id} type="checkbox" aria-describedby={describedBy} aria-invalid={invalid} />
      )}
    </FieldFrame>
  );
}

type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & {
  label: string;
  help?: string;
  error?: string | null;
  options: { value: string; label: string }[];
};

export function SelectField({ label, help, error, options, ...rest }: SelectProps) {
  return (
    <FieldFrame label={label} help={help} error={error}>
      {({ id, describedBy, invalid }) => (
        <select {...rest} id={id} className="select" aria-describedby={describedBy} aria-invalid={invalid}>
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      )}
    </FieldFrame>
  );
}

export function DateTimeField({ label, help, error, ...rest }: InputProps) {
  return (
    <FieldFrame label={label} help={help} error={error}>
      {({ id, describedBy, invalid }) => (
        <input {...rest} id={id} type="datetime-local" className="input" aria-describedby={describedBy} aria-invalid={invalid} />
      )}
    </FieldFrame>
  );
}

type AreaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string; help?: string; error?: string | null };

export function TextAreaField({ label, help, error, ...rest }: AreaProps) {
  return (
    <FieldFrame label={label} help={help} error={error}>
      {({ id, describedBy, invalid }) => (
        <textarea {...rest} id={id} className="input" aria-describedby={describedBy} aria-invalid={invalid}
          spellCheck={false} />
      )}
    </FieldFrame>
  );
}

type FileProps = Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & { label: string; help?: string; error?: string | null };

export function FileField({ label, help, error, ...rest }: FileProps) {
  return (
    <FieldFrame label={label} help={help} error={error}>
      {({ id, describedBy, invalid }) => (
        <input {...rest} id={id} type="file" className="input" aria-describedby={describedBy} aria-invalid={invalid} />
      )}
    </FieldFrame>
  );
}
