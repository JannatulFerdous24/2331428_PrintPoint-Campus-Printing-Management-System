/** Mirrors the server rules (backend/auth/security.py) to give instant feedback.
 *  The server still checks everything - this is only for convenience. */
export function passwordProblems(password: string, email?: string): string[] {
  const problems: string[] = []
  if (password.length < 10) problems.push("at least 10 characters")
  if (password.length > 128) problems.push("at most 128 characters")
  if (!/[A-Za-z]/.test(password)) problems.push("at least one letter")
  if (!/\d/.test(password)) problems.push("at least one digit")
  if (email && password.trim().toLowerCase() === email.trim().toLowerCase()) {
    problems.push("must not be the same as your email")
  }
  return problems
}
